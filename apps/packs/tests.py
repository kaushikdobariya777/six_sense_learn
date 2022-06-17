from rest_framework import status
from common.sixsense_test import CommonTest


class PackTest(CommonTest):
    """Test module for Packs model"""

    def test_pack_list(self):
        # testing for org_id 1
        res = self.authorized_client.get("/api/v1/packs/?sub_organization_id=1", format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEquals(2, res.data.get("count"))
        # checking for inner data
        self.assertEquals("model1", res.data.get("results")[0].get("name"))
        self.assertEquals(False, res.data.get("results")[0].get("is_demo"))
        self.assertEquals("Public", res.data.get("results")[0].get("type"))

        self.assertEquals("model2", res.data.get("results")[1].get("name"))
        self.assertEquals(True, res.data.get("results")[1].get("is_demo"))
        self.assertEquals("Public", res.data.get("results")[1].get("type"))

        # testing for org_id 2
        res = self.authorized_client.get("/api/v1/packs/?sub_organization_id=2", format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEquals(2, res.data.get("count"))

        # checking for internal data
        self.assertEquals("model2", res.data.get("results")[0].get("name"))
        self.assertEquals(True, res.data.get("results")[0].get("is_demo"))
        self.assertEquals("Public", res.data.get("results")[0].get("type"))

        self.assertEquals("model3", res.data.get("results")[1].get("name"))
        self.assertEquals(False, res.data.get("results")[1].get("is_demo"))
        self.assertEquals("Public", res.data.get("results")[1].get("type"))
