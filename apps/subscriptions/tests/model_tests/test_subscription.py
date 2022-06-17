from datetime import datetime, timedelta

from pytz import UTC
from sixsense.tenant_test_case import SixsenseTenantTestCase
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.subscriptions.models import Subscription
from apps.users.models import SubOrganization
from apps.packs.models import Pack


class SubscriptionTest(SixsenseTenantTestCase, ValidationErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(SubscriptionTest, cls).setUpTestData()
        cls.pack = Pack.objects.create()
        cls.sub_org = SubOrganization.objects.create(name="test_sub_org", code="test_code")

    def setUp(self) -> None:
        super(SubscriptionTest, self).setUp()
        self.pack = self.__class__.pack
        self.sub_org = self.__class__.sub_org
        self.fsmi = [
            {
                "field": "package",
                "name": "Package",
                "field_type": "CharField",
                "field_props": {"required": False, "max_length": 256},
            },
        ]
        self.starts_at = datetime.now(UTC)
        self.expires_at = self.starts_at + timedelta(days=10)

    def test_field_validation(self):
        subscription = Subscription()
        with self.assertValidationErrors(["pack", "sub_organization", "starts_at", "expires_at"]):
            subscription.full_clean()

    def test_create(self):
        Subscription.objects.create(
            pack=self.pack,
            sub_organization=self.sub_org,
            starts_at=self.starts_at,
            expires_at=self.expires_at,
            file_set_meta_info=self.fsmi,
        )
        self.assertEquals(Subscription.objects.all().count(), 1)

    def test_meta_info_valid_schema(self):
        invalid_fsmi = [
            {
                "field": "package",
                "field_props": {"required": False, "max_length": "256"},
                "associated_with_defects": "True",
            },
            {
                "name": "Inspected",
                "field_type": "InvalidField",
                "field_props": {"required": "False", "allowed_null": 100},
                "is_filterable": 100,
            },
            {
                "name": "YieldMin",
                "field_type": "CharField",
                "invalid_key_name": {
                    "invalid_key_required": False,
                },
            },
        ]
        subscription = Subscription(
            pack=self.pack,
            sub_organization=self.sub_org,
            starts_at=self.starts_at,
            expires_at=self.expires_at,
            file_set_meta_info=invalid_fsmi,
        )
        with self.assertValidationErrors(["file_set_meta_info"]):
            subscription.full_clean()

    def test_valid_starts_expires(self):
        invalid_expiry = self.starts_at - timedelta(days=10)
        subscription = Subscription(
            pack=self.pack,
            sub_organization=self.sub_org,
            starts_at=self.starts_at,
            expires_at=invalid_expiry,
            file_set_meta_info=self.fsmi,
        )
        with self.assertValidationErrors(["starts_at", "expires_at"]):
            subscription.full_clean()
