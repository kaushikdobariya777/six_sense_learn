from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import FileSet, FileSetInferenceQueue, MlModel, UploadSession
import json


class FileSetInferenceQueueTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.ml_model = MlModel.objects.create(
            name="test-model",
            code="test-code",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.single_label_use_case,
        )
        upload_session = UploadSession.objects.create(
            name="test-upload", subscription=cls.subscription, use_case=cls.use_case
        )
        valid_meta_info = {"tray_id": "abcd", "Pass": 1, "row_and_col_id": "xyz", "StartDate": "2020-08-01 06:00"}
        file_sets = []
        for _ in range(0, 5):
            file_set = FileSet(
                upload_session=upload_session,
                subscription=cls.subscription,
                use_case=cls.use_case,
                meta_info=valid_meta_info,
            )
            file_sets.append(file_set)

        cls.file_sets = FileSet.objects.bulk_create(file_sets)
        inference_queue = []
        statuses = ["PENDING", "FINISHED", "FAILED", "PENDING", "FINISHED"]
        inference_ml_model = MlModel.objects.create(
            name="inference-model",
            code="inference-code",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.single_label_use_case,
        )
        for file_set, status in zip(cls.file_sets, statuses):
            inference_queue.append(
                FileSetInferenceQueue(ml_model=inference_ml_model, file_set=file_set, status=status)
            )
        FileSetInferenceQueue.objects.bulk_create(inference_queue)

    def setUp(self):
        super().setUp()
        self.ml_model = self.__class__.ml_model
        self.file_sets = self.__class__.file_sets

    def test_create_inference_queue(self):
        file_set_id = self.file_sets[0].id
        # TODO(aryan9600): Users shouldn't be able to update the status field.
        response = self.authorized_client.post(
            "/api/v1/classif-ai/file-set-inference-queue/",
            json.dumps({"file_set": file_set_id, "ml_model": self.ml_model.id, "status": "FAILED"}),
            content_type="application/json",
        )

        # Check status code.
        self.assertEquals(response.status_code, 201)
        # Check count.
        self.assertEquals(FileSetInferenceQueue.objects.all().count(), 6)

    def test_list_inference_queue(self):
        response = self.authorized_client.get(
            "/api/v1/classif-ai/file-set-inference-queue/",
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 5)

    def test_progress_status(self):
        response = self.authorized_client.get(
            "/api/v1/classif-ai/file-set-inference-queue/progress_status/?ml_model_id__in=2",
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check results.
        self.assertEquals(response.data["finished"], 2)
        self.assertEquals(response.data["total"], 5)
        self.assertEquals(response.data["failed"], 1)

        failed_file_set_id = FileSetInferenceQueue.objects.get(status="FAILED").file_set_id
        FileSetInferenceQueue.objects.create(file_set_id=failed_file_set_id, ml_model_id=2, status="FINISHED")

        response = self.authorized_client.get(
            "/api/v1/classif-ai/file-set-inference-queue/progress_status/?ml_model_id__in=2",
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check results.
        self.assertEquals(response.data["finished"], 3)
        self.assertEquals(response.data["total"], 5)
        self.assertEquals(response.data["failed"], 0)
