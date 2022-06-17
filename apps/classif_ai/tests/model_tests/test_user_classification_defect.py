from common.error_test_mixins.integerity_error_test_mixin import IntegrityErrorTestMixin
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import Defect, File, FileSet, UploadSession, UserClassification, UserClassificationDefect
from django.contrib.auth import get_user_model


class UserClassificationDefectTest(ClassifAiTestCase, ValidationErrorTestMixin, IntegrityErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(UserClassificationDefectTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")
        cls.user = get_user_model().objects.create(email="a@a.com", is_superuser=True, is_staff=True)
        cls.classification = UserClassification.objects.create(file=cls.file, user=cls.user)
        cls.defect = Defect.objects.create(name="test-defect", code="test-code", subscription=cls.subscription)
        UserClassificationDefect.objects.create(classification=cls.classification, defect=cls.defect)

    def setUp(self) -> None:
        super(UserClassificationDefectTest, self).setUp()
        self.classification = self.__class__.classification
        self.defect = self.__class__.defect

    def test_field_validation(self):
        user_classification_defect = UserClassificationDefect(classification=None, defect=None)
        with self.assertValidationErrors(["classification", "defect"]):
            user_classification_defect.full_clean()

        user_classification_defect = UserClassificationDefect(classification_id=0, defect_id=0)
        with self.assertValidationErrors(["classification", "defect"]):
            user_classification_defect.full_clean()

    def test_unique_together(self):
        user_classification_defect = UserClassificationDefect(classification=self.classification, defect=self.defect)
        with self.asssertIntegrityErrors(["classification", "defect"]):
            user_classification_defect.save()
