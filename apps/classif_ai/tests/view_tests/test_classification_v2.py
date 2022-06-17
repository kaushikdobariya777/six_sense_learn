from apps.classif_ai.models import (
    Defect,
    File,
    FileSet,
    GTClassification,
    GTClassificationDefect,
    MlModel,
    ModelClassification,
    ModelClassificationDefect,
    TrainingSession,
    TrainingSessionFileSet,
    UploadSession,
    UseCase,
    WaferMap,
)
from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase


class ClassificationV2Test(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Since we have file_level_metrics, timeseries_metrics, defect_distribution etc, we need to
        # have some extra cases
        cls.single_label_use_case.automation_conditions = {"threshold_percentage": 60}
        cls.single_label_use_case.save()

        # use_case - model - wafer - folder - file - file_created - gt_defect - model_defect, confidence (N means null, confidence_threshold=0.95, wafer_threshold=0.6)
        # 2 - 1 - 1 - 1 - 1 - 2020-10-11 - 1 - 1 - 0.96 : total=1, auto_classified=1, accurate=1, gt_defects={1= total=1,auto=1,accu=1} : confident and matched
        # 2 - 1 - 1 - 2 - 2 - 2020-10-12 - 2 - 3 - 0.96 : total=2, auto_classified=2, accurate=1, gt_defects={1= 1-1-1, 2= 1-1-0} : confident but no match
        # 2 - 1 - 1 - 2 - 3 - 2020-10-13 - 3 - 2 - 0.96 : total=3, auto_classified=3, accurate=1, gt_defects={1= 1-1-1, 2= 1-1-0, 3= 1-1-0} : confident but no match
        # 2 - 1 - 1 - 1 - 4 - 2020-10-14 - 4 - N - N    : total=4, auto_classified=3, accurate=1, gt_defects={1= 1-1-1, 2= 1-1-0, 3= 1-1-0, 4= 1-0-0} : no model defect
        # 2 - 1 - 1 - 1 - 5 - 2020-10-15 - N - 5 - 0.96 : total=5, auto_classified=4, accurate=1, gt_defects={1= 1-1-1, 2= 1-1-0, 3= 1-1-0, 4= 1-0-0} : no gt defect
        # 2 - 1 - 1 - 1 - 6 - 2020-10-16 - 1 - 1 - 0.16 : total=6, auto_classified=4, accurate=1, gt_defects={1= 2-1-1, 2= 1-1-0, 3= 1-1-0, 4= 1-0-0} : not confident so no point being accurate
        # 2 - 1 - 1 - 1 - 7 - 1900-10-17 - 1 - 1 - 0.96 : total=6, auto_classified=4, accurate=1, gt_defects={1= 2-1-1, 2= 1-1-0, 3= 1-1-0, 4= 1-0-0} : file's created date is not in the range, year 1900
        # 2 - 1 - 2 - 1 - 8 - 2020-10-16 - 1 - 1 - 0.96 : total=7, auto_classified=5, accurate=2, gt_defects={1= 3-2-2, 2= 1-1-0, 3= 1-1-0, 4= 1-0-0} : confident and matched, wafer-2
        # 2 - 1 - 1 - 1 - 9 - 2020-10-19 - N - N - N    : total=8, auto_classified=5, accurate=2, gt_defects={1= 3-2-2, 2= 1-1-0, 3= 1-1-0, 4= 1-0-0} : no gt_defect and model_defect

        # 2 - 1 - N -10 - 2030-10-11 - 1 - 1 - 0.96 : total=7, auto_classified=5, accurate=3 : wafer is Null
        # 2 - 1 - 1 -11 - 2030-10-11 - 1 - 1 - 0.96 : total=8, auto_classified=6, accurate=4 : file_set.use_case is Null, but upload_session.use_case not Null

        cls.ml_model_1 = MlModel.objects.create(
            name="test-model-1",
            code="test-code-1",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.single_label_use_case,
            confidence_threshold="0.96",
        )
        cls.upload_session_1 = UploadSession.objects.create(
            name="test-session-1",
            subscription=cls.subscription,
            use_case=cls.single_label_use_case,
            is_bookmarked=True,
        )
        cls.upload_session_2 = UploadSession.objects.create(
            name="test-session-2", subscription=cls.subscription, use_case=cls.single_label_use_case
        )

        cls.defect_1 = Defect.objects.create(name="test-defect-1", code="test-code-1", subscription=cls.subscription)
        cls.defect_2 = Defect.objects.create(name="test-defect-2", code="test-code-2", subscription=cls.subscription)
        cls.defect_3 = Defect.objects.create(name="test-defect-3", code="test-code-3", subscription=cls.subscription)
        cls.defect_4 = Defect.objects.create(name="test-defect-4", code="test-code-4", subscription=cls.subscription)
        cls.defect_5 = Defect.objects.create(name="test-defect-5", code="test-code-5", subscription=cls.subscription)

        cls.wafer_map_1 = WaferMap.objects.create(organization_wafer_id="charfiled-1")
        cls.wafer_map_2 = WaferMap.objects.create(organization_wafer_id="charfiled-2")

        cls.file_set_1 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_2 = FileSet.objects.create(
            upload_session=cls.upload_session_2,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_3 = FileSet.objects.create(
            upload_session=cls.upload_session_2,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_4 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_5 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_6 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_7 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd1"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_8 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd1"},
            wafer=cls.wafer_map_2,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_9 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )
        cls.file_set_10 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            use_case=cls.single_label_use_case,
        )
        cls.file_set_11 = FileSet.objects.create(
            upload_session=cls.upload_session_1,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
        )

        # not able to pass created ts directly while creation :(
        cls.file_1 = File.objects.create(file_set=cls.file_set_1, name="test-file-name-1", path="test/test-path-1")
        cls.file_1.created_ts = "2020-10-11 00:00:00+00:00"
        cls.file_1.save()
        cls.file_set_1.created_ts = "2020-10-11 00:00:00+00:00"
        cls.file_set_1.save()

        cls.file_2 = File.objects.create(file_set=cls.file_set_2, name="test-file-name-2", path="test/test-path-2")
        cls.file_2.created_ts = "2020-10-12 00:00:00+00:00"
        cls.file_2.save()
        cls.file_set_2.created_ts = "2020-10-12 00:00:00+00:00"
        cls.file_set_2.save()

        cls.file_3 = File.objects.create(file_set=cls.file_set_3, name="test-file-name-3", path="test/test-path-3")
        cls.file_3.created_ts = "2020-10-13 00:00:00+00:00"
        cls.file_3.save()
        cls.file_set_3.created_ts = "2020-10-13 00:00:00+00:00"
        cls.file_set_3.save()

        cls.file_4 = File.objects.create(file_set=cls.file_set_4, name="test-file-name-4", path="test/test-path-4")
        cls.file_4.created_ts = "2020-10-14 00:00:00+00:00"
        cls.file_4.save()
        cls.file_set_4.created_ts = "2020-10-14 00:00:00+00:00"
        cls.file_set_4.save()

        cls.file_5 = File.objects.create(file_set=cls.file_set_5, name="test-file-name-5", path="test/test-path-5")
        cls.file_5.created_ts = "2020-10-15 00:00:00+00:00"
        cls.file_5.save()
        cls.file_set_5.created_ts = "2020-10-15 00:00:00+00:00"
        cls.file_set_5.save()

        cls.file_6 = File.objects.create(file_set=cls.file_set_6, name="test-file-name-6", path="test/test-path-6")
        cls.file_6.created_ts = "2020-10-16 00:00:00+00:00"
        cls.file_6.save()
        cls.file_set_6.created_ts = "2020-10-16 00:00:00+00:00"
        cls.file_set_6.save()

        cls.file_7 = File.objects.create(file_set=cls.file_set_7, name="test-file-name-7", path="test/test-path-7")
        cls.file_7.created_ts = "1900-10-17 00:00:00+00:00"
        cls.file_7.save()
        cls.file_set_7.created_ts = "1900-10-17 00:00:00+00:00"
        cls.file_set_7.save()

        cls.file_8 = File.objects.create(file_set=cls.file_set_8, name="test-file-name-8", path="test/test-path-8")
        cls.file_8.created_ts = "2020-10-18 00:00:00+00:00"
        cls.file_8.save()
        cls.file_set_8.created_ts = "2020-10-18 00:00:00+00:00"
        cls.file_set_8.save()

        cls.file_9 = File.objects.create(file_set=cls.file_set_9, name="test-file-name-9", path="test/test-path-9")
        cls.file_9.created_ts = "2020-10-19 00:00:00+00:00"
        cls.file_9.save()
        cls.file_set_9.created_ts = "2020-10-19 00:00:00+00:00"
        cls.file_set_9.save()

        cls.file_10 = File.objects.create(file_set=cls.file_set_10, name="test-file-name-10", path="test/test-path-10")
        cls.file_10.created_ts = "2030-10-11 00:00:00+00:00"
        cls.file_10.save()
        cls.file_set_10.created_ts = "2030-10-11 00:00:00+00:00"
        cls.file_set_10.save()

        cls.file_11 = File.objects.create(file_set=cls.file_set_11, name="test-file-name-11", path="test/test-path-11")
        cls.file_11.created_ts = "2030-10-11 00:00:00+00:00"
        cls.file_11.save()
        cls.file_set_11.created_ts = "2030-10-11 00:00:00+00:00"
        cls.file_set_11.save()

        cls.training_session_1 = TrainingSession.objects.create(new_ml_model=cls.ml_model_1)
        cls.training_session_fileset_1 = TrainingSessionFileSet.objects.create(
            file_set=cls.file_set_1,
            training_session=cls.training_session_1,
            dataset_train_type="TRAIN",
            defects={1: {}},
        )

        cls.gt_classification_1 = GTClassification.objects.create(file=cls.file_1)
        cls.gt_classification_2 = GTClassification.objects.create(file=cls.file_2)
        cls.gt_classification_3 = GTClassification.objects.create(file=cls.file_3)
        cls.gt_classification_4 = GTClassification.objects.create(file=cls.file_4)
        cls.gt_classification_5 = GTClassification.objects.create(file=cls.file_5)
        cls.gt_classification_6 = GTClassification.objects.create(file=cls.file_6)
        cls.gt_classification_7 = GTClassification.objects.create(file=cls.file_7)
        cls.gt_classification_8 = GTClassification.objects.create(file=cls.file_8)
        cls.gt_classification_9 = GTClassification.objects.create(file=cls.file_9)
        cls.gt_classification_10 = GTClassification.objects.create(file=cls.file_10)
        cls.gt_classification_11 = GTClassification.objects.create(file=cls.file_11)

        cls.gt_classification_defect_1 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_1, defect=cls.defect_1
        )
        cls.gt_classification_defect_2 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_2, defect=cls.defect_2
        )
        cls.gt_classification_defect_3 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_3, defect=cls.defect_3
        )
        cls.gt_classification_defect_4 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_4, defect=cls.defect_4
        )
        cls.gt_classification_defect_6 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_6, defect=cls.defect_1
        )
        cls.gt_classification_defect_7 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_7, defect=cls.defect_1
        )
        cls.gt_classification_defect_8 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_8, defect=cls.defect_1
        )
        cls.gt_classification_defect_9 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_10, defect=cls.defect_1
        )
        cls.gt_classification_defect_10 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_11, defect=cls.defect_1
        )

        cls.model_classification_1 = ModelClassification.objects.create(file=cls.file_1, ml_model=cls.ml_model_1)
        cls.model_classification_2 = ModelClassification.objects.create(file=cls.file_2, ml_model=cls.ml_model_1)
        cls.model_classification_3 = ModelClassification.objects.create(file=cls.file_3, ml_model=cls.ml_model_1)
        cls.model_classification_4 = ModelClassification.objects.create(file=cls.file_4, ml_model=cls.ml_model_1)
        cls.model_classification_5 = ModelClassification.objects.create(file=cls.file_5, ml_model=cls.ml_model_1)
        cls.model_classification_6 = ModelClassification.objects.create(file=cls.file_6, ml_model=cls.ml_model_1)
        cls.model_classification_7 = ModelClassification.objects.create(file=cls.file_7, ml_model=cls.ml_model_1)
        cls.model_classification_8 = ModelClassification.objects.create(file=cls.file_8, ml_model=cls.ml_model_1)
        cls.model_classification_10 = ModelClassification.objects.create(file=cls.file_9, ml_model=cls.ml_model_1)
        cls.model_classification_11 = ModelClassification.objects.create(file=cls.file_10, ml_model=cls.ml_model_1)
        cls.model_classification_12 = ModelClassification.objects.create(file=cls.file_11, ml_model=cls.ml_model_1)

        cls.model_classification_defect_1 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_1, defect=cls.defect_1, confidence=0.96
        )
        cls.model_classification_defect_2 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_2, defect=cls.defect_3, confidence=0.96
        )
        cls.model_classification_defect_3 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_3, defect=cls.defect_2, confidence=0.96
        )
        cls.model_classification_defect_5 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_5, defect=cls.defect_5, confidence=0.96
        )
        cls.model_classification_defect_6 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_6, defect=cls.defect_1, confidence=0.16
        )
        cls.model_classification_defect_7 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_7, defect=cls.defect_1, confidence=0.96
        )
        cls.model_classification_defect_8 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_8, defect=cls.defect_1, confidence=0.96
        )
        cls.model_classification_defect_10 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_11, defect=cls.defect_1, confidence=0.96
        )
        cls.model_classification_defect_11 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_12, defect=cls.defect_1, confidence=0.96
        )

    def test_distribution_metrics_use_case(self):

        url = "/api/v1/classif-ai/classification/metrics/distribution/use_case_level/?unit=xyz&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("this unit is not accepted", str(response.data[0]))

        # unit is file
        url = "/api/v1/classif-ai/classification/metrics/distribution/use_case_level/?unit=file&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, len(response.data))
        self.assertEquals("single-label-test-usecase", response.data[0]["use_case_name"])
        self.assertEquals("test-model-1", response.data[0]["ml_model_name"])
        self.assertEquals(8, response.data[0]["total"])
        self.assertEquals(5, response.data[0]["auto_classified"])
        self.assertEquals(3, response.data[0]["manual"])
        self.assertEquals(62, response.data[0]["auto_classified_percentage"])
        self.assertEquals(5, response.data[0]["audited"])
        self.assertEquals(2, response.data[0]["accurate"])
        self.assertEquals(3, response.data[0]["inaccurate"])
        self.assertEquals(40, response.data[0]["accuracy_percentage"])

        # unit is wafer
        url = "/api/v1/classif-ai/classification/metrics/distribution/use_case_level/?unit=wafer&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, len(response.data))
        self.assertEquals("single-label-test-usecase", response.data[0]["use_case_name"])
        self.assertEquals("test-model-1", response.data[0]["ml_model_name"])
        self.assertEquals(2, response.data[0]["total"])
        self.assertEquals(1, response.data[0]["auto_classified"])
        self.assertEquals(1, response.data[0]["manual"])
        self.assertEquals(50, response.data[0]["auto_classified_percentage"])
        self.assertEquals(8, response.data[0]["total_files"])
        self.assertEquals(5, response.data[0]["audited_files"])
        self.assertEquals(2, response.data[0]["accurate_files"])
        self.assertEquals(3, response.data[0]["inaccurate_files"])
        self.assertEquals(40, response.data[0]["accuracy_percentage_files"])

    def test_distribution_metrics_folder_level(self):

        url = "/api/v1/classif-ai/classification/metrics/distribution/folder_level/?date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(2, len(response.data))

        for row in response.data:
            if row["upload_session_name"] == "test-session-1":
                self.assertEquals("test-session-1", row["upload_session_name"])
                self.assertEquals(6, row["total"])
                self.assertEquals(3, row["auto_classified"])
                self.assertEquals(3, row["manual"])
                self.assertEquals(50, row["auto_classified_percentage"])
                self.assertEquals(3, row["audited"])
                self.assertEquals(2, row["accurate"])
                self.assertEquals(1, row["inaccurate"])
                self.assertEquals(67, row["accuracy_percentage"])

    # def test_distribution_metrics_defect_level(self):

    #     url = "/api/v1/classif-ai/classification/metrics/distribution/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01"
    #     response = self.authorized_client.get(url)

    #     self.assertEquals(200, response.status_code)
    #     self.assertEquals(4, len(response.data))

    #     for row in response.data:
    #         if row.get("gt_defect_id") == 2:
    #             self.assertEquals(1, row["total"])
    #             self.assertEquals(1, row["auto_classified"])
    #             self.assertEquals(0, row["manual"])
    #             self.assertEquals(100, row["auto_classified_percentage"])
    #             self.assertEquals(0, row["accurate"])
    #             self.assertEquals(1, row["inaccurate"])
    #             self.assertEquals(0, row["accuracy_percentage"])
    #         elif row.get("gt_defect_id") == 3:
    #             self.assertEquals(1, row["total"])
    #             self.assertEquals(1, row["auto_classified"])
    #             self.assertEquals(0, row["manual"])
    #             self.assertEquals(100, row["auto_classified_percentage"])
    #             self.assertEquals(0, row["accurate"])
    #             self.assertEquals(1, row["inaccurate"])
    #             self.assertEquals(0, row["accuracy_percentage"])
    #         elif row.get("gt_defect_id") == 4:
    #             self.assertEquals(1, row["total"])
    #             self.assertEquals(0, row["auto_classified"])
    #             self.assertEquals(1, row["manual"])
    #             self.assertEquals(0, row["auto_classified_percentage"])
    #             self.assertEquals(0, row["accurate"])
    #             self.assertEquals(0, row["inaccurate"])
    #             self.assertEquals(None, row["accuracy_percentage"])
    #         elif row.get("gt_defect_id") == 1:
    #             self.assertEquals(3, row["total"])
    #             self.assertEquals(2, row["auto_classified"])
    #             self.assertEquals(1, row["manual"])
    #             self.assertEquals(66, row["auto_classified_percentage"])
    #             self.assertEquals(2, row["accurate"])
    #             self.assertEquals(0, row["inaccurate"])
    #             self.assertEquals(100, row["accuracy_percentage"])

    def test_cohort_metrics_use_case_level(self):
        url = "/api/v1/classif-ai/classification/metrics/cohort/use_case_level/?date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("this unit is not accepted", str(response.data[0]))

        url = "/api/v1/classif-ai/classification/metrics/cohort/use_case_level/?unit=file&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("auto_classification or accuracy ranges are not present", str(response.data[0]))

        url = "/api/v1/classif-ai/classification/metrics/cohort/use_case_level/?unit=file&auto_classification=0,93,100&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)

        self.assertEquals("93-100", response.data[0]["cohort"])
        self.assertEquals(0, response.data[0]["total"])
        self.assertEquals(None, response.data[0].get("use_case_ids"))
        self.assertEquals(0, response.data[0]["percentage"])

        self.assertEquals("0-93", response.data[1]["cohort"])
        self.assertEquals(1, response.data[1]["total"])
        self.assertEquals([2], response.data[1]["use_case_ids"])
        self.assertEquals(100, response.data[1]["percentage"])

        url = "/api/v1/classif-ai/classification/metrics/cohort/use_case_level/?unit=wafer&auto_classification=0,93,100&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals("93-100", response.data[0]["cohort"])
        self.assertEquals(0, response.data[0]["total"])
        self.assertEquals(0, response.data[0]["percentage"])

        self.assertEquals(200, response.status_code)
        self.assertEquals("0-93", response.data[1]["cohort"])
        self.assertEquals(1, response.data[1]["total"])
        self.assertEquals([2], response.data[1]["use_case_ids"])
        self.assertEquals(100, response.data[1]["percentage"])

    def test_cohort_metrics_folder_level(self):

        url = (
            "/api/v1/classif-ai/classification/metrics/cohort/folder_level/?&date__gte=2020-01-01&date__lte=2021-01-01"
        )
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("auto_classification or accuracy ranges are not present", str(response.data[0]))

        url = "/api/v1/classif-ai/classification/metrics/cohort/folder_level/?auto_classification=0,93,100&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(3, len(response.data))

        self.assertEquals("93-100", response.data[0]["cohort"])
        self.assertEquals(1, response.data[0]["total"])
        self.assertEquals([2], response.data[0]["upload_session_ids"])
        self.assertEquals(50, response.data[0]["percentage"])

        self.assertEquals("0-93", response.data[1]["cohort"])
        self.assertEquals(1, response.data[1]["total"])
        self.assertEquals([1], response.data[1]["upload_session_ids"])
        self.assertEquals(50, response.data[1]["percentage"])

    def test_cohort_metrics_defect_level(self):

        url = (
            "/api/v1/classif-ai/classification/metrics/cohort/defect_level/?&date__gte=2020-01-01&date__lte=2021-01-01"
        )
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("auto_classification or accuracy ranges are not present", str(response.data[0]))

        url = "/api/v1/classif-ai/classification/metrics/cohort/defect_level/?accuracy=0,90,100&date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(3, len(response.data))

        for row in response.data:
            if row.get("cohort") == "N/A":
                self.assertEquals(2, row["total"])
                self.assertEquals({4, 5}, row["gt_defect_ids"])
                self.assertEquals(40, row["percentage"])
            elif row.get("cohort") == "0-90":
                self.assertEquals(2, row["total"])
                self.assertEquals({2, 3}, row["gt_defect_ids"])
                self.assertEquals(40, row["percentage"])
            elif row.get("cohort") == "90-100":
                self.assertEquals(1, row["total"])
                self.assertEquals({1}, row["gt_defect_ids"])
                self.assertEquals(20, row["percentage"])
