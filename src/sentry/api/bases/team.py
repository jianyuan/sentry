from rest_framework.permissions import BasePermission
from rest_framework.request import Request

from sentry.api.base import Endpoint
from sentry.api.exceptions import ResourceDoesNotExist
from sentry.models.team import Team, TeamStatus
from sentry.utils.sdk import bind_organization_context

from .organization import OrganizationPermission


def has_team_permission(request, team, scope_map):
    allowed_scopes = set(scope_map.get(request.method, []))
    return any(request.access.has_team_scope(team, s) for s in allowed_scopes)


class TeamPermission(OrganizationPermission):
    scope_map = {
        "GET": ["team:read", "team:write", "team:admin"],
        "POST": ["team:write", "team:admin"],
        "PUT": ["team:write", "team:admin"],
        "DELETE": ["team:admin"],
    }

    def has_object_permission(self, request: Request, view, team):
        has_org_scope = super().has_object_permission(request, view, team.organization)
        if has_org_scope:
            # Org-admin has "team:admin", but they can only act on their teams
            # Org-owners and Org-managers have no restrictions due to team memberships
            return request.access.has_team_access(team)

        return has_team_permission(request, team, self.scope_map)


class TeamEndpoint(Endpoint):
    permission_classes: tuple[type[BasePermission], ...] = (TeamPermission,)

    def convert_args(
        self, request: Request, organization_id_or_slug, team_id_or_slug, *args, **kwargs
    ):
        try:
            team = (
                Team.objects.filter(
                    organization__slug__id_or_slug=organization_id_or_slug,
                    slug__id_or_slug=team_id_or_slug,
                )
                .select_related("organization")
                .get()
            )
        except Team.DoesNotExist:
            raise ResourceDoesNotExist

        if team.status != TeamStatus.ACTIVE:
            raise ResourceDoesNotExist

        self.check_object_permissions(request, team)

        bind_organization_context(team.organization)

        request._request.organization = team.organization  # type: ignore[attr-defined]

        kwargs["team"] = team
        return (args, kwargs)
