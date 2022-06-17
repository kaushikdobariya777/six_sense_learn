from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import File, FileSet, MlModel, TrainingSession, TrainingSessionFileSet, UploadSession


class TrainingSessionFileSetTest(ClassifAiTestCase, ValidationErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(TrainingSessionFileSetTest, cls).setUpTestData()
        upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        ml_model = MlModel.objects.create(
            code="test-code-1",
            version=1,
            status="training",
            is_stable=False,
            subscription=cls.subscription,
            use_case=cls.use_case,
            path={},
            name="test-model",
        )
        cls.file_set = FileSet.objects.create(
            subscription=cls.subscription, upload_session=upload_session, meta_info={"tray_id": "av"}
        )
        File.objects.create(file_set=cls.file_set, name="test-file")
        cls.training_session = TrainingSession.objects.create(new_ml_model=ml_model, status={"progress": 90})

    def setUp(self) -> None:
        self.file_set = self.__class__.file_set
        self.training_session = self.__class__.training_session

    def test_field_validation(self):
        training_session_file_set = TrainingSessionFileSet(
            file_set=None,
            training_session=None,
            defects={"id": 110, "files": []},
            dataset_train_type="ABCD",
            belongs_to_old_model_training_data=False,
        )
        with self.assertValidationErrors(["file_set", "training_session", "dataset_train_type"]):
            training_session_file_set.full_clean()

        training_session_file_set = TrainingSessionFileSet(
            file_set_id=0,
            training_session_id=0,
            defects={"id": 110, "files": []},
            dataset_train_type="ABCD",
            belongs_to_old_model_training_data=False,
        )
        with self.assertValidationErrors(["file_set", "training_session", "dataset_train_type"]):
            training_session_file_set.full_clean()

        # Test invalid file_id
        training_session_file_set = TrainingSessionFileSet(
            file_set=self.file_set,
            training_session=self.training_session,
            defects={"id": 110, "files": [{"id": 110}]},
            dataset_train_type="TEST",
            belongs_to_old_model_training_data=False,
        )
        with self.assertValidationErrors(["defects"]):
            training_session_file_set.full_clean()


# TODO Need to add test cases for classification and detection defects json
