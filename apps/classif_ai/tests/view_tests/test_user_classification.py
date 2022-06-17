import json

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.classif_ai.models import (
    Defect,
    UploadSession,
    FileSet,
    File,
    UserClassification,
    UseCase,
    UseCaseDefect,
    UserClassificationDefect,
)
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase


class UserClassificationTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super(UserClassificationTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-upload-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.file_1 = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.defect_1 = Defect.objects.create(name="defect-1", subscription=cls.subscription)
        cls.defect_2 = Defect.objects.create(name="defect-2", subscription=cls.subscription)
        cls.usecase_defect_1 = UseCaseDefect.objects.create(use_case=cls.use_case, defect=cls.defect_1)
        cls.usecase_defect_2 = UseCaseDefect.objects.create(use_case=cls.use_case, defect=cls.defect_2)

        # Single label
        cls.single_label_upload_session = UploadSession.objects.create(
            name="single-label-upload-session", subscription=cls.subscription, use_case=cls.single_label_use_case
        )
        cls.single_label_file_set = FileSet.objects.create(
            upload_session=cls.single_label_upload_session,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
        )
        cls.single_label_file = File.objects.create(
            file_set=cls.single_label_file_set, name="test-file-name", path="test/test-path"
        )
        cls.single_label_defect = Defect.objects.create(
            name="new-defect-from-other-usecase", code="other-use-case-defect", subscription=cls.subscription
        )
        cls.single_label_use_case_defect = UseCaseDefect.objects.create(
            use_case=cls.single_label_use_case, defect=cls.single_label_defect
        )

    def setUp(self):
        super().setUp()
        self.defect_1 = self.__class__.defect_1
        self.defect_2 = self.__class__.defect_2

    def create_user_classification_with_defects(self):
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/",
            json.dumps(
                {
                    "is_no_defect": False,
                    "file": self.file.id,
                    "defects": [self.defect_1.id, self.defect_2.id],
                }
            ),
            content_type="application/json",
        )
        data = response.data
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(data["file"], "The file doesn't exist in the response")
        self.assertEqual(data["file"], self.file.id)
        self.assertEqual(len(data["defects"]), 2)
        return response

    def create_user_classification_without_defects(self):
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/",
            json.dumps(
                {
                    "is_no_defect": True,
                    "file": self.file.id,
                    "defects": [self.defect_1.id, self.defect_2.id],
                    # The param user from the request body is ignored and logged in user gets picked up
                    "user": 1,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/",
            json.dumps({"is_no_defect": True, "file": self.file.id, "defects": []}),
            content_type="application/json",
        )
        data = response.data
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(data["file"], "The file doesn't exist in the response")
        self.assertEqual(data["file"], self.file.id)
        self.assertEqual(len(data["defects"]), 0)
        return response

    def test_create_user_classification_with_defects(self):
        response = self.create_user_classification_with_defects()

        # Check status code.
        self.assertEqual(response.status_code, 201)

        data = response.data
        # Check response data.
        self.assertIsNotNone(data["file"], "The file doesn't exist in the response")
        self.assertEqual(data["file"], self.file.id)
        self.assertEqual(data["user"], self.user.id)

        # Check related defects.
        self.assertEqual(len(data["defects"]), 2)

    def test_create_user_classification_without_defects(self):
        response = self.create_user_classification_without_defects()

        # Check status code.
        self.assertEqual(response.status_code, 201)

        data = response.data
        # Check response data.
        self.assertIsNotNone(data["file"], "The file doesn't exist in the response")
        self.assertEqual(data["file"], self.file.id)
        self.assertEqual(data["user"], self.user.id)

        # Check related defects.
        self.assertEqual(len(data["defects"]), 0)

    def test_update_user_classification_with_defects(self):
        resp = self.create_user_classification_with_defects()
        user_classification = resp.data
        response = self.authorized_client.put(
            "/api/v1/classif-ai/user-classification/%s/" % user_classification["id"],
            json.dumps({"is_no_defect": False, "file": self.file.id, "defects": [self.defect_1.id]}),
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 200)

        data = response.data
        # Check response data.
        self.assertIsNotNone(data["file"], "The file doesn't exist in the response")
        self.assertEqual(data["file"], self.file.id)
        self.assertEqual(data["user"], self.user.id)

        # Check related defects.
        self.assertEqual(len(data["defects"]), 1)

    def test_update_user_classification_without_defects(self):
        resp = self.create_user_classification_with_defects()
        user_classification = resp.data
        response = self.authorized_client.put(
            "/api/v1/classif-ai/user-classification/%s/" % user_classification["id"],
            json.dumps({"is_no_defect": True, "defects": [self.defect_1.id]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        response = self.authorized_client.put(
            "/api/v1/classif-ai/user-classification/%s/" % user_classification["id"],
            json.dumps({"is_no_defect": True}),
            content_type="application/json",
        )
        # ToDo: We need to add a test case which gives 400 status code when is_no_defect is marked as False and defects
        #  param isn't there or is empty

        # Check status code.
        self.assertEqual(response.status_code, 200)

        data = response.data
        # Check response data.
        self.assertIsNotNone(data["file"], "The file doesn't exist in the response")
        self.assertEqual(data["file"], self.file.id)
        self.assertEqual(data["user"], self.user.id)

        # Check related defects.
        self.assertEqual(len(data["defects"]), 0)

    def test_update_file_and_user_in_user_classification(self):
        resp = self.create_user_classification_with_defects()
        user_classification = resp.data
        new_user = get_user_model().objects.create_user(
            email="asdasdj@asdjhc.com",
            password="TEST_USER_PASSWORD",
            first_name="TEST_USER_FIRST_NAME",
            last_name="TEST_USER_LAST_NAME",
            is_active=True,
        )
        new_file = File.objects.create(file_set=self.file_set, name="asdasjdk.jpg")
        response = self.authorized_client.put(
            "/api/v1/classif-ai/user-classification/%s/" % user_classification["id"],
            json.dumps(
                {"is_no_defect": True, "file": self.file.id, "user": new_user.id, "defects": [self.defect_1.id]}
            ),
            content_type="application/json",
        )
        # ToDo: We need to add a test case which gives 400 status code when is_no_defect is marked as False and defects
        #  param isn't there or is empty

        # Check status code.
        self.assertEqual(response.status_code, 400)
        response = self.authorized_client.put(
            "/api/v1/classif-ai/user-classification/%s/" % user_classification["id"],
            json.dumps({"is_no_defect": True, "file": new_file.id, "defects": [self.defect_1.id]}),
            content_type="application/json",
        )
        # ToDo: We need to add a test case which gives 400 status code when is_no_defect is marked as False and defects
        #  param isn't there or is empty
        # Check status code.
        self.assertEqual(response.status_code, 400)

    def test_list_user_classif_defects(self):
        response = self.authorized_client.get(
            "/api/v1/classif-ai/user-classification/",
            content_type="application/json",
        )
        # ToDo: Add more users and test the user filter well

        # Check status code.
        self.assertEqual(response.status_code, 400)

        response = self.authorized_client.get(
            "/api/v1/classif-ai/user-classification/?file=%s" % self.file.id,
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 200)

    def test_get_user_classif_defects(self):
        user_classification = UserClassification.objects.create(file=self.file, user=self.user)
        response = self.authorized_client.get(
            "/api/v1/classif-ai/user-classification/%s/" % user_classification.id,
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 403)

    def test_delete_user_classif_defects(self):
        user_classification = UserClassification.objects.create(file=self.file, user=self.user)
        user_classification_id = user_classification.id
        response = self.authorized_client.delete(
            "/api/v1/classif-ai/user-classification/%s/" % user_classification_id,
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 204)
        self.assertEqual(UserClassification.objects.filter(id=user_classification_id).exists(), False)

    # TODO Add more test cases for bulk actions
    def user_classification_bulk_create(self):
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/bulk_create/",
            json.dumps(
                {
                    "is_no_defect": False,
                    "file_ids": [self.file.id, self.file_1.id],
                    "defects": [self.defect_1.id, self.defect_2.id],
                }
            ),
            content_type="application/json",
        )
        return response

    def test_bulk_create(self):
        response = self.user_classification_bulk_create()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(UserClassification.objects.all().count(), 2)
        self.assertEqual(UserClassificationDefect.objects.all().count(), 4)

        self.assertTrue(UserClassification.objects.filter(file=self.file, user=self.user).exists())
        classification = UserClassification.objects.get(file=self.file, user=self.user)
        self.assertEqual(UserClassificationDefect.objects.filter(classification=classification).count(), 2)
        user_classification_defects = UserClassificationDefect.objects.filter(
            defect__in=[self.defect_1.id, self.defect_2.id]
        )
        self.assertTrue(user_classification_defects.exists())
        # Add more test cases to cover various params like is_no_defect, or replace_existing_labels

    def test_bulk_replace(self):
        response = self.user_classification_bulk_create()
        self.assertEqual(response.status_code, 201)
        defect_3 = Defect.objects.create(name="defect-3", subscription=self.subscription)
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/bulk_replace/",
            json.dumps(
                {
                    "file_ids": [self.file.id, self.file_1.id],
                    "original_defect": self.defect_1.id,
                    "new_defect": defect_3.id,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserClassification.objects.all().count(), 2)
        self.assertEqual(UserClassificationDefect.objects.filter(defect=self.defect_1.id).count(), 0)
        self.assertEqual(UserClassificationDefect.objects.filter(defect=defect_3.id).count(), 2)

    def test_bulk_remove(self):
        self.user_classification_bulk_create()
        # ToDo: Add a test for remove all = True as well
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/bulk_remove/",
            json.dumps(
                {
                    "remove_all": False,
                    "file_ids": [self.file.id, self.file_1.id],
                    "defects": [self.defect_2.id],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserClassification.objects.all().count(), 2)
        self.assertEqual(UserClassificationDefect.objects.filter(defect=self.defect_1.id).count(), 2)
        self.assertEqual(UserClassificationDefect.objects.filter(defect=self.defect_2.id).count(), 0)

    def test_bulk_create_by_passing_another_use_case_defect(self):
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/bulk_create/",
            json.dumps(
                {
                    "is_no_defect": False,
                    "file_ids": [self.file.id],
                    "defects": [self.defect_1.id, self.single_label_defect.id],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_bulk_create_by_passing_single_use_case_success(self):
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/bulk_create/",
            json.dumps(
                {
                    "is_no_defect": False,
                    "file_ids": [self.single_label_file.id],
                    "defects": [self.single_label_defect.id],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(UserClassification.objects.all().count(), 1)
        self.assertEqual(UserClassificationDefect.objects.all().count(), 1)

    def test_bulk_create_by_passing_single_use_case(self):
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-classification/bulk_create/",
            json.dumps(
                {
                    "is_no_defect": False,
                    "file_ids": [self.single_label_file.id],
                    "defects": [self.defect_1.id, self.defect_2.id],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
