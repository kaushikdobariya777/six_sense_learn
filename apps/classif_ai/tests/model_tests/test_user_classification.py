from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import File, FileSet, UploadSession, UserClassification
from django.contrib.auth import get_user_model


class UserClassificationTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    # ToDo: Add more test cases. Especially for single and multi label constraints,
    #  trying to defects which doesn't belong to same use case, etc.
    @classmethod
    def setUpTestData(cls):
        super(UserClassificationTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.user = get_user_model().objects.create(email="a@a.com", is_superuser=True, is_staff=True)
        UserClassification.objects.create(file=cls.file, user=cls.user)

    def setUp(self) -> None:
        super(UserClassificationTest, self).setUp()
        self.file = self.__class__.file
        self.user = self.__class__.user

    def test_field_validation(self):
        user_classification = UserClassification(file=None, user=None)
        with self.assertValidationErrors(["file", "user"]):
            user_classification.full_clean()

        user_classification = UserClassification(file_id=0, user_id=0)
        with self.assertValidationErrors(["file", "user"]):
            user_classification.full_clean()

    def test_unique_together(self):
        user_classification = UserClassification(file=self.file, user=self.user)
        with self.asssertIntegrityErrors(["file", "user"]):
            user_classification.save()
