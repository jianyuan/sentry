from sentry.testutils.cases import TestCase
from sentry.workflow_engine.endpoints.validators.base import BaseDataConditionGroupValidator
from sentry.workflow_engine.models import Condition, DataConditionGroup


class TestBaseDataConditionGroupValidator(TestCase):
    def setUp(self):
        self.valid_data = {
            "logicType": DataConditionGroup.Type.ANY,
            "organizationId": self.organization.id,
            "conditions": [],
        }

    def test_conditions__empty(self):
        validator = BaseDataConditionGroupValidator(data=self.valid_data)
        assert validator.is_valid() is True

    def test_conditions__valid_conditions(self):
        condition_group = self.create_data_condition_group()
        self.valid_data["conditions"] = [
            {
                "type": Condition.EQUAL,
                "comparison": 1,
                "conditionResult": True,
                "conditionGroupId": condition_group.id,
            },
            {
                "type": Condition.GREATER,
                "comparison": 0,
                "conditionResult": True,
                "conditionGroupId": condition_group.id,
            },
        ]
        validator = BaseDataConditionGroupValidator(data=self.valid_data)

        assert validator.is_valid() is True

    def test_conditions__invalid_condition(self):
        self.valid_data["conditions"] = [{"comparison": 0}]
        validator = BaseDataConditionGroupValidator(data=self.valid_data)
        assert validator.is_valid() is False

    def test_conditions__custom_handler__invalid_to_schema(self):
        self.valid_data["conditions"] = [
            {
                "type": Condition.AGE_COMPARISON,
                "comparison": {
                    "comparison_type": "older",
                    "value": 1,
                    "time": "days",  # Invalid
                },
                "conditionResult": True,
                "conditionGroupId": 1,
            }
        ]

        validator = BaseDataConditionGroupValidator(data=self.valid_data)
        assert validator.is_valid() is False

    def test_conditions__custom_handler__invalid__missing_group_id(self):
        self.valid_data["conditions"] = [
            {
                "type": Condition.AGE_COMPARISON,
                "comparison": {
                    "comparison_type": "older",
                    "value": 1,
                    "time": "day",
                },
                "conditionResult": True,
                # conditionGroupId missing
            }
        ]

        validator = BaseDataConditionGroupValidator(data=self.valid_data)
        assert validator.is_valid() is False

    def test_conditions__custom_handler(self):
        self.valid_data["conditions"] = [
            {
                "type": Condition.AGE_COMPARISON,
                "comparison": {
                    "comparison_type": "older",
                    "value": 1,
                    "time": "day",
                },
                "conditionResult": True,
                "conditionGroupId": 1,
            }
        ]

        validator = BaseDataConditionGroupValidator(data=self.valid_data)
        assert validator.is_valid() is True
