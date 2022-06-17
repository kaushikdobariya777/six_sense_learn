from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import File, FileSet, UploadSession, UserDetection, UserDetectionRegion
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry


class UserDetectionRegionTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(UserDetectionRegionTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.detection_use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.user = get_user_model().objects.create(email="a@a.com", is_superuser=True, is_staff=True)
        cls.detection = UserDetection.objects.create(file=cls.file, user=cls.user)
        cls.region = GEOSGeometry(
            "POLYGON ((-98.503358 29.335668, -98.503086 29.335668, -98.503086 29.335423, -98.503358 29.335423, -98.503358 29.335668))"
        )
        UserDetectionRegion.objects.create(detection=cls.detection, region=cls.region)

    def setUp(self) -> None:
        super(UserDetectionRegionTest, self).setUp()
        self.detection = self.__class__.detection
        self.region = self.__class__.region

    def test_field_validation(self):
        user_detection_region = UserDetectionRegion(detection=None, region=None)
        with self.assertValidationErrors(["detection", "region"]):
            user_detection_region.full_clean()

        user_detection_region = UserDetectionRegion(detection_id=0, region=None)
        with self.assertValidationErrors(["detection", "region"]):
            user_detection_region.full_clean()

    def test_unique_together(self):
        user_detection_region = UserDetectionRegion(detection=self.detection, region=self.region)
        with self.asssertIntegrityErrors(["detection", "region"]):
            user_detection_region.save()
