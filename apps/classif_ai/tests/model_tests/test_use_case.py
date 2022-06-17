from apps.classif_ai.models import UseCase
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin


class UseCaseTest(ValidationErrorTestMixin, IntegrityErrorTestMixin, ClassifAiTestCase):
    def setUp(self):
        self.use_case = self.__class__.use_case
        self.subscription = self.__class__.subscription
        return super().setUp()

    def test_field_validation(self):
        use_case = UseCase(name="use_case", subscription=None, type="PREDICTION", classification_type="INVALID_LABEL")
        with self.assertValidationErrors(["subscription", "type", "classification_type"]):
            use_case.full_clean()

        with self.asssertIntegrityErrors(["name"]):
            UseCase.objects.create(name="TEST-usecase", subscription=self.subscription)
