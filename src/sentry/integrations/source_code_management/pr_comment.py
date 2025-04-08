from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Generic, NamedTuple, TypeVar

from django.db import connection
from snuba_sdk import Column, Condition, Direction, Entity, Function, Op, OrderBy, Query
from snuba_sdk import Request as SnubaRequest

from sentry.constants import ObjectStatus
from sentry.integrations.services.integration import integration_service
from sentry.integrations.source_code_management.commit_context import CommitContextIntegration
from sentry.models.options.organization_option import OrganizationOption
from sentry.models.organization import Organization
from sentry.models.project import Project
from sentry.models.repository import Repository
from sentry.shared_integrations.exceptions import ApiError
from sentry.snuba.dataset import Dataset
from sentry.snuba.referrer import Referrer
from sentry.tasks.commit_context import DEBOUNCE_PR_COMMENT_CACHE_KEY
from sentry.utils import metrics
from sentry.utils.cache import cache
from sentry.utils.snuba import raw_snql_query

MERGED_PR_METRICS_BASE = "{integration}.pr_comment.{key}"


MAX_SUSPECT_COMMITS = 1000


class PrToIssueQueryResult(NamedTuple):
    repo_id: int
    pr_key: str
    org_id: int
    issue_group_ids: list[int]


PullRequestIssueT = TypeVar("PullRequestIssueT")


