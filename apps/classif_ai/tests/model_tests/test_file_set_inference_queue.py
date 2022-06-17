from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import FileSetInferenceQueue, FileSet, UploadSession, MlModel


class FileSetInferenceQueueTest(ValidationErrorTestMixin, ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super(FileSetInferenceQueueTest, cls).setUpTestData()
        valid_meta_info = {"tray_id": "abcd", "Pass": 1, "row_and_col_id": "xyz", "StartDate": "2020-08-01 06:00"}
        cls.ml_model = MlModel.objects.create(
            code="test-code",
            version=1,
            status="training",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.use_case,
            path={},
            name="test-model",
            training_performance_metrics={},
        )
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info=valid_meta_info
        )
        FileSetInferenceQueue.objects.create(file_set=cls.file_set, ml_model=cls.ml_model, status="FAILED")
        FileSetInferenceQueue.objects.create(file_set=cls.file_set, ml_model=cls.ml_model, status="FAILED")
        FileSetInferenceQueue.objects.create(file_set=cls.file_set, ml_model=cls.ml_model, status="FINISHED")

    def setUp(self) -> None:
        super(FileSetInferenceQueueTest, self).setUp()
        self.ml_model = self.__class__.ml_model
        self.file_set = self.__class__.file_set

    def test_field_validation(self):
        # file_set_inference_queue = FileSetInferenceQueue(file_set=None, ml_model=None, status='CHECKING')
        file_set_inference_queue = FileSetInferenceQueue(file_set=self.file_set, ml_model=None, status="CHECKING")
        with self.assertRaises(MlModel.DoesNotExist):
            file_set_inference_queue.full_clean()

        file_set_inference_queue = FileSetInferenceQueue(file_set=None, ml_model=self.ml_model, status="CHECKING")
        with self.assertRaises(FileSet.DoesNotExist):
            file_set_inference_queue.full_clean()

        file_set_inference_queue = FileSetInferenceQueue(
            file_set=self.file_set, ml_model=self.ml_model, status="CHECKING"
        )
        with self.assertValidationErrors(["status", "__all__"]):
            file_set_inference_queue.full_clean()

        # file_set_inference_queue = FileSetInferenceQueue(file_set_id=0, ml_model_id=0, status='PENDING')
        # with self.assertValidationErrors(['file_set', 'ml_model']):
        #     file_set_inference_queue.full_clean()

        file_set_inference_queue = FileSetInferenceQueue(
            file_set=self.file_set, ml_model=self.ml_model, status="FINISHED"
        )
        with self.assertValidationErrors(["__all__"]):
            file_set_inference_queue.full_clean()
