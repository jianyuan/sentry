from __future__ import annotations

import logging
from typing import Any, TypedDict

from django.db import router, transaction
from django.http import Http404

from sentry.incidents.models.incident import IncidentStatus
from sentry.incidents.typings.metric_detector import (
    AlertContext,
    MetricIssueContext,
    NotificationContext,
)
from sentry.integrations.metric_alerts import incident_attachment_info
from sentry.integrations.models.organization_integration import OrganizationIntegration
from sentry.integrations.pagerduty.client import PAGERDUTY_DEFAULT_SEVERITY
from sentry.integrations.services.integration import integration_service
from sentry.integrations.services.integration.model import RpcOrganizationIntegration
from sentry.models.organization import Organization
from sentry.shared_integrations.client.proxy import infer_org_integration
from sentry.shared_integrations.exceptions import ApiError
from sentry.silo.base import control_silo_function
from sentry.utils import metrics

logger = logging.getLogger("sentry.integrations.pagerduty")

PAGERDUTY_CUSTOM_PRIORITIES = {
    "critical",
    "warning",
    "error",
    "info",
}  # known as severities in pagerduty


class PagerDutyServiceDict(TypedDict):
    integration_id: int
    integration_key: str
    service_name: str
    id: int


@control_silo_function
def add_service(
    organization_integration: OrganizationIntegration, integration_key: str, service_name: str
) -> PagerDutyServiceDict:
    with transaction.atomic(router.db_for_write(OrganizationIntegration)):
        OrganizationIntegration.objects.filter(id=organization_integration.id).select_for_update()

        with transaction.get_connection(
            router.db_for_write(OrganizationIntegration)
        ).cursor() as cursor:
            cursor.execute(
                "SELECT nextval(%s)", [f"{OrganizationIntegration._meta.db_table}_id_seq"]
            )
            next_id: int = cursor.fetchone()[0]

        service: PagerDutyServiceDict = {
            "id": next_id,
            "integration_key": integration_key,
            "service_name": service_name,
            "integration_id": organization_integration.integration_id,
        }

        existing = organization_integration.config.get("pagerduty_services", [])
        new_services: list[PagerDutyServiceDict] = existing + [service]
        organization_integration.config["pagerduty_services"] = new_services
        organization_integration.save()
    return service


def get_services(
    org_integration: OrganizationIntegration | RpcOrganizationIntegration | None,
) -> list[PagerDutyServiceDict]:
    if not org_integration:
        return []
    return org_integration.config.get("pagerduty_services", [])


def get_service(
    org_integration: OrganizationIntegration | RpcOrganizationIntegration | None,
    service_id: int | str,
) -> PagerDutyServiceDict | None:
    services = get_services(org_integration)
    if not services:
        return None
    service: PagerDutyServiceDict | None = None
    for candidate in services:
        if str(candidate["id"]) == str(service_id):
            service = candidate
            break
    return service


def build_incident_attachment(
    alert_context: AlertContext,
    metric_issue_context: MetricIssueContext,
    organization: Organization,
    integration_key,
    notification_uuid: str | None = None,
) -> dict[str, Any]:

    data = incident_attachment_info(
        organization=organization,
        alert_context=alert_context,
        metric_issue_context=metric_issue_context,
        notification_uuid=notification_uuid,
        referrer="metric_alert_pagerduty",
    )
    severity = "info"
    if metric_issue_context.new_status == IncidentStatus.CRITICAL:
        severity = "critical"
    elif metric_issue_context.new_status == IncidentStatus.WARNING:
        severity = "warning"
    elif metric_issue_context.new_status == IncidentStatus.CLOSED:
        severity = "info"

    event_action = "resolve"
    if metric_issue_context.new_status in [IncidentStatus.WARNING, IncidentStatus.CRITICAL]:
        event_action = "trigger"

    return {
        "routing_key": integration_key,
        "event_action": event_action,
        "dedup_key": f"incident_{organization.id}_{metric_issue_context.open_period_identifier}",
        "payload": {
            "summary": alert_context.name,
            "severity": severity,
            "source": str(metric_issue_context.open_period_identifier),
            "custom_details": {"details": data["text"]},
        },
        "links": [{"href": data["title_link"], "text": data["title"]}],
    }


def attach_custom_severity(
    data: dict[str, Any],
    sentry_app_config: list[dict[str, Any]] | dict[str, Any] | None,
    new_status: IncidentStatus,
) -> dict[str, Any]:
    # use custom severity (overrides default in build_incident_attachment)
    if new_status == IncidentStatus.CLOSED or sentry_app_config is None:
        return data

    if isinstance(sentry_app_config, list):
        raise ValueError("Sentry app config must be a single dict")

    severity = sentry_app_config.get("priority", None)
    if severity is not None and severity != PAGERDUTY_DEFAULT_SEVERITY:
        data["payload"]["severity"] = severity

    return data


def send_incident_alert_notification(
    notification_context: NotificationContext,
    alert_context: AlertContext,
    metric_issue_context: MetricIssueContext,
    organization: Organization,
    notification_uuid: str | None = None,
) -> bool:
    from sentry.integrations.pagerduty.integration import PagerDutyIntegration

    integration_id = notification_context.integration_id
    organization_id = organization.id

    result = integration_service.organization_context(
        organization_id=organization_id,
        integration_id=integration_id,
    )
    integration = result.integration
    org_integration = result.organization_integration
    if integration is None:
        logger.info(
            "pagerduty.integration.missing",
            extra={
                "integration_id": integration_id,
                "organization_id": organization_id,
            },
        )
        raise Http404

    org_integration_id: int | None = None
    if org_integration:
        org_integration_id = org_integration.id
    else:
        org_integrations = None
        if integration_id is not None:
            org_integration_id = infer_org_integration(
                integration_id=integration_id, ctx_logger=logger
            )
        if org_integration_id:
            org_integrations = integration_service.get_organization_integrations(
                org_integration_ids=[org_integration_id]
            )
        if org_integrations:
            org_integration = org_integrations[0]

    install = integration.get_installation(organization_id=organization_id)
    assert isinstance(install, PagerDutyIntegration)
    try:
        client = install.get_keyring_client(str(notification_context.target_identifier))
    except ValueError:
        # service has been removed after rule creation
        logger.info(
            "fetch.fail.pagerduty_metric_alert",
            extra={
                "integration_id": integration_id,
                "organization_id": organization_id,
                "target_identifier": notification_context.target_identifier,
            },
        )
        metrics.incr(
            "pagerduty.metric_alert_rule.integration_removed_after_rule_creation", sample_rate=1.0
        )
        return False

    attachment = build_incident_attachment(
        alert_context=alert_context,
        metric_issue_context=metric_issue_context,
        organization=organization,
        integration_key=client.integration_key,
        notification_uuid=notification_uuid,
    )
    attachment = attach_custom_severity(
        attachment, notification_context.sentry_app_config, metric_issue_context.new_status
    )

    try:
        client.send_trigger(attachment)
        return True
    except ApiError as e:
        logger.info(
            "rule.fail.pagerduty_metric_alert",
            extra={
                "error": str(e),
                "service_id": notification_context.target_identifier,
                "integration_id": integration_id,
            },
        )
        raise
