from apps.classif_ai.models import MlModel
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from common.error_test_mixins.validation_error_test_mixin import ValidationErrorTestMixin


class MlModelTest(ValidationErrorTestMixin, ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super(MlModelTest, cls).setUpTestData()
        MlModel.objects.create(
            name="test-model",
            code="test-code",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.use_case,
            path={},
            training_performance_metrics={},
        )

    def setUp(self) -> None:
        super(MlModelTest, self).setUp()
        self.subscription = self.__class__.subscription
        self.use_case = self.__class__.use_case

    def test_field_validation(self):
        ml_model = MlModel(
            code=None,
            version=None,
            status=None,
            is_stable=False,
            subscription=None,
            use_case=None,
            path={},
            name=None,
            training_performance_metrics={},
        )
        with self.assertValidationErrors(["use_case", "status", "subscription", "version", "code", "name"]):
            ml_model.full_clean()

        with self.assertValidationErrors(["name"]):
            MlModel.objects.create(
                name="TEST-MODEL",
                code="test-code-1",
                version=2,
                status="deployed_in_prod",
                is_stable=True,
                subscription=self.subscription,
                use_case=self.use_case,
                path={},
                training_performance_metrics={},
            )

    def test_status_update(self):
        MlModel.objects.create(
            code="test-code-2",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=self.subscription,
            use_case=self.use_case,
            path={},
            name="test-model-2",
            training_performance_metrics={},
        )
        old_status = list(MlModel.objects.filter(code="test-code").values_list("status", flat=True))[0]
        self.assertEquals(old_status, "retired")

    def test_load_model(self):
        # ToDo: We should write the test cases that it's able to load the model here.
        #  Since the models are currently only available in the production GPU machine, this will fail everywhere else.
        #  So, we should somehow gracefully handle this. May be use some env variable to see if this is running on GPU
        #  machine or not.
        pass
