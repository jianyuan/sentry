from typing import Any

from sentry.workflow_engine.models.data_condition import Condition
from sentry.workflow_engine.registry import condition_handler_registry
from sentry.workflow_engine.types import DataConditionHandler, WorkflowJob


@condition_handler_registry.register(Condition.ISSUE_RESOLUTION_CHANGE)
class IssueResolutionConditionHandler(DataConditionHandler[WorkflowJob]):
    group = DataConditionHandler.Group.WORKFLOW_TRIGGER

    @staticmethod
    def evaluate_value(job: WorkflowJob, comparison: Any) -> bool:
        group = job["event"].group
        return group.status == comparison
