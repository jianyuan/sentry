from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.serializers import serialize
from sentry.models.group import Group
from sentry.models.project import Project
from sentry.sentry_apps.api.bases.sentryapps import (
    SentryAppInstallationExternalIssueBaseEndpoint as ExternalIssueBaseEndpoint,
)
from sentry.sentry_apps.api.parsers.sentry_app import URLField
from sentry.sentry_apps.api.serializers.platform_external_issue import (
    PlatformExternalIssueSerializer as ResponsePlatformExternalIssueSerializer,
)
from sentry.sentry_apps.external_issues.external_issue_creator import ExternalIssueCreator
from sentry.sentry_apps.utils.errors import SentryAppError


class PlatformExternalIssueSerializer(serializers.Serializer):
    webUrl = URLField()
    project = serializers.CharField()
    identifier = serializers.CharField()


@region_silo_endpoint
class SentryAppInstallationExternalIssuesEndpoint(ExternalIssueBaseEndpoint):
    owner = ApiOwner.INTEGRATIONS
    publish_status = {
        "POST": ApiPublishStatus.UNKNOWN,
    }

    def post(self, request: Request, installation) -> Response:
        data = request.data

        try:
            group = Group.objects.get(
                id=data.get("issueId"),
                project_id__in=Project.objects.filter(organization_id=installation.organization_id),
            )
        except Group.DoesNotExist:
            raise SentryAppError(
                message="Could not find the corresponding issue for the given issueId",
                status_code=404,
            )

        serializer = PlatformExternalIssueSerializer(data=request.data)
        if serializer.is_valid():
            external_issue = ExternalIssueCreator(
                install=installation,
                group=group,
                web_url=data["webUrl"],
                project=data["project"],
                identifier=data["identifier"],
            ).run()

            return Response(
                serialize(
                    objects=external_issue, serializer=ResponsePlatformExternalIssueSerializer()
                )
            )

        return Response(serializer.errors, status=400)