class PrCommentIntegration(ABC, Generic[PullRequestIssueT]):
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    @property
    @abstractmethod
    def integration_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def referrer(self) -> Referrer:
        raise NotImplementedError

    @property
    @abstractmethod
    def organization_option_key(self) -> str:
        raise NotImplementedError

    def pr_to_issue_query(self, pr_id: int) -> list[PrToIssueQueryResult]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pr.repository_id repo_id,
                    pr.key pr_key,
                    pr.organization_id org_id,
                    array_agg(go.group_id ORDER BY go.date_added) issues
                FROM sentry_groupowner go
                JOIN sentry_pullrequest_commit c ON c.commit_id = (go.context::jsonb->>'commitId')::bigint
                JOIN sentry_pull_request pr ON c.pull_request_id = pr.id
                WHERE go.type=0
                AND pr.id=%s
                GROUP BY repo_id,
                    pr_key,
                    org_id
                """,
                params=[pr_id],
            )
            return [PrToIssueQueryResult(*row) for row in cursor.fetchall()]

    def get_top_5_issues_by_count(
        self, issue_list: list[int], project: Project
    ) -> list[dict[str, Any]]:
        """Given a list of issue group ids, return a sublist of the top 5 ordered by event count"""
        request = SnubaRequest(
            dataset=Dataset.Events.value,
            app_id="default",
            tenant_ids={"organization_id": project.organization_id},
            query=(
                Query(Entity("events"))
                .set_select([Column("group_id"), Function("count", [], "event_count")])
                .set_groupby([Column("group_id")])
                .set_where(
                    [
                        Condition(Column("project_id"), Op.EQ, project.id),
                        Condition(Column("group_id"), Op.IN, issue_list),
                        Condition(Column("timestamp"), Op.GTE, datetime.now() - timedelta(days=30)),
                        Condition(Column("timestamp"), Op.LT, datetime.now()),
                        Condition(Column("level"), Op.NEQ, "info"),
                    ]
                )
                .set_orderby([OrderBy(Column("event_count"), Direction.DESC)])
                .set_limit(5)
            ),
        )
        return raw_snql_query(request, referrer=self.referrer.value)["data"]

    @abstractmethod
    def get_comment_contents(self, issue_list: list[int]) -> list[PullRequestIssueT]:
        raise NotImplementedError

    @abstractmethod
    def format_comment(self, issues: list[PullRequestIssueT]) -> str:
        raise NotImplementedError

    @abstractmethod
    def build_comment_data_for_organization(
        self,
        organization: Organization,
        repo: Repository,
        pr_key: str,
        comment_body: str,
        issue_list: list[int],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def run_comment_workflow(self, pullrequest_id: int, project_id: int) -> None:
        cache_key = DEBOUNCE_PR_COMMENT_CACHE_KEY(pullrequest_id)

        repo_id, pr_key, org_id, issue_list = self.pr_to_issue_query(pullrequest_id)[0]

        # cap to 1000 issues in which the merge commit is the suspect commit
        issue_list = issue_list[:MAX_SUSPECT_COMMITS]

        try:
            organization = Organization.objects.get_from_cache(id=org_id)
        except Organization.DoesNotExist:
            cache.delete(cache_key)
            self.logger.info(f"{self.integration_name}.pr_comment.org_missing")
            metrics.incr(
                MERGED_PR_METRICS_BASE.format(integration=self.integration_name, key="error"),
                tags={"type": "missing_org"},
            )
            return

        if not OrganizationOption.objects.get_value(
            organization=organization,
            key=self.organization_option_key,
            default=True,
        ):
            self.logger.info(
                f"{self.integration_name}.pr_comment.option_missing",
                extra={"organization_id": org_id},
            )
            return

        try:
            project = Project.objects.get_from_cache(id=project_id)
        except Project.DoesNotExist:
            cache.delete(cache_key)
            self.logger.info(
                f"{self.integration_name}.pr_comment.project_missing",
                extra={"organization_id": org_id},
            )
            metrics.incr(
                MERGED_PR_METRICS_BASE.format(integration=self.integration_name, key="error"),
                tags={"type": "missing_project"},
            )
            return

        top_5_issues = self.get_top_5_issues_by_count(issue_list, project)
        if not top_5_issues:
            self.logger.info(
                f"{self.integration_name}.pr_comment.no_issues",
                extra={"organization_id": org_id, "pr_id": pullrequest_id},
            )
            cache.delete(cache_key)
            return

        top_5_issue_ids = [issue["group_id"] for issue in top_5_issues]

        issue_comment_contents = self.get_comment_contents(top_5_issue_ids)

        try:
            repo = Repository.objects.get(id=repo_id)
        except Repository.DoesNotExist:
            cache.delete(cache_key)
            self.logger.info(
                f"{self.integration_name}.pr_comment.repo_missing",
                extra={"organization_id": org_id},
            )
            metrics.incr(
                MERGED_PR_METRICS_BASE.format(integration=self.integration_name, key="error"),
                tags={"type": "missing_repo"},
            )
            return

        integration = integration_service.get_integration(
            integration_id=repo.integration_id, status=ObjectStatus.ACTIVE
        )
        if not integration:
            cache.delete(cache_key)
            self.logger.info(
                f"{self.integration_name}.pr_comment.integration_missing",
                extra={"organization_id": org_id},
            )
            metrics.incr(
                MERGED_PR_METRICS_BASE.format(integration=self.integration_name, key="error"),
                tags={"type": "missing_integration"},
            )
            return

        installation = integration.get_installation(organization_id=org_id)
        assert isinstance(installation, CommitContextIntegration)

        comment_body = self.format_comment(issue_comment_contents)
        self.logger.info(
            f"{self.integration_name}.pr_comment.comment_body", extra={"body": comment_body}
        )

        top_24_issues = issue_list[:24]  # 24 is the P99 for issues-per-PR

        comment_data = self.build_comment_data_for_organization(
            organization=organization,
            repo=repo,
            pr_key=pr_key,
            comment_body=comment_body,
            issue_list=top_24_issues,
        )

        try:
            installation.create_or_update_comment(
                repo=repo,
                pr_key=pr_key,
                comment_data=comment_data,
                pullrequest_id=pullrequest_id,
                issue_list=top_24_issues,
                metrics_base=MERGED_PR_METRICS_BASE,
            )
        except ApiError as e:
            cache.delete(cache_key)

            if self.on_create_or_update_comment_error(api_error=e):
                return

            metrics.incr(
                MERGED_PR_METRICS_BASE.format(integration=self.integration_name, key="error"),
                tags={"type": "api_error"},
            )
            raise

    @abstractmethod
    def on_create_or_update_comment_error(self, api_error: ApiError) -> bool:
        raise NotImplementedError
