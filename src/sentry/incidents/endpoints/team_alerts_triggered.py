from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDay
from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response

from sentry.api.api_owners import ApiOwner
from sentry.api.api_publish_status import ApiPublishStatus
from sentry.api.base import region_silo_endpoint
from sentry.api.bases.team import TeamEndpoint
from sentry.api.paginator import OffsetPaginator
from sentry.api.serializers import serialize
from sentry.api.utils import get_date_range_from_params
from sentry.incidents.endpoints.serializers.alert_rule import AlertRuleSerializer
from sentry.incidents.models.alert_rule import AlertRule
from sentry.incidents.models.incident import (
    IncidentActivity,
    IncidentActivityType,
    IncidentProject,
    IncidentStatus,
)
from sentry.models.project import Project
from sentry.models.team import Team


@region_silo_endpoint
class TeamAlertsTriggeredTotalsEndpoint(TeamEndpoint):
    owner = ApiOwner.ISSUES
    publish_status = {
        "GET": ApiPublishStatus.PRIVATE,
    }

    def get(self, request: Request, team: Team) -> Response:
        """
        Return a time-bucketed (by day) count of triggered alerts owned by a given team.
        """
        project_list = Project.objects.get_for_team_ids([team.id])
        member_user_ids = team.get_member_user_ids()

        start, end = get_date_range_from_params(request.GET)
        end = end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        bucketed_alert_counts = (
            IncidentActivity.objects.filter(
                (
                    Q(type=IncidentActivityType.CREATED.value)
                    | Q(
                        type=IncidentActivityType.STATUS_CHANGE.value,
                        value__in=[
                            IncidentStatus.OPEN,
                            IncidentStatus.CRITICAL,
                            IncidentStatus.WARNING,
                        ],
                    )
                ),
                (
                    Q(incident__alert_rule__user_id__in=member_user_ids)
                    | Q(incident__alert_rule__team_id=team.id)
                ),
                incident__organization_id=team.organization_id,
                incident_id__in=IncidentProject.objects.filter(project__in=project_list).values(
                    "incident_id"
                ),
                date_added__gte=start,
                date_added__lte=end,
            )
            .annotate(bucket=TruncDay("date_added"))
            .values("bucket")
            .annotate(count=Count("id"))
        )

        counts = {str(r["bucket"].isoformat()): r["count"] for r in bucketed_alert_counts}
        current_day = start
        while current_day < end:
            counts.setdefault(str(current_day.isoformat()), 0)
            current_day += timedelta(days=1)

        return Response(counts)


class TriggeredAlertRuleSerializer(AlertRuleSerializer):
    def __init__(self, start, end):
        super().__init__()
        self.start = start
        self.end = end

    def get_attrs(self, item_list, user, **kwargs):
        result = super().get_attrs(item_list, user, **kwargs)

        qs = (
            AlertRule.objects.filter(
                (
                    Q(incident__incidentactivity__type=IncidentActivityType.CREATED.value)
                    | Q(
                        incident__incidentactivity__type=IncidentActivityType.STATUS_CHANGE.value,
                        incident__incidentactivity__value__in=[
                            str(IncidentStatus.OPEN.value),
                            str(IncidentStatus.CRITICAL.value),
                            str(IncidentStatus.WARNING.value),
                        ],
                    )
                ),
                incident__date_added__gte=self.start,
                incident__date_added__lt=self.end,
                id__in=[item.id for item in item_list],
            )
            .values("id")
            .annotate()
            .annotate(count=Count("id"))
        )
        alert_rule_counts = {row["id"]: row["count"] for row in qs}
        weeks = (self.end - self.start).days // 7

        for alert_rule in item_list:
            alert_rule_attrs = result.setdefault(alert_rule, {})
            alert_rule_attrs["weekly_avg"] = alert_rule_counts.get(alert_rule.id, 0) / weeks
        return result

    def serialize(self, obj, attrs, user, **kwargs):
        result = super().serialize(obj, attrs, user)
        result["weeklyAvg"] = attrs["weekly_avg"]
        result["totalThisWeek"] = obj.count
        return result


@region_silo_endpoint
class TeamAlertsTriggeredIndexEndpoint(TeamEndpoint):
    owner = ApiOwner.ISSUES
    publish_status = {
        "GET": ApiPublishStatus.PRIVATE,
    }

    def get(self, request, team: Team) -> Response:
        """
        Returns alert rules ordered by highest number of alerts fired this week.
        """
        member_user_ids = team.get_member_user_ids()
        end = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start = end - timedelta(days=7)

        qs = AlertRule.objects.filter(
            (
                Q(incident__incidentactivity__type=IncidentActivityType.CREATED.value)
                | Q(
                    incident__incidentactivity__type=IncidentActivityType.STATUS_CHANGE.value,
                    incident__incidentactivity__value__in=[
                        str(IncidentStatus.OPEN.value),
                        str(IncidentStatus.CRITICAL.value),
                        str(IncidentStatus.WARNING.value),
                    ],
                )
            ),
            (Q(user_id__in=member_user_ids) | Q(team_id=team.id)),
            incident__incidentactivity__date_added__gte=start,
            incident__incidentactivity__date_added__lt=end,
            organization_id=team.organization_id,
        ).annotate(count=Count("id"))

        stats_start, stats_end = get_date_range_from_params(request.GET)
        stats_start = stats_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=1
        )
        stats_end = stats_end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

        return self.paginate(
            default_per_page=10,
            request=request,
            queryset=qs,
            order_by=("-count", "name"),
            on_results=lambda x: serialize(
                x, request.user, TriggeredAlertRuleSerializer(stats_start, stats_end)
            ),
            paginator_cls=OffsetPaginator,
        )
