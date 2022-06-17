from apps.classif_ai.models import FileRegion, FileRegionHistory
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase


class FileRegionTest(ClassifAiTestCase, ValidationErrorTestMixin):
    def test_field_validation(self):
        file_region = FileRegion(file=None, ml_model=None, defects={1: {}}, region={"x": {}})
        # ToDo: Validate the region _as well_
        with self.assertValidationErrors(["file", "ml_model"]):
            file_region.full_clean()

        file_region = FileRegion(file_id=0, ml_model_id=0, defects={1: {}}, region={"x": {}})
        with self.assertValidationErrors(["file", "ml_model"]):
            file_region.full_clean()


class FileRegionHistoryTest(ClassifAiTestCase, ValidationErrorTestMixin):
    def test_field_validation(self):
        file_region_history = FileRegionHistory(
            file=None,
            ml_model=None,
            defects={1: {}},
            region={"x": {}},
            file_region=None,
            ai_region=None,
            is_user_feedback=False,
            is_deleted=False,
        )
        with self.assertValidationErrors(["file", "ml_model", "file_region", "ai_region"]):
            file_region_history.full_clean()

        file_region_history = FileRegionHistory(
            file_id=0,
            ml_model_id=0,
            defects={1: {}},
            region={"x": {}},
            file_region_id=0,
            ai_region_id=None,
            is_user_feedback=False,
            is_deleted=False,
        )
        with self.assertValidationErrors(["file", "ml_model", "file_region", "ai_region"]):
            file_region_history.full_clean()
