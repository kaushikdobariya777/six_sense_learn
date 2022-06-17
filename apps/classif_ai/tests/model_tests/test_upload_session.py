from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from sixsense.tenant_test_case import SixsenseTenantTestCase
from apps.classif_ai.models import UploadSession


class UploadSessionTest(SixsenseTenantTestCase, ValidationErrorTestMixin):
    def test_field_validation(self):
        upload_session = UploadSession(subscription=None, name=None)
        with self.assertValidationErrors(["subscription", "name"]):
            upload_session.full_clean()

        upload_session = UploadSession(subscription_id=0, name="")
        with self.assertValidationErrors(["subscription", "name"]):
            upload_session.full_clean()
