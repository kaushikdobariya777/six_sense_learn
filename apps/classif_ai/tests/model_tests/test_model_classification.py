from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import File, FileSet, MlModel, UploadSession, ModelClassification


class ModelClassificationTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(ModelClassificationTest, cls).setUpTestData()
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
        ModelClassification.objects.create(file=cls.file, ml_model=cls.ml_model)

    def setUp(self) -> None:
        super(ModelClassificationTest, self).setUp()
        self.file = self.__class__.file
        self.ml_model = self.__class__.ml_model

    def test_field_validation(self):
        model_classification = ModelClassification(file=None, ml_model=None)
        with self.assertValidationErrors(["file", "ml_model"]):
            model_classification.full_clean()

        model_classification = ModelClassification(file_id=0, ml_model_id=0)
        with self.assertValidationErrors(["file", "ml_model"]):
            model_classification.full_clean()

    def test_unique_together(self):
        model_classification = ModelClassification(file=self.file, ml_model=self.ml_model)
        with self.asssertIntegrityErrors(["file", "ml_model"]):
            model_classification.save()
