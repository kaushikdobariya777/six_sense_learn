from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import (
    Defect,
    File,
    FileSet,
    MlModel,
    UploadSession,
    ModelClassification,
    ModelClassificationDefect,
)
from django.contrib.auth import get_user_model


class ModelClassificationDefectTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(ModelClassificationDefectTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
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
        cls.classification = ModelClassification.objects.create(file=cls.file, ml_model=cls.ml_model)
        cls.defect = Defect.objects.create(name="test-defect", code="test-code", subscription=cls.subscription)
        ModelClassificationDefect.objects.create(classification=cls.classification, defect=cls.defect)

    def setUp(self) -> None:
        super(ModelClassificationDefectTest, self).setUp()
        self.classification = self.__class__.classification
        self.defect = self.__class__.defect

    def test_field_validation(self):
        model_classification_defect = ModelClassificationDefect(classification=None, defect=None)
        with self.assertValidationErrors(["classification", "defect"]):
            model_classification_defect.full_clean()

        model_classification_defect = ModelClassificationDefect(classification_id=0, defect_id=0)
        with self.assertValidationErrors(["classification", "defect"]):
            model_classification_defect.full_clean()

    def test_unique_together(self):
        model_classification_defect = ModelClassificationDefect(classification=self.classification, defect=self.defect)
        with self.asssertIntegrityErrors(["classification", "defect"]):
            model_classification_defect.save()
