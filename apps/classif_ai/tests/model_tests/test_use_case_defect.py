from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import Defect, UseCaseDefect


class UseCaseDefectTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(UseCaseDefectTest, cls).setUpTestData()
        cls.defect = Defect.objects.create(
            name="test-defect", description="test-description", subscription=cls.subscription
        )
        UseCaseDefect.objects.create(use_case=cls.use_case, defect=cls.defect)

    def setUp(self) -> None:
        super(UseCaseDefectTest, self).setUp()
        self.use_case = self.__class__.use_case
        self.defect = self.__class__.defect

    def test_field_validation(self):
        use_case_defect = UseCaseDefect(use_case=None, defect=None)
        with self.assertValidationErrors(["use_case", "defect"]):
            use_case_defect.full_clean()

        use_case_defect = UseCaseDefect(use_case_id=0, defect_id=0)
        with self.assertValidationErrors(["use_case", "defect"]):
            use_case_defect.full_clean()

    def test_unique_together(self):
        use_case_defect = UseCaseDefect(use_case=self.use_case, defect=self.defect)
        with self.asssertIntegrityErrors(["use_case", "defect"]):
            use_case_defect.save()
