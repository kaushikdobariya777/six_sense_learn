import tempfile

import requests
from common.services import S3Service
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.models import File, FileSet, UploadSession


class FileTest(ClassifAiTestCase, ValidationErrorTestMixin):
    @classmethod
    def setUpTestData(cls):
        super(FileTest, cls).setUpTestData()
        cls.upload_session = UploadSession.objects.create(
            name="test-session", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.file_set = FileSet.objects.create(
            upload_session=cls.upload_session, subscription=cls.subscription, meta_info={"tray_id": "abcd"}
        )
        cls.file = File.objects.create(file_set=cls.file_set, name="test-file-name", path="test/test-path")

    def setUp(self) -> None:
        super(FileTest, self).setUp()
        self.upload_session = self.__class__.upload_session
        self.file_set = self.__class__.file_set
        self.file = self.__class__.file

    def test_field_validation(self):
        file = File(file_set=None, name=None, path=None)
        with self.assertValidationErrors(["file_set"]):
            file.full_clean()

        file = File(file_set_id=0, name="", path="")
        with self.assertValidationErrors(["file_set"]):
            file.full_clean()

    def test_null_path(self):
        file = File.objects.create(file_set=self.file_set, name="test-file-name", path=None)
        self.assertIsNotNone(file.path)

    # def upload_with_pre_signed_post_data(self):
    # self.assertIsNotNone(self.file.get_pre_signed_post_data())
    # s3_service = S3Service()
    # data = s3_service.generate_pre_signed_post(self.file.path)
    # fields = {key: val for key, val in data['fields'].items()}
    # temp_file = tempfile.NamedTemporaryFile()
    # with open(temp_file.name, 'w'):
    # temp_file.write(b'a')
    # r = requests.post(data['url'], files={**fields, 'file': open(temp_file.name, 'rb')})
    # self.assertEqual(r.status_code, 204)
    # temp_file.close()


#
# def delete_file(self):
# self.file.delete()
# s3_service = S3Service()
# self.assertFalse(s3_service.check_if_key_exists(self.file.path))
#
# def read_with_pre_signed_url(self):
# url = self.file.get_pre_signed_url()
# self.assertIsNotNone(url)
# r = requests.get(url)
# self.assertEqual(r.status_code, 200)
#
# def _s3_operations(self):
# operations = ['upload_with_pre_signed_post_data', 'read_with_pre_signed_url', 'delete_file']
# for op in operations:
# yield op, getattr(self, op)
#
# def test_s3_operations(self):
# for name, op in self._s3_operations():
# try:
# op()
# except Exception as e:
# self.fail("{} failed ({}: {})".format(name, type(e), e))
