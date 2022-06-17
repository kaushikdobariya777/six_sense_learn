import json
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import Tag, WaferMap, WaferMapTag


class WaferMapViewSetTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        tag_1 = Tag.objects.create(name="test-tag-1", description="test tag")
        wafer_map_1 = WaferMap.objects.create(organization_wafer_id="test-wafer-map-1", meta_data={})
        wafer_map_tag_1 = WaferMapTag.objects.create(wafer=wafer_map_1, tag=tag_1)

    def test_add_wafer_map_tag(self):
        tag = Tag.objects.create(name="test-tag-temp")
        wafer_map = WaferMap.objects.get(id=1)
        self.assertEquals(bool(tag in wafer_map.tags.all()), False)

        response = self.authorized_client.put(
            "/api/v1/classif-ai/wafer-map/tags/?id__in=1",
            json.dumps({"tag_ids": [tag.id]}),
            content_type="application/json",
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check whether tag was added or not
        self.assertEquals(bool(tag in wafer_map.tags.all()), True)

    def test_remove_wafer_map_tag(self):
        tag = Tag.objects.create(name="test-tag-temp")
        wafer_map = WaferMap.objects.get(id=1)
        wafer_map.tags.add(tag)
        self.assertEquals(bool(tag in wafer_map.tags.all()), True)

        response = self.authorized_client.delete(
            "/api/v1/classif-ai/wafer-map/tags/?id__in=1",
            json.dumps({"tag_ids": [tag.id]}),
            content_type="application/json",
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check whether tag was removed or not
        self.assertEquals(bool(tag in wafer_map.tags.all()), False)

        # test for remove all
        response = self.authorized_client.delete(
            "/api/v1/classif-ai/wafer-map/tags/?id__in=1",
            json.dumps({"remove_all_tags": True}),
            content_type="application/json",
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        self.assertEquals(WaferMapTag.objects.filter(wafer=wafer_map).count(), 0)
