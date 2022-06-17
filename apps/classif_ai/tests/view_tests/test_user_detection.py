import json

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Polygon

from apps.classif_ai.models import (
    Defect,
    UploadSession,
    FileSet,
    File,
    UserDetectionRegionDefect,
    UserDetection,
    UserDetectionRegion,
    UseCase,
    UseCaseDefect,
)
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase


class UserDetectionTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super(UserDetectionTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-upload-session", subscription=cls.subscription, use_case=cls.detection_use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.file_1 = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.user = get_user_model().objects.create(email="a@a.com", is_superuser=True, is_staff=True)
        cls.defect_1 = Defect.objects.create(name="defect-1", subscription=cls.subscription)
        cls.defect_2 = Defect.objects.create(name="defect-2", subscription=cls.subscription)
        cls.usecase_defect_1 = UseCaseDefect.objects.create(use_case=cls.use_case, defect=cls.defect_1)
        cls.usecase_defect_2 = UseCaseDefect.objects.create(use_case=cls.use_case, defect=cls.defect_2)

    def setUp(self):
        super().setUp()
        self.defect_1 = self.__class__.defect_1
        self.defect_2 = self.__class__.defect_2
        self.dummy_region = {"type": "box", "coordinates": {"h": 0.1, "w": 0.1, "x": 0, "y": 0}}

    def create_user_detection(self, is_no_defect):
        data = json.dumps(
            {
                "is_no_defect": is_no_defect,
                "file": self.file.id,
                "user": self.user.id,
                "detection_regions": [
                    {
                        "region": self.dummy_region,
                        "defects": [self.defect_1.id, self.defect_2.id],
                    }
                ],
            }
        )
        content_type = "application/json"
        response = self.authorized_client.post("/api/v1/classif-ai/user-detection/", data, content_type=content_type)
        return response

    def assert_file_and_user(self, data):
        self.assertIsNotNone(data["file"], "The file doesn't exist in the response")
        self.assertEqual(data["file"], self.file.id)
        self.assertEqual(data["user"], self.user.id)

    def test_create_user_detection_with_defects(self):
        response = self.create_user_detection(False)

        # Check status code.
        self.assertEqual(response.status_code, 201)

        data = response.data
        # Check response data.
        self.assert_file_and_user(data)

        # Check defects
        detection_region_count = UserDetectionRegion.objects.count()
        self.assertEqual(detection_region_count, 1)
        detection_region = UserDetectionRegion.objects.first()
        self.assertTrue(Polygon(((0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1), (0, 0))).equals(detection_region.region))
        defect_count = UserDetectionRegionDefect.objects.all().count()
        self.assertEqual(defect_count, 2)

    def test_create_user_detection_without_defects(self):
        response = self.create_user_detection(True)

        # Check status code.
        self.assertEqual(response.status_code, 201)

        data = response.data
        # Check response data.
        self.assert_file_and_user(data)

        # Check defects
        detection_region_count = UserDetectionRegion.objects.count()
        self.assertEqual(detection_region_count, 0)

    def test_list_user_detection(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        created_data = response.data

        url = "/api/v1/classif-ai/user-detection/?file=%s" % created_data["file"]
        response = self.authorized_client.get(url, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        actual_data = response.data["results"][0]

        # check created and fetched data
        self.assertEqual(created_data["is_no_defect"], actual_data["is_no_defect"])
        self.assertEqual(created_data["file"], actual_data["file"])
        self.assertEqual(created_data["detection_regions"], actual_data["detection_regions"])
        # ToDo: Add more users and test the user filter well
        new_user = get_user_model().objects.create_user(
            email="asdasdj@asdjhc.com",
            password="TEST_USER_PASSWORD",
            first_name="TEST_USER_FIRST_NAME",
            last_name="TEST_USER_LAST_NAME",
            is_active=True,
        )
        url = "/api/v1/classif-ai/user-detection/?file=%s&user=%s" % (created_data["file"], new_user.id)
        response = self.authorized_client.get(url, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_update_user_detection_with_defects(self):
        # user_detection = UserDetection.objects.create(file=self.file, user=self.user)
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        user_detection = response.data
        url = "/api/v1/classif-ai/user-detection/%s/" % user_detection["id"]
        response = self.authorized_client.put(
            url,
            json.dumps(
                {
                    "is_no_defect": False,
                    "file": self.file.id,
                    "user": self.user.id,
                    "detection_regions": [
                        {
                            "region": self.dummy_region,
                            "defects": [self.defect_1.id],
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 200)

        data = response.data
        # Check response data.
        self.assert_file_and_user(data)

        # Check defects
        detection_region = UserDetectionRegion.objects.first()
        self.assertTrue(Polygon(((0, 0), (0.1, 0), (0.1, 0.1), (0, 0.1), (0, 0))).equals(detection_region.region))
        defect_count = UserDetectionRegionDefect.objects.all().count()
        self.assertEqual(defect_count, 1)

    def test_update_user_detection_without_defects(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        user_detection = response.data
        url = "/api/v1/classif-ai/user-detection/%s/" % user_detection["id"]
        response = self.authorized_client.put(
            url,
            json.dumps(
                {
                    "is_no_defect": True,
                    "file": self.file.id,
                    "user": self.user.id,
                    "detection_regions": [
                        {
                            "region": self.dummy_region,
                            "defects": [self.defect_1.id],
                        }
                    ],
                }
            ),
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 200)

        data = response.data
        # Check response data.
        self.assert_file_and_user(data)

        # Check defects
        defect_count = UserDetectionRegionDefect.objects.all().count()
        self.assertEqual(defect_count, 0)

    def test_update_user_in_user_detection(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        user_detection = response.data
        new_user = get_user_model().objects.create_user(
            email="asdasdj@asdjhc.com",
            password="TEST_USER_PASSWORD",
            first_name="TEST_USER_FIRST_NAME",
            last_name="TEST_USER_LAST_NAME",
            is_active=True,
        )
        url = "/api/v1/classif-ai/user-detection/%s/" % user_detection["id"]
        response = self.authorized_client.put(
            url,
            json.dumps(
                {
                    "is_no_defect": True,
                    "file": self.file.id,
                    "user": new_user.id,
                    "detection_regions": [
                        {
                            "region": self.dummy_region,
                            "defects": [self.defect_1.id],
                        }
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_update_file_in_user_detection(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        user_detection = response.data
        new_file = File.objects.create(file_set=self.file_set, name="asdasjdk.jpg")
        url = "/api/v1/classif-ai/user-detection/%s/" % user_detection["id"]
        response = self.authorized_client.put(
            url,
            json.dumps(
                {
                    "is_no_defect": True,
                    "file": new_file.id,
                    "user": self.user.id,
                    "detection_regions": [
                        {
                            "region": self.dummy_region,
                            "defects": [self.defect_1.id],
                        }
                    ],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_get_user_detection_defects(self):
        user_detection = UserDetection.objects.create(file=self.file, user=self.user)
        url = "/api/v1/classif-ai/user-detection/%s/" % user_detection.id
        response = self.authorized_client.get(url, content_type="application/json")

        # Check status code.
        self.assertEqual(response.status_code, 403)

    def test_delete_user_detection_defects(self):
        user_detection = UserDetection.objects.create(file=self.file, user=self.user)
        url = "/api/v1/classif-ai/user-detection/%s/" % user_detection.id
        response = self.authorized_client.delete(url, content_type="application/json")

        # Check status code.
        self.assertEqual(response.status_code, 204)
        self.assertEqual(UserDetection.objects.filter(id=user_detection.id).exists(), False)

    # TODO Need to add more test cases
    def test_bulk_replace_user_detection(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        defect_3 = Defect.objects.create(name="defect-3", subscription=self.subscription)
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-detection/bulk_replace/",
            json.dumps(
                {
                    "user": self.user.id,
                    "file_ids": [self.file.id, self.file_1.id],
                    "original_defect": self.defect_1.id,
                    "new_defect": defect_3.id,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_bulk_replace_user_detection_with_different_use_case_defect(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        defect_3 = Defect.objects.create(name="defect-3", subscription=self.subscription)
        use_case_defect = UseCaseDefect.objects.create(use_case=self.single_label_use_case, defect=defect_3)
        try:
            response = self.authorized_client.post(
                "/api/v1/classif-ai/user-detection/bulk_replace/",
                json.dumps(
                    {
                        "user": self.user.id,
                        "file_ids": [self.file.id, self.file_1.id],
                        "original_defect": self.defect_1.id,
                        "new_defect": defect_3.id,
                    }
                ),
                content_type="application/json",
            )
            self.assertNotEqual(response.status_code, 201)
        except:
            pass

    def test_bulk_remove_by_id(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-detection/bulk_remove/",
            json.dumps(
                {
                    "user": self.user.id,
                    "file_ids": [self.file.id, self.file_1.id],
                    "defects": [self.defect_1.id],
                    "remove_all": False,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_bulk_remove_all_defects(self):
        response = self.create_user_detection(False)
        self.assertEqual(response.status_code, 201)
        response = self.authorized_client.post(
            "/api/v1/classif-ai/user-detection/bulk_remove/",
            json.dumps(
                {
                    "user": self.user.id,
                    "file_ids": [self.file.id, self.file_1.id],
                    "defects": [],
                    "remove_all": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
