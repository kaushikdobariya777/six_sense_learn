import json
from apps.classif_ai.models import (
    UploadSession,
    FileSet,
    File,
    MlModel,
    ModelClassification,
    ModelClassificationDefect,
    Defect,
)
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase


class MLModelClassificationTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super(MLModelClassificationTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.single_label_use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            use_case=cls.single_label_use_case,
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

    def setUp(self):
        super().setUp()

    def create_ml_model_classification(self):
        url = "/api/v2/classif-ai/ml-model-classification/"
        json_body = {
            "is_no_defect": False,
            "defects": [{"defect_id": self.defect_1.id, "confidence": 0.96}],
            "file": self.file.id,
            "ml_model": self.ml_model.id,
        }
        response = self.admin_client.post(url, json.dumps(json_body), content_type="application/json")
        return response

    def test_create_ml_model_classification(self):
        response = self.create_ml_model_classification()
        data = response.data
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(data["classification_defects"]), 1)

    def get_ml_model_classifications(self):
        self.create_ml_model_classification()
        url = "/api/v2/classif-ai/ml-model-classification/?file=%d&ml_model=%d" % (
            self.file.id,
            self.ml_model.id,
        )
        response = self.authorized_client.get(url, content_type="application/json")
        return response

    def test_get_ml_model_classifications(self):
        response = self.get_ml_model_classifications()
        data = response.data["results"]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data[0]["classification_defects"]), 1)
