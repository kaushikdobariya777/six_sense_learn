import boto3
import pytz
from moto import mock_s3

from apps.classif_ai.models import UseCase
from datetime import datetime, timedelta
from apps.subscriptions.models import Subscription
from apps.users.models import SubOrganization
from apps.packs.models import Pack
from sixsense.settings import AWS_STORAGE_BUCKET_NAME
from sixsense.tenant_test_case import SixsenseTenantTestCase


@mock_s3
class ClassifAiTestCase(SixsenseTenantTestCase):
    @classmethod
    def setUpTestData(cls):
        super(ClassifAiTestCase, cls).setUpTestData()
        # ToDo: Use fixtures instead.
        file_set_meta_info = [
            {
                "name": "Tray id",
                "field": "tray_id",
                "field_type": "CharField",
                "field_props": {"required": True, "allow_null": True, "max_length": 256},
                "is_filterable": True,
            },
            {"name": "Pass", "field": "Pass", "field_type": "IntegerField", "field_props": {"required": False}},
            {
                "name": "Row and col id",
                "field": "row_and_col_id",
                "field_type": "CharField",
                "field_props": {"required": False, "max_length": 256},
            },
            {
                "name": "StartDate",
                "field": "StartDate",
                "field_type": "DateTimeField",
                "field_props": {"required": False},
            },
        ]
        pack = Pack.objects.create()
        sub_org = SubOrganization.objects.create(name="test_sub_org", code="tes_code")
        starts_at = datetime.now(pytz.UTC)
        expires_at = starts_at + timedelta(days=10)
        subscription = Subscription.objects.create(
            pack=pack,
            sub_organization=sub_org,
            starts_at=starts_at,
            expires_at=expires_at,
            file_set_meta_info=file_set_meta_info,
        )
        cls.subscription = subscription
        use_case = UseCase.objects.create(
            name="test-usecase", type="CLASSIFICATION", subscription=subscription, classification_type="MULTI_LABEL"
        )
        single_label_use_case = UseCase.objects.create(
            name="single-label-test-usecase",
            type="CLASSIFICATION",
            subscription=subscription,
            classification_type="SINGLE_LABEL",
        )
        use_case_detection = UseCase.objects.create(
            name="test-detection-usecase",
            type="CLASSIFICATION_AND_DETECTION",
            subscription=cls.subscription,
            classification_type="MULTI_LABEL",
        )
        cls.use_case = use_case
        cls.detection_use_case = use_case_detection
        cls.single_label_use_case = single_label_use_case

    def setUp(self):
        super(ClassifAiTestCase, self).setUp()
        conn = boto3.resource("s3", region_name="us-east-1")
        # We need to create the bucket since this is all in Moto's 'virtual' AWS account
        conn.create_bucket(Bucket=AWS_STORAGE_BUCKET_NAME)
