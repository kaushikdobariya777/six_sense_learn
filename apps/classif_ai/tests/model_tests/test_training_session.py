from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import TrainingSession


class TrainingSessionTest(ClassifAiTestCase, ValidationErrorTestMixin):
    def test_field_validation(self):
        training_session = TrainingSession(old_ml_model_id="", new_ml_model=None, status={"test": "status"})
        with self.assertValidationErrors(["new_ml_model"]):
            training_session.full_clean()
