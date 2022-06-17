from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import MlModelDefect, Defect, MlModel


class MlModelDefectTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(MlModelDefectTest, cls).setUpTestData()
        cls.ml_model = MlModel.objects.create(
            code="test-code-1",
            version=1,
            status="training",
            is_stable=False,
            subscription=cls.subscription,
            use_case=cls.use_case,
            path={},
            name="test-model",
        )
        cls.defect = Defect.objects.create(
            name="test-defect", description="test-description", subscription=cls.subscription
        )
        MlModelDefect.objects.create(ml_model=cls.ml_model, defect=cls.defect)

    def setUp(self) -> None:
        super(MlModelDefectTest, self).setUp()
        self.ml_model = self.__class__.ml_model
        self.defect = self.__class__.defect

    def test_field_validation(self):
        mlmodel_defect = MlModelDefect(ml_model=None, defect=None)
        with self.assertValidationErrors(["ml_model", "defect"]):
            mlmodel_defect.full_clean()

        mlmodel_defect = MlModelDefect(ml_model_id=0, defect_id=0)
        with self.assertValidationErrors(["ml_model", "defect"]):
            mlmodel_defect.full_clean()

    def test_unique_together(self):
        ml_model = MlModelDefect(ml_model=self.ml_model, defect=self.defect)
        with self.asssertIntegrityErrors(["ml_model", "defect"]):
            ml_model.save()
