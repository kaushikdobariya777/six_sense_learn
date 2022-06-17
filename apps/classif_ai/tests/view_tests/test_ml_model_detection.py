from django.contrib.auth import get_user_model
from django.contrib.gis.geos import GEOSGeometry

from apps.classif_ai.models import (
    UploadSession,
    FileSet,
    File,
    MlModel,
    Defect,
    ModelDetection,
    ModelDetectionRegion,
    ModelDetectionRegionDefect,
)
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase


class MLModelDetectionTest(ClassifAiTestCase):
    # ToDo: Sai. Review this full class
    @classmethod
    def setUpTestData(cls):
        super(MLModelDetectionTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.defect_1 = Defect.objects.create(name="Test-defect_1", code="test-code", subscription=cls.subscription)
        cls.defect_2 = Defect.objects.create(name="Test-defect_2", code="test-code-2", subscription=cls.subscription)
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
        cls.ml_model_detection = ModelDetection.objects.create(
            file=cls.file,
            ml_model=cls.ml_model,
        )
        cls.region = GEOSGeometry(
            "POLYGON ((-98.503358 29.335668, -98.503086 29.335668, -98.503086 29.335423, -98.503358 29.335423, -98.503358 29.335668))"
        )
        cls.detection_region = ModelDetectionRegion.objects.create(detection=cls.ml_model_detection, region=cls.region)
        ModelDetectionRegionDefect.objects.create(detection_region=cls.detection_region, defect=cls.defect_2)

    def setUp(self):
        super().setUp()

    def get_ml_model_detection(self, pk=None):
        if pk:
            url = "/api/v1/classif-ai/ml-model-detection/%d?file=%d&ml_model=%d" % (
                pk,
                self.file.id,
                self.ml_model_detection.id,
            )
        else:
            url = "/api/v1/classif-ai/ml-model-detection?file=%d&ml_model=%d" % (
                self.file.id,
                self.ml_model_detection.id,
            )
        response = self.authorized_client.get(url, content_type="application/json")
        return response

    def test_get_ml_model_detection(self):
        response = self.get_ml_model_detection()
        data = response.data
        result = data["results"]
        ml_model = result[0]["ml_model"]
        detection_regions = result[0]["detection_regions"]
        defect = detection_regions[0]["defects"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ml_model["code"], "test-code-1")
        self.assertIsNotNone(len(detection_regions[0]["defects"]))
        self.assertEqual(defect[0]["name"], "Test-defect_2")

    def test_get_ml_model_detection_by_id(self):
        response = self.get_ml_model_detection(pk=self.ml_model_detection.id)
        data = response.data
        ml_model = data["ml_model"]
        detection_region = data["detection_regions"]
        defect = detection_region[0]["defects"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ml_model["code"], "test-code-1")
        self.assertEqual(defect[0]["description"], "")
