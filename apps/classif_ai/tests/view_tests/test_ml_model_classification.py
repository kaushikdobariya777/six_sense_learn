from django.contrib.auth import get_user_model
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
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.defect_1 = Defect.objects.create(name="Test-defect_1", code="test-code", subscription=cls.subscription)
        cls.use_case.defects.add(cls.defect_1)
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
        cls.ml_model_classification = ModelClassification.objects.create(
            file=cls.file,
            ml_model=cls.ml_model,
        )
        cls.user = get_user_model().objects.create(email="test@test.com")
        ModelClassificationDefect.objects.create(classification=cls.ml_model_classification, defect=cls.defect_1)

    def get_ml_model_classifications(self, file_id=None, ml_model_id=None):
        url = "/api/v1/classif-ai/ml-model-classification?file=%d&ml_model=%d" % (
            file_id,
            ml_model_id,
        )

        response = self.authorized_client.get(url, content_type="application/json")
        return response

    def test_get_ml_model_classifications(self):
        response = self.get_ml_model_classifications(file_id=self.file.id, ml_model_id=self.ml_model.id)
        data = response.data
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["count"], 1)

        result = data["results"]
        ml_model = result[0]["ml_model"]
        file = result[0]["file"]
        self.assertEqual(ml_model["id"], self.ml_model.id)
        self.assertEqual(file["id"], self.file.id)
        defects = result[0]["defects"]
        self.assertEqual(len(defects), 1)
        self.assertEqual(defects[0]["name"], self.defect_1.name)
