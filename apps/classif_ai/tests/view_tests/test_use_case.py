import json
from apps.classif_ai.models import Defect, UseCase, UseCaseDefect
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase


class UseCaseTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.defect_1 = Defect.objects.create(name="defect-1", subscription=cls.subscription)
        cls.defect_2 = Defect.objects.create(name="defect-2", subscription=cls.subscription)

    def setUp(self):
        super().setUp()
        self.defect_1 = self.__class__.defect_1
        self.defect_2 = self.__class__.defect_2

    def test_create_use_case(self):
        response = self.authorized_client.post(
            "/api/v1/classif-ai/use-case/",
            json.dumps(
                {
                    "name": "test-upload",
                    "type": "DETECTION",
                    "defects": [self.defect_1.id, self.defect_2.id],
                    "subscription": self.subscription.id,
                }
            ),
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 201)

        data = response.data
        # Check response data.
        self.assertEqual(data["name"], "test-upload")
        self.assertEqual(data["type"], "DETECTION")

        # Check related defects.
        self.assertEqual(len(data["defects"]), 2)

    def test_list_use_cases(self):
        response = self.authorized_client.get("/api/v1/classif-ai/use-case/")

        # Check status code.
        self.assertEqual(response.status_code, 200)

        # Check response data.
        data = response.data
        self.assertEqual(data["count"], 3)

    def test_update_use_case(self):
        use_case_id = UseCase.objects.first().id
        UseCaseDefect.objects.create(use_case_id=use_case_id, defect=self.defect_1)
        UseCaseDefect.objects.create(use_case_id=use_case_id, defect=self.defect_2)
        temp_defect = Defect.objects.create(name="temp-defect", subscription=self.subscription)

        response = self.authorized_client.patch(
            f"/api/v1/classif-ai/use-case/{use_case_id}/",
            json.dumps(
                {"name": "updated-usecase", "type": "CLASSIFICATION_AND_DETECTION", "defects": [temp_defect.id]}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

        response = self.authorized_client.patch(
            f"/api/v1/classif-ai/use-case/{use_case_id}/",
            json.dumps({"name": "updated-usecase", "defects": [temp_defect.id]}),
            content_type="application/json",
        )

        # Check status code.
        self.assertEqual(response.status_code, 200)

        use_case = UseCase.objects.first()

        # Check if name was updated.
        self.assertEqual(use_case.name, "updated-usecase")

        # Verify that type _wasn't_ updated.
        self.assertNotEqual(use_case.type, "CLASSIFICATION_AND_DETECTION")

        # Check if related defects was updated.
        self.assertEqual(response.data["defects"][0]["id"], temp_defect.id)
