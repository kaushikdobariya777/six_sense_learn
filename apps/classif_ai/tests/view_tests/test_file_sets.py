from apps.classif_ai.tests.classif_ai_test_case import ClassifAiTestCase
from apps.classif_ai.models import (
    MlModel,
    TrainingSession,
    TrainingSessionFileSet,
    UploadSession,
    FileSet,
    Defect,
    WaferMap,
    File,
    GTClassification,
    GTClassificationDefect,
    ModelClassification,
    ModelClassificationDefect,
)


class FileSetFilterTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        ml_model_1 = MlModel.objects.create(
            name="test-model-1",
            code="test-code",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.single_label_use_case,
        )
        ml_model_2 = MlModel.objects.create(
            name="test-model-2",
            code="test-code",
            version=2,
            status="ready_for_deployment",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.single_label_use_case,
        )
        upload_session = UploadSession.objects.create(
            name="test-upload", subscription=cls.subscription, use_case=cls.use_case
        )
        valid_meta_info = {"tray_id": "abcd", "Pass": 1, "row_and_col_id": "xyz", "StartDate": "2020-08-01 06:00"}
        file_sets = []
        for _ in range(0, 17):
            file_set = FileSet(
                upload_session=upload_session,
                subscription=cls.subscription,
                use_case=cls.use_case,
                meta_info=valid_meta_info,
            )
            file_sets.append(file_set)

        cls.file_sets = FileSet.objects.bulk_create(file_sets)
        ts_1 = TrainingSession.objects.create(new_ml_model=ml_model_1)
        tsfs = []
        train_types = ["TEST"] * 4
        train_types.extend(["TRAIN"] * 5)
        train_types.append("VALIDATION")
        for file_set, train_type in zip(cls.file_sets[0:10], train_types):
            tsfs.append(
                TrainingSessionFileSet(file_set=file_set, training_session=ts_1, dataset_train_type=train_type)
            )
        TrainingSessionFileSet.objects.bulk_create(tsfs)
        ts_2 = TrainingSession.objects.create(new_ml_model=ml_model_2)
        TrainingSessionFileSet.objects.bulk_create(
            [
                TrainingSessionFileSet(file_set=file_set, training_session=ts_2, dataset_train_type="TEST")
                for file_set in cls.file_sets[9:12]
            ]
        )

    def test_get_file_sets_with_train_type(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?train_type__in=NOT_TRAINED,TEST")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 12)
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?train_type__in=TRAIN,VALIDATION")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 6)
        response = self.authorized_client.get(
            "/api/v1/classif-ai/file-set/?train_type__in=NOT_TRAINED&training_ml_model__in=1"
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 7)
        response = self.authorized_client.get(
            "/api/v1/classif-ai/file-set/?train_type__in=NOT_TRAINED,TEST&training_ml_model__in=1,2"
        )
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 12)


