from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import File, FileSet, UploadSession, GTDetection


class GTDetectionTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(GTDetectionTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        GTDetection.objects.create(file=cls.file)

    def setUp(self) -> None:
        super(GTDetectionTest, self).setUp()
        self.file = self.__class__.file

    def test_field_validation(self):
        gt_detection = GTDetection(file=None)
        with self.assertValidationErrors(["file"]):
            gt_detection.full_clean()

        gt_detection = GTDetection(file_id=0)
        with self.assertValidationErrors(["file"]):
            gt_detection.full_clean()

    def test_unique_together(self):
        gt_detection = GTDetection(file=self.file)
        with self.asssertIntegrityErrors(["file"]):
            gt_detection.save()
