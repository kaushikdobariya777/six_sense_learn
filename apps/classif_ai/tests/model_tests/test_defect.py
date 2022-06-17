from apps.classif_ai.models import Defect
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin


class DefectTest(ValidationErrorTestMixin, IntegrityErrorTestMixin, ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super(DefectTest, cls).setUpTestData()
        cls.defect = Defect.objects.create(name="test-defect", code="test-code", subscription=cls.subscription)

    def setUp(self):
        super(DefectTest, self).setUp()
        self.subscription = self.__class__.subscription
        self.defect = self.__class__.defect

    def test_field_validation(self):
        defect = Defect(name="defect", code="test-code", subscription=None)
        with self.assertValidationErrors(["code", "subscription"]):
            defect.full_clean()

        with self.asssertIntegrityErrors(["name"]):
            Defect.objects.create(name="test-dEFECT", code="code", subscription=self.subscription)

    def test_code_creation(self):
        defect = Defect.objects.create(name="test-creation", subscription=self.subscription)
        self.assertNotEquals(defect.code, "")
