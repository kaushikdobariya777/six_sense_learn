from apps.classif_ai.services import InferenceService
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import (
    FileSetInferenceQueue,
    MlModel,
    FileSet,
    ModelClassification,
    ModelClassificationDefect,
    ModelDetection,
    ModelDetectionRegion,
    ModelDetectionRegionDefect,
    UseCase,
    UploadSession,
    Defect,
    File,
)
from unittest.mock import patch
from collections import OrderedDict


class InferenceServiceTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super(InferenceServiceTest, cls).setUpTestData()
        cad_use_case = UseCase.objects.create(
            name="test-usecase-cad", type="CLASSIFICATION_AND_DETECTION", subscription=cls.subscription
        )
        cls.ml_model_1 = MlModel.objects.create(
            name="test-model-1",
            code="test-code-1",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.use_case,
            path={},
            training_performance_metrics={},
        )
        cls.ml_model_2 = MlModel.objects.create(
            name="test-model-2",
            code="test-code-2",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cad_use_case,
            path={},
            training_performance_metrics={},
        )
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set_1 = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file_1 = File.objects.create(file_set=cls.file_set_1, name="test-file-1", path="test/test-path-1")
        cls.file_set_2 = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file_2 = File.objects.create(file_set=cls.file_set_2, name="test-file-2", path="test/test-path-2")
        cls.defect_1 = Defect.objects.create(name="test-defect-1", code="test-code-1", subscription=cls.subscription)
        cls.defect_2 = Defect.objects.create(name="test-defect-2", code="test-code-2", subscription=cls.subscription)
        FileSetInferenceQueue.objects.create(file_set=cls.file_set_1, ml_model=cls.ml_model_1)
        FileSetInferenceQueue.objects.create(file_set=cls.file_set_2, ml_model=cls.ml_model_2)

    def setUp(self) -> None:
        super(InferenceServiceTest, self).setUp()
        self.subscription = self.__class__.subscription
        self.use_case = self.__class__.use_case
        self.file_set_1 = self.__class__.file_set_1
        self.file_set_2 = self.__class__.file_set_2
        self.ml_model_1 = self.__class__.ml_model_1
        self.ml_model_2 = self.__class__.ml_model_2
        self.upload_session = self.__class__.upload_session
        self.defect_1 = self.__class__.defect_1
        self.defect_2 = self.__class__.defect_2
        self.file_1 = self.__class__.file_1
        self.file_2 = self.__class__.file_2

    @patch("apps.classif_ai.services.InferenceService.predict", autospec=True)
    def test_perform_classification_inference(self, mock_predict):
        model_output = {
            "id": self.file_set_2.id,
            "files": [
                OrderedDict(
                    [
                        ("id", self.file_2.id),
                        ("file_set", self.file_set_2.id),
                        ("name", "23_107_1196_CRACK_02.jpg"),
                        ("path", "test.jpg"),
                        ("image", None),
                        (
                            "pre_signed_post_data",
                            {
                                "url": "https://test.com",
                                "fields": {
                                    "key": "test.jpg",
                                    "AWSAccessKeyId": "something",
                                    "policy": "else",
                                    "signature": "sign",
                                },
                            },
                        ),
                        ("url", "https://img.com"),
                        (
                            "file_regions",
                            [
                                {
                                    "region": {
                                        "type": None,
                                        "coordinates": {"h": None, "w": None, "x": None, "y": None},
                                    },
                                    "defects": {self.defect_1.id: {"confidence": 0.9956904}},
                                    "model_output_meta_info": {},
                                },
                                {
                                    "region": {
                                        "type": None,
                                        "coordinates": {"h": None, "w": None, "x": None, "y": None},
                                    },
                                    "defects": {self.defect_2.id: {"confidence": 0.9331}},
                                    "model_output_meta_info": {},
                                },
                            ],
                        ),
                    ]
                )
            ],
            "upload_session": 1,
            "subscription": 1,
            "meta_info": {},
            "created_ts": "2021-03-01T07:06:05.481654Z",
            "updated_ts": "2021-08-08T15:49:29.433047Z",
            "created_by": None,
            "upload_session_name": "test-upload",
            "user_name": None,
            "is_deleted": False,
            "is_bookmarked": False,
            "use_case": 1,
        }
        mock_predict.return_value = model_output
        service = InferenceService(self.ml_model_1.id, self.file_set_1.id)
        service.perform()
        self.assertEquals(ModelClassification.objects.count(), 1)
        self.assertEquals(ModelClassificationDefect.objects.count(), 2)

    @patch("apps.classif_ai.services.InferenceService.predict", autospec=True)
    def test_perform_detection_inference(self, mock_predict):
        model_output = {
            "id": self.file_set_2.id,
            "files": [
                OrderedDict(
                    [
                        ("id", self.file_2.id),
                        ("file_set", self.file_set_2.id),
                        ("name", "23_107_1196_CRACK_02.jpg"),
                        ("path", "test.jpg"),
                        ("image", None),
                        (
                            "pre_signed_post_data",
                            {
                                "url": "https://test.com",
                                "fields": {
                                    "key": "test.jpg",
                                    "AWSAccessKeyId": "something",
                                    "policy": "else",
                                    "signature": "sign",
                                },
                            },
                        ),
                        ("url", "https://img.com"),
                        (
                            "file_regions",
                            [
                                {
                                    "region": {"type": "Box", "coordinates": {"h": 0.3, "w": 0.4, "x": 0.1, "y": 0.1}},
                                    "defects": {self.defect_1.id: {"confidence": 0.9956904}},
                                    "model_output_meta_info": {},
                                },
                                {
                                    "region": {"type": "Box", "coordinates": {"h": 0.5, "w": 0.3, "x": 0.2, "y": 0.2}},
                                    "defects": {self.defect_2.id: {"confidence": 0.9331}},
                                    "model_output_meta_info": {},
                                },
                            ],
                        ),
                    ]
                )
            ],
            "upload_session": 1,
            "subscription": 1,
            "meta_info": {},
            "created_ts": "2021-03-01T07:06:05.481654Z",
            "updated_ts": "2021-08-08T15:49:29.433047Z",
            "created_by": None,
            "upload_session_name": "test-upload",
            "user_name": None,
            "is_deleted": False,
            "is_bookmarked": False,
            "use_case": 1,
        }
        mock_predict.return_value = model_output
        service = InferenceService(self.ml_model_2.id, self.file_set_2.id)
        service.perform()
        # TODO: validate polygons.
        self.assertEquals(ModelDetection.objects.count(), 1)
        self.assertEquals(ModelDetectionRegion.objects.count(), 2)
        self.assertEquals(ModelDetectionRegionDefect.objects.count(), 2)