class FileSetFiltersTest(ClassifAiTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
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

        cls.upload_session = UploadSession.objects.create(
            name="test-session",
            subscription=cls.subscription,
            use_case=cls.use_case,
        )

        cls.defect_1 = Defect.objects.create(name="test-defect-1", code="test-code-1", subscription=cls.subscription)
        cls.defect_2 = Defect.objects.create(name="test-defect-2", code="test-code-2", subscription=cls.subscription)
        cls.defect_3 = Defect.objects.create(name="test-defect-3", code="test-code-3", subscription=cls.subscription)
        cls.defect_4 = Defect.objects.create(name="test-defect-4", code="test-code-4", subscription=cls.subscription)
        cls.defect_5 = Defect.objects.create(name="test-defect-5", code="test-code-5", subscription=cls.subscription)
        cls.defect_6 = Defect.objects.create(name="test-defect-6", code="test-code-6", subscription=cls.subscription)

        cls.wafer_map_1 = WaferMap.objects.create(organization_wafer_id="charfiled-1")
        cls.wafer_map_2 = WaferMap.objects.create(organization_wafer_id="charfiled-2", status="auto_classified")

        cls.file_set_1 = FileSet.objects.create(
            upload_session=cls.upload_session,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_1,
            use_case=cls.single_label_use_case,
        )

        cls.file_set_2 = FileSet.objects.create(
            upload_session=cls.upload_session,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_2,
            use_case=cls.single_label_use_case,
        )

        cls.file_1 = File.objects.create(file_set=cls.file_set_1, name="test-file-name-1", path="test/test-path-1")
        cls.file_1.created_ts = "2020-10-11 00:00:00+00:00"
        cls.file_1.save()
        cls.file_2 = File.objects.create(file_set=cls.file_set_1, name="test-file-name-2", path="test/test-path-2")
        cls.file_2.created_ts = "2020-10-12 00:00:00+00:00"
        cls.file_2.save()
        cls.file_3 = File.objects.create(file_set=cls.file_set_1, name="test-file-name-3", path="test/test-path-3")
        cls.file_3.created_ts = "2020-10-13 00:00:00+00:00"
        cls.file_3.save()
        cls.file_4 = File.objects.create(file_set=cls.file_set_1, name="test-file-name-4", path="test/test-path-4")
        cls.file_4.created_ts = "2020-10-14 00:00:00+00:00"
        cls.file_4.save()
        cls.file_5 = File.objects.create(file_set=cls.file_set_1, name="test-file-name-5", path="test/test-path-5")
        cls.file_5.created_ts = "2020-10-15 00:00:00+00:00"
        cls.file_5.save()
        cls.file_6 = File.objects.create(file_set=cls.file_set_2, name="test-file-name-6", path="test/test-path-6")
        cls.file_6.created_ts = "2020-10-16 00:00:00+00:00"
        cls.file_6.save()
        cls.file_7 = File.objects.create(file_set=cls.file_set_2, name="test-file-name-7", path="test/test-path-7")
        cls.file_7.created_ts = "1900-10-17 00:00:00+00:00"
        cls.file_7.save()

        cls.gt_classification_1 = GTClassification.objects.create(file=cls.file_1)
        cls.gt_classification_2 = GTClassification.objects.create(file=cls.file_2)
        cls.gt_classification_3 = GTClassification.objects.create(file=cls.file_3)
        cls.gt_classification_4 = GTClassification.objects.create(file=cls.file_4)

        cls.gt_classification_defect_1 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_1, defect=cls.defect_1
        )
        cls.gt_classification_defect_2 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_2, defect=cls.defect_2
        )
        cls.gt_classification_defect_3 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_3, defect=cls.defect_3
        )

        cls.model_classification_1 = ModelClassification.objects.create(file=cls.file_1, ml_model=cls.ml_model_1)
        cls.model_classification_2 = ModelClassification.objects.create(file=cls.file_2, ml_model=cls.ml_model_1)
        cls.model_classification_3 = ModelClassification.objects.create(file=cls.file_3, ml_model=cls.ml_model_1)
        cls.model_classification_4 = ModelClassification.objects.create(file=cls.file_4, ml_model=cls.ml_model_1)
        cls.model_classification_5 = ModelClassification.objects.create(file=cls.file_5, ml_model=cls.ml_model_1)
        cls.model_classification_6 = ModelClassification.objects.create(file=cls.file_6, ml_model=cls.ml_model_1)

        cls.model_classification_defect_1 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_1, defect=cls.defect_1, confidence=0.96
        )
        cls.model_classification_defect_2 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_2, defect=cls.defect_2, confidence=0.96
        )
        cls.model_classification_defect_3 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_3, defect=cls.defect_3, confidence=0.96
        )
        cls.model_classification_defect_4 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_4, defect=cls.defect_4, confidence=0.96
        )
        cls.model_classification_defect_5 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_5, defect=cls.defect_5, confidence=0.96
        )
        cls.model_classification_defect_6 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_6, defect=cls.defect_6, confidence=0.90
        )

    def test_get_file_sets_with_is_audited_true(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?is_audited=true")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 4)

    def test_get_file_sets_with_is_audited_false(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?is_audited=false")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 1)

    def test_get_file_sets_with_is_wafer_map_status_pending(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?wafer_map__status__in=pending")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(1, response.data["count"])

    def test_get_file_sets_with_is_wafer_map_status_auto_classified(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?wafer_map__status__in=auto_classified")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 1)

    def test_get_file_sets_with_is_ai_or_gt_classified_true(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?is_ai_or_gt_classified=true")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(response.data["count"], 5)

    def test_get_file_sets_with_is_ai_or_gt_classified_false(self):
        response = self.authorized_client.get("/api/v1/classif-ai/file-set/?is_ai_or_gt_classified=false")
        # Check status code.
        self.assertEquals(response.status_code, 200)
        # Check count.
        self.assertEquals(1, response.data["count"])


# TODO: add celery mock into this
# class FileSetCopyToFolderTest(ClassifAiTestCase):
#     @classmethod
#     def setUpTestData(cls):
#         super().setUpTestData()
#         cls.upload_session_1 = UploadSession.objects.create(
#             name="test-session",
#             subscription=cls.subscription,
#             use_case=cls.use_case,
#         )

#         cls.wafer_map_1 = WaferMap.objects.create(organization_wafer_id="charfiled-1")
#         cls.file_set_1 = FileSet.objects.create(
#             upload_session=cls.upload_session_1,
#             subscription=cls.subscription,
#             meta_info={"tray_id": "abcd"},
#             wafer=cls.wafer_map_1,
#             use_case=cls.single_label_use_case,
#         )

#         cls.file_1 = File.objects.create(file_set=cls.file_set_1, name="test-file-name-1", path="test/test-path-1")
#         cls.file_1.created_ts = "2020-10-11 00:00:00+00:00"
#         cls.file_1.save()

#         cls.upload_session_2 = UploadSession.objects.create(
#             name="test-session-2",
#             subscription=cls.subscription,
#             use_case=cls.use_case,
#         )
#         cls.file_set_2 = FileSet.objects.create(
#             upload_session=cls.upload_session_2,
#             subscription=cls.subscription,
#             meta_info={"tray_id": "abcd"},
#             wafer=cls.wafer_map_1,
#             use_case=cls.single_label_use_case,
#         )

#         cls.file_2 = File.objects.create(file_set=cls.file_set_2, name="test-file-name-1", path="test/test-path-1")
#         cls.file_2.created_ts = "2020-10-11 00:00:00+00:00"
#         cls.file_2.save()

#     def test_copy_to_folder_with_skipping_existing_images(self):
#         response = self.authorized_client.post(
#             "/api/v1/classif-ai/file-set/copy/",
#             data={
#                 "upload_session_id": self.upload_session_2.id,
#                 "skip_existing_images": True,
#                 "file_set_filters": {"upload_session_id__in": "%s" % self.upload_session_1.id},
#             },
#             format="json",
#         )
#         # Check status code.
#         self.assertEquals(response.status_code, 200)
#         # Check count.
#         file_set = FileSet.objects.filter(upload_session=self.upload_session_2.id)
#         self.assertEquals(1, file_set.count())

#     def test_copy_to_folder_with_skipping_existing_images_false(self):
#         response = self.authorized_client.post(
#             "/api/v1/classif-ai/file-set/copy/",
#             data={
#                 "upload_session_id": self.upload_session_2.id,
#                 "skip_existing_images": False,
#                 "file_set_filters": {"upload_session_id__in": "%s" % self.upload_session_1.id},
#             },
#             format="json",
#         )
#         # Check status code.
#         self.assertEquals(response.status_code, 200)
#         # Check count.
#         file_set = FileSet.objects.filter(upload_session=self.upload_session_2.id)
#         self.assertEquals(2, file_set.count())
