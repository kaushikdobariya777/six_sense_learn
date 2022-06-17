from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import (
    Defect,
    File,
    FileSet,
    UploadSession,
    UserDetection,
    UserDetectionRegion,
    UserDetectionRegionDefect,
)
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry


class UserDetectionRegionDefectTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(UserDetectionRegionDefectTest, cls).setUpTestData()
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
        cls.detection_region = UserDetectionRegion.objects.create(detection=cls.detection, region=cls.region)
        cls.defect = Defect.objects.create(name="test-defect", code="test-code", subscription=cls.subscription)
        UserDetectionRegionDefect.objects.create(detection_region=cls.detection_region, defect=cls.defect)

    def setUp(self) -> None:
        super(UserDetectionRegionDefectTest, self).setUp()
        self.detection_region = self.__class__.detection_region
        self.defect = self.__class__.defect

    def test_field_validation(self):
        user_detection_region_defect = UserDetectionRegionDefect(detection_region=None, defect=None)
        with self.assertValidationErrors(["detection_region", "defect"]):
            user_detection_region_defect.full_clean()

        user_detection_region_defect = UserDetectionRegionDefect(detection_region_id=0, defect_id=None)
        with self.assertValidationErrors(["detection_region", "defect"]):
            user_detection_region_defect.full_clean()

    def test_unique_together(self):
        user_detection_region_defect = UserDetectionRegionDefect(
            detection_region=self.detection_region, defect=self.defect
        )
        with self.asssertIntegrityErrors(["detection_region", "defect"]):
            user_detection_region_defect.save()
