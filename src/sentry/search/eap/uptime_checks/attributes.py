from sentry.search.eap import constants
from sentry.search.eap.columns import (
    ResolvedAttribute,
    VirtualColumnDefinition,
    datetime_processor,
    project_context_constructor,
    project_term_resolver,
)
from sentry.search.eap.common_columns import COMMON_COLUMNS

UPTIME_CHECK_ATTRIBUTE_DEFINITIONS = {
    column.public_alias: column
    for column in COMMON_COLUMNS
    + [
        ResolvedAttribute(
            public_alias="environment",
            internal_name="environment",
            search_type="string",
        ),
        ResolvedAttribute(
            public_alias="uptime_subscription_id",
            internal_name="uptime_subscription_id",
            search_type="string",
        ),
        ResolvedAttribute(
            public_alias="uptime_check_id",
            internal_name="uptime_check_id",
            search_type="string",
        ),
        ResolvedAttribute(
            public_alias="scheduled_check_time",
            internal_name="scheduled_check_time",
            search_type="string",
            processor=datetime_processor,
        ),
        ResolvedAttribute(
            public_alias="timestamp",
            internal_name="timestamp",
            search_type="string",
            processor=datetime_processor,
        ),
        ResolvedAttribute(
            public_alias="duration_ms",
            internal_name="duration_ms",
            search_type="number",
        ),
        ResolvedAttribute(
            public_alias="region",
            internal_name="region",
            search_type="string",
        ),
        ResolvedAttribute(
            public_alias="check_status",
            internal_name="check_status",
            search_type="string",
        ),
        ResolvedAttribute(
            public_alias="check_status_reason",
            internal_name="check_status_reason",
            search_type="string",
        ),
        ResolvedAttribute(
            public_alias="http_status_code",
            internal_name="http_status_code",
            search_type="number",
        ),
        ResolvedAttribute(
            public_alias="trace_id",
            internal_name="trace_id",
            search_type="string",
        ),
    ]
}

UPTIME_CHECK_VIRTUAL_CONTEXTS = {
    key: VirtualColumnDefinition(
        constructor=project_context_constructor(key),
        term_resolver=project_term_resolver,
        filter_column="project.id",
    )
    for key in constants.PROJECT_FIELDS
}
