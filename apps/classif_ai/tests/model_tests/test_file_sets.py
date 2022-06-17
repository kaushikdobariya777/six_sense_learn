from sixsense import settings
from django.db import transaction
from moto import mock_s3
import tempfile
from common.services import S3Service
import boto3

from apps.classif_ai.models import (
    FileSet,
    UploadSession,
    FileSetInferenceQueue,
    File,
    FileRegion,
    MlModel,
    TrainingSession,
)
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.tests.helpers import prepare_training_session_file_set
from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin


class FileSetTest(ValidationErrorTestMixin, IntegrityErrorTestMixin, ClassifAiTestCase):
    valid_meta_info = {"tray_id": "abcd", "Pass": 1, "row_and_col_id": "xyz", "StartDate": "2020-08-01 06:00"}

    invalid_meta_info = {
        # missing required tray_id field
        "Pass": "abcd",  # Pass is an IntegerField
        "row_and_col_id": True,  # row_and_col_id is a CharField
        "StartDate": 10,  # StartDate is a DateTimeField
    }

    def setUp(self) -> None:
        super(FileSetTest, self).setUp()
        self.use_case = self.__class__.use_case
        self.subscription = self.__class__.subscription
        self.upload_session = UploadSession.objects.create(
            name="test-session", subscription=self.subscription, use_case=self.use_case
        )

    def test_field_validation(self):
        file_set = FileSet(upload_session_id=None, subscription_id=None, meta_info={"asd": "pqr"})
        with self.assertValidationErrors(["subscription"]):
            file_set.full_clean()

        file_set = FileSet(upload_session_id=0, subscription_id=0, meta_info={"asd": "pqr"})
        with self.assertValidationErrors(["upload_session", "subscription"]):
            file_set.full_clean()

        # ToDo: Pick a test subscription which is built with known meta info fields.
        #  Test different kinds of validation errors like if we send string to an integer meta field,
        #  not sending a required meta field etc.

    def test_meta_info_validation(self):
        file_set = FileSet(
            upload_session=self.upload_session, subscription=self.subscription, meta_info=self.valid_meta_info
        )
        file_set.full_clean()

        file_set = FileSet(
            upload_session=self.upload_session, subscription=self.subscription, meta_info=self.invalid_meta_info
        )
        with self.assertValidationErrors(["tray_id", "Pass", "row_and_col_id", "StartDate"]):
            file_set.full_clean()

    def test_delete(self):
        file_set = FileSet.objects.create(
            upload_session=self.upload_session, subscription=self.subscription, meta_info=self.valid_meta_info
        )
        s3_service = S3Service()
        ml_model = MlModel.objects.create(
            code="test-code",
            version=1,
            status="training",
            is_stable=True,
            subscription=self.subscription,
            use_case=self.use_case,
            path={},
            name="test-model",
            training_performance_metrics={},
        )
        file = File.objects.create(file_set=file_set, name="test-file.jpg")
        temp_file = tempfile.NamedTemporaryFile()
        s3_service.upload_file(temp_file.name, file.path)
        temp_file.close()
        file_region = FileRegion.objects.create(file=file, ml_model=ml_model)
        training_session = TrainingSession.objects.create(old_ml_model=ml_model, new_ml_model=ml_model)
        training_session_file_set = prepare_training_session_file_set(training_session, file_set, file.id, file_region)
        training_session.save()
        training_session_file_set.save()
        file_set_inference_queue = FileSetInferenceQueue.objects.create(file_set=file_set, ml_model=ml_model)
        with self.asssertIntegrityErrors(["file_set"]):
            file_set.delete()
        exists = s3_service.check_if_key_exists(file.path)
        self.assertTrue(exists)
        training_session_file_set.delete()
        with self.captureOnCommitCallbacks(execute=True):
            file_set.delete()
        exists = s3_service.check_if_key_exists(file.path)
        self.assertFalse(exists)
        self.assertFalse(FileSet.objects.filter(id=file_set.id).exists())
        self.assertFalse(File.objects.filter(id=file.id).exists())
        self.assertFalse(FileRegion.objects.filter(id=file_region.id).exists())
        self.assertFalse(FileSetInferenceQueue.objects.filter(id=file_set_inference_queue.id).exists())
