from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import sentry_sdk

from sentry import features
from sentry.constants import ObjectStatus
from sentry.integrations.github.constants import ISSUE_LOCKED_ERROR_MESSAGE, RATE_LIMITED_MESSAGE
from sentry.integrations.github.tasks.utils import PullRequestIssue
from sentry.integrations.services.integration import integration_service
from sentry.integrations.source_code_management.pr_comment import (
    MERGED_PR_METRICS_BASE,
    PrCommentIntegration,
)
from sentry.models.group import Group
from sentry.models.organization import Organization
from sentry.models.pullrequest import PullRequestComment
from sentry.models.repository import Repository
from sentry.shared_integrations.exceptions import ApiError
from sentry.silo.base import SiloMode
from sentry.snuba.referrer import Referrer
from sentry.tasks.base import instrumented_task
from sentry.taskworker.config import TaskworkerConfig
from sentry.taskworker.namespaces import integrations_tasks
from sentry.types.referrer_ids import GITHUB_PR_BOT_REFERRER
from sentry.utils import metrics
from sentry.utils.query import RangeQuerySetWrapper

logger = logging.getLogger(__name__)


class GitHubPrCommentIntegration(PrCommentIntegration[PullRequestIssue]):
    integration_name = "github"
    referrer = Referrer.GITHUB_PR_COMMENT_BOT
    organization_option_key = "sentry:github_pr_bot"

    MERGED_PR_SINGLE_ISSUE_TEMPLATE = "- ‼️ **{title}** `{subtitle}` [View Issue]({url})"

    MERGED_PR_COMMENT_BODY_TEMPLATE = """\
## Suspect Issues
This pull request was deployed and Sentry observed the following issues:

{issue_list}

<sub>Did you find this useful? React with a 👍 or 👎</sub>"""

    def get_comment_contents(self, issue_list: list[int]) -> list[PullRequestIssue]:
        """Retrieve the issue information that will be used for comment contents"""
        issues = Group.objects.filter(id__in=issue_list).order_by("id").all()
        return [
            PullRequestIssue(
                title=issue.title, subtitle=issue.culprit, url=issue.get_absolute_url()
            )
            for issue in issues
        ]

    def format_comment_url(self, url: str, referrer: str) -> str:
        return url + "?referrer=" + referrer

    def format_comment(self, issues: list[PullRequestIssue]) -> str:
        issue_list = "\n".join(
            [
                self.MERGED_PR_SINGLE_ISSUE_TEMPLATE.format(
                    title=issue.title,
                    subtitle=self.format_comment_subtitle(issue.subtitle),
                    url=self.format_comment_url(issue.url, GITHUB_PR_BOT_REFERRER),
                )
                for issue in issues
            ]
        )

        return self.MERGED_PR_COMMENT_BODY_TEMPLATE.format(issue_list=issue_list)

    def build_comment_data_for_organization(
        self,
        organization: Organization,
        repo: Repository,
        pr_key: str,
        comment_body: str,
        issue_list: list[int],
    ) -> dict[str, Any]:
        enabled_copilot = features.has("organizations:gen-ai-features", organization)

        comment_data = {
            "body": comment_body,
        }
        if enabled_copilot:
            comment_data["actions"] = [
                {
                    "name": f"Root cause #{i + 1}",
                    "type": "copilot-chat",
                    "prompt": f"@sentry root cause issue {str(issue_id)} with PR URL https://github.com/{repo.name}/pull/{str(pr_key)}",
                }
                for i, issue_id in enumerate(issue_list[:3])
            ]

        return comment_data

    def on_create_or_update_comment_error(self, api_error: ApiError) -> bool:
        if api_error.json:
            if ISSUE_LOCKED_ERROR_MESSAGE in api_error.json.get("message", ""):
                metrics.incr(
                    MERGED_PR_METRICS_BASE.format(integration=self.integration_name, key="error"),
                    tags={"type": "issue_locked_error"},
                )
                return True

            elif RATE_LIMITED_MESSAGE in api_error.json.get("message", ""):
                metrics.incr(
                    MERGED_PR_METRICS_BASE.format(integration=self.integration_name, key="error"),
                    tags={"type": "rate_limited_error"},
                )
                return True

        return False


@instrumented_task(
    name="sentry.integrations.github.tasks.github_comment_workflow",
    silo_mode=SiloMode.REGION,
    taskworker_config=TaskworkerConfig(
        namespace=integrations_tasks,
    ),
)
def github_comment_workflow(pullrequest_id: int, project_id: int) -> None:
    pr_comment_integration = GitHubPrCommentIntegration(logger=logger)
    pr_comment_integration.run_comment_workflow(
        pullrequest_id=pullrequest_id, project_id=project_id
    )


@instrumented_task(
    name="sentry.integrations.github.tasks.github_comment_reactions",
    silo_mode=SiloMode.REGION,
    taskworker_config=TaskworkerConfig(
        namespace=integrations_tasks,
    ),
)
def github_comment_reactions():
    logger.info("github.pr_comment.reactions_task")

    comments = PullRequestComment.objects.filter(
        created_at__gte=datetime.now(tz=timezone.utc) - timedelta(days=30)
    ).select_related("pull_request")

    comment_count = 0

    for comment in RangeQuerySetWrapper(comments):
        pr = comment.pull_request
        try:
            repo = Repository.objects.get(id=pr.repository_id)
        except Repository.DoesNotExist:
            metrics.incr("pr_comment.comment_reactions.missing_repo")
            continue

        integration = integration_service.get_integration(
            integration_id=repo.integration_id, status=ObjectStatus.ACTIVE
        )
        if not integration:
            logger.info(
                "pr_comment.comment_reactions.integration_missing",
                extra={
                    "organization_id": pr.organization_id,
                },
            )
            metrics.incr("pr_comment.comment_reactions.missing_integration")
            continue

        installation = integration.get_installation(organization_id=pr.organization_id)

        # GitHubApiClient
        # TODO(cathy): create helper function to fetch client for repo
        client = installation.get_client()

        try:
            reactions = client.get_comment_reactions(repo=repo.name, comment_id=comment.external_id)

            comment.reactions = reactions
            comment.save()
        except ApiError as e:
            if e.json and RATE_LIMITED_MESSAGE in e.json.get("message", ""):
                metrics.incr("pr_comment.comment_reactions.rate_limited_error")
                break

            if e.code == 404:
                metrics.incr("pr_comment.comment_reactions.not_found_error")
            else:
                metrics.incr("pr_comment.comment_reactions.api_error")
                sentry_sdk.capture_exception(e)
            continue

        comment_count += 1

        metrics.incr("pr_comment.comment_reactions.success")

    logger.info("pr_comment.comment_reactions.total_collected", extra={"count": comment_count})
