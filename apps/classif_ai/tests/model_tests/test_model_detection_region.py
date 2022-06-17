from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import File, FileSet, MlModel, UploadSession, ModelDetection, ModelDetectionRegion
from django.contrib.gis.geos import GEOSGeometry


class ModelDetectionRegionTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(ModelDetectionRegionTest, cls).setUpTestData()
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
        cls.detection = ModelDetection.objects.create(file=cls.file, ml_model=cls.ml_model)
        cls.region = GEOSGeometry(
            "POLYGON ((-98.503358 29.335668, -98.503086 29.335668, -98.503086 29.335423, -98.503358 29.335423, -98.503358 29.335668))"
        )
        ModelDetectionRegion.objects.create(detection=cls.detection, region=cls.region)

    def setUp(self) -> None:
        super(ModelDetectionRegionTest, self).setUp()
        self.detection = self.__class__.detection
        self.region = self.__class__.region

    def test_field_validation(self):
        model_detection_region = ModelDetectionRegion(detection=None, region=None)
        with self.assertValidationErrors(["detection", "region"]):
            model_detection_region.full_clean()

        model_detection_region = ModelDetectionRegion(detection_id=0, region=None)
        with self.assertValidationErrors(["detection", "region"]):
            model_detection_region.full_clean()

    def test_unique_together(self):
        model_detection_region = ModelDetectionRegion(detection=self.detection, region=self.region)
        with self.asssertIntegrityErrors(["detection", "region"]):
            model_detection_region.save()
