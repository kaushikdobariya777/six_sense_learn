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


class SingleLabelClassificationTest(ClassifAiTestCase):
    # use_case - model - wafer - file - file_created - gt_defect - model_defect, confidence (N means null, confidence_threshold=0.95, wafer_threshold=0.6)
    # 1 - 1 - 1 - 1 - 2020-10-11 - 1 - 1 - 0.96 : total=1, auto_classified=1, accurate=1 : confident and matched
    # 1 - 1 - 1 - 2 - 2020-10-12 - 2 - 3 - 0.96 : total=2, auto_classified=2, accurate=1 : confident but no match
    # 1 - 1 - 1 - 3 - 2020-10-13 - 3 - 2 - 0.96 : total=3, auto_classified=3, accurate=1 : confident but no match
    # 1 - 1 - 1 - 4 - 2020-10-14 - 4 - N - N    : total=4, auto_classified=3, accurate=1 : no model defect
    # 1 - 1 - 1 - 5 - 2020-10-15 - N - 5 - 0.96 : total=4, auto_classified=3, accurate=1 : no gt defect
    # 1 - 2 - 1 - 6 - 2020-10-16 - 1 - 1 - 0.16 : total=5, auto_classified=3, accurate=1 : not confident
    # 1 - 2 - 1 - 1 - 2020-10-11 - 1 - 1 - 0.96 : total=5, auto_classified=3, accurate=1 : automodel on file #1
    # 1 - 2 - 1 - 7 - 1900-10-17 - 1 - 1 - 0.96 : total=5, auto_classified=3, accurate=1 : file's created date is not in the range, year 1900
    # 1 - 2 - 2 - 8 - 2020-10-16 - 1 - 1 - 0.96 : total=6, auto_classified=4, accurate=2 : confident and matched, wafer-2
    # 1 - 2 - 1 - 9 - 2020-10-19 - N - N - N    : total=6, auto_classified=4, accurate=2 : no gt_defect and model_defect
    # 1 - 2 - N -10 - 2030-10-11 - 1 - 1 - 0.96 : total=7, auto_classified=5, accurate=3 : wafer is Null
    # 1 - 2 - 1 -11 - 2030-10-11 - 1 - 1 - 0.96 : total=8, auto_classified=6, accurate=4 : file_set.use_case is Null, but upload_session.use_case not Null
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Since we have file_level_metrics, timeseries_metrics, defect_distribution etc, we need to
        # have some extra cases
        cls.single_label_use_case.automation_conditions = {"threshold_percentage": 60}
        cls.single_label_use_case.save()

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
        cls.ml_model_2 = MlModel.objects.create(
            name="test-model-2",
            code="test-code-2",
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
        cls.model_classification_6 = ModelClassification.objects.create(file=cls.file_6, ml_model=cls.ml_model_2)
        cls.model_classification_7 = ModelClassification.objects.create(file=cls.file_7, ml_model=cls.ml_model_2)
        cls.model_classification_8 = ModelClassification.objects.create(file=cls.file_8, ml_model=cls.ml_model_2)
        cls.model_classification_9 = ModelClassification.objects.create(file=cls.file_1, ml_model=cls.ml_model_2)
        cls.model_classification_10 = ModelClassification.objects.create(file=cls.file_9, ml_model=cls.ml_model_2)
        cls.model_classification_11 = ModelClassification.objects.create(file=cls.file_10, ml_model=cls.ml_model_2)
        cls.model_classification_12 = ModelClassification.objects.create(file=cls.file_11, ml_model=cls.ml_model_2)

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
        cls.model_classification_defect_9 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_9, defect=cls.defect_1, confidence=0.96
        )
        cls.model_classification_defect_10 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_11, defect=cls.defect_1, confidence=0.96
        )
        cls.model_classification_defect_11 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_12, defect=cls.defect_1, confidence=0.96
        )

        # multi label usecase and dataset

        # use_case - model - wafer - file - file_created - gt_defect - model_defect, confidence (N means null, confidence_threshold=0.96, wafer_threshold=0.6)
        # 1 - 1 - 1 - 101 - 2020-10-11 - [1, 2] - [1, 2]  - [0.96, 0.96] : total_files=1, auto_classified_files=1 : confident defects
        # 1 - 1 - 1 - 102 - 2020-10-12 - [1, 2] - [1, 3]  - [0.96, 0.96] : total_files=2, auto_classified_files=2 : confident defects
        # 1 - 1 - 1 - 103 - 2020-10-13 - [    ] - [2, 3]  - [0.96, 0.96] : total_files=2, auto_classified_files=2 : no gt defect
        # 1 - 1 - 1 - 104 - 2020-10-14 - [1, 2] - [    ]  -  N           : total_files=3, auto_classified_files=2 : no model defect
        # 1 - 1 - 1 - 105 - 2020-10-15 - [1]    - [1]     - [0.16]       : total_files=4, auto_classified_files=2 : not confident
        # 1 - 2 - 1 - 106 - 2020-10-16 - [1, 2]  - [1, 2] - [0.16, 0.96] : total_files=5, auto_classified_files=3 : atleast one confident defect

        cls.use_case.automation_conditions = {"threshold_percentage": 60}
        cls.use_case.save()

        cls.ml_model_101 = MlModel.objects.create(
            name="test-model-101",
            code="test-code-101",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.use_case,
            confidence_threshold="0.96",
        )
        cls.ml_model_102 = MlModel.objects.create(
            name="test-model-102",
            code="test-code-102",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.use_case,
            confidence_threshold="0.96",
        )
        cls.upload_session_101 = UploadSession.objects.create(
            name="test-session-101", subscription=cls.subscription, use_case=cls.use_case
        )
        cls.upload_session_102 = UploadSession.objects.create(
            name="test-session-102", subscription=cls.subscription, use_case=cls.use_case
        )

        cls.defect_101 = Defect.objects.create(
            name="test-defect-101", code="test-code-101", subscription=cls.subscription
        )
        cls.defect_102 = Defect.objects.create(
            name="test-defect-102", code="test-code-102", subscription=cls.subscription
        )
        cls.defect_103 = Defect.objects.create(
            name="test-defect-103", code="test-code-103", subscription=cls.subscription
        )
        cls.defect_104 = Defect.objects.create(
            name="test-defect-104", code="test-code-104", subscription=cls.subscription
        )
        cls.defect_105 = Defect.objects.create(
            name="test-defect-105", code="test-code-105", subscription=cls.subscription
        )

        cls.wafer_map_101 = WaferMap.objects.create(organization_wafer_id="charfiled-101")
        cls.wafer_map_102 = WaferMap.objects.create(organization_wafer_id="charfiled-102")

        cls.file_set_101 = FileSet.objects.create(
            upload_session=cls.upload_session_101,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_101,
            use_case=cls.use_case,
        )
        cls.file_set_102 = FileSet.objects.create(
            upload_session=cls.upload_session_102,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_101,
            use_case=cls.use_case,
        )
        cls.file_set_103 = FileSet.objects.create(
            upload_session=cls.upload_session_102,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_101,
            use_case=cls.use_case,
        )
        cls.file_set_104 = FileSet.objects.create(
            upload_session=cls.upload_session_101,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_101,
            use_case=cls.use_case,
        )
        cls.file_set_105 = FileSet.objects.create(
            upload_session=cls.upload_session_101,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_101,
            use_case=cls.use_case,
        )
        cls.file_set_106 = FileSet.objects.create(
            upload_session=cls.upload_session_101,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_101,
            use_case=cls.use_case,
        )
        cls.file_set_107 = FileSet.objects.create(
            upload_session=cls.upload_session_101,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_101,
            use_case=cls.use_case,
        )
        cls.file_set_108 = FileSet.objects.create(
            upload_session=cls.upload_session_101,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_102,
            use_case=cls.use_case,
        )

        # not able to pass created ts directly while creation :(
        cls.file_101 = File.objects.create(
            file_set=cls.file_set_101, name="test-file-name-101", path="test/test-path-1"
        )
        cls.file_101.created_ts = "2020-10-11 00:00:00+00:00"
        cls.file_101.save()
        cls.file_set_101.created_ts = "2020-10-11 00:00:00+00:00"
        cls.file_set_101.save()
        cls.file_102 = File.objects.create(
            file_set=cls.file_set_102, name="test-file-name-102", path="test/test-path-2"
        )
        cls.file_102.created_ts = "2020-10-12 00:00:00+00:00"
        cls.file_102.save()
        cls.file_set_102.created_ts = "2020-10-12 00:00:00+00:00"
        cls.file_set_102.save()
        cls.file_103 = File.objects.create(
            file_set=cls.file_set_103, name="test-file-name-103", path="test/test-path-3"
        )
        cls.file_103.created_ts = "2020-10-13 00:00:00+00:00"
        cls.file_103.save()
        cls.file_set_103.created_ts = "2020-10-13 00:00:00+00:00"
        cls.file_set_103.save()

        cls.file_104 = File.objects.create(
            file_set=cls.file_set_104, name="test-file-name-104", path="test/test-path-4"
        )
        cls.file_104.created_ts = "2020-10-14 00:00:00+00:00"
        cls.file_104.save()
        cls.file_set_104.created_ts = "2020-10-14 00:00:00+00:00"
        cls.file_set_104.save()

        cls.file_105 = File.objects.create(
            file_set=cls.file_set_105, name="test-file-name-105", path="test/test-path-5"
        )
        cls.file_105.created_ts = "2020-10-15 00:00:00+00:00"
        cls.file_105.save()
        cls.file_set_105.created_ts = "2020-10-15 00:00:00+00:00"
        cls.file_set_105.save()

        cls.file_106 = File.objects.create(
            file_set=cls.file_set_106, name="test-file-name-106", path="test/test-path-6"
        )
        cls.file_106.created_ts = "2020-10-16 00:00:00+00:00"
        cls.file_106.save()
        cls.file_set_106.created_ts = "2020-10-16 00:00:00+00:00"
        cls.file_set_106.save()

        cls.file_107 = File.objects.create(
            file_set=cls.file_set_107, name="test-file-name-107", path="test/test-path-7"
        )
        cls.file_107.created_ts = "1900-10-17 00:00:00+00:00"
        cls.file_107.save()
        cls.file_set_107.created_ts = "1900-10-17 00:00:00+00:00"
        cls.file_set_107.save()

        cls.file_108 = File.objects.create(
            file_set=cls.file_set_108, name="test-file-name-108", path="test/test-path-8"
        )
        cls.file_108.created_ts = "2020-10-18 00:00:00+00:00"
        cls.file_108.save()
        cls.file_set_108.created_ts = "2020-10-18 00:00:00+00:00"
        cls.file_set_108.save()

        cls.gt_classification_101 = GTClassification.objects.create(file=cls.file_101)
        cls.gt_classification_102 = GTClassification.objects.create(file=cls.file_102)
        cls.gt_classification_103 = GTClassification.objects.create(file=cls.file_103)
        cls.gt_classification_104 = GTClassification.objects.create(file=cls.file_104)
        cls.gt_classification_105 = GTClassification.objects.create(file=cls.file_105)
        cls.gt_classification_106 = GTClassification.objects.create(file=cls.file_106)

        cls.gt_classification_defect_101 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_101, defect=cls.defect_101
        )
        cls.gt_classification_defect_102 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_101, defect=cls.defect_102
        )
        cls.gt_classification_defect_103 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_102, defect=cls.defect_101
        )
        cls.gt_classification_defect_104 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_102, defect=cls.defect_102
        )
        cls.gt_classification_defect_106 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_104, defect=cls.defect_101
        )
        cls.gt_classification_defect_107 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_104, defect=cls.defect_102
        )
        cls.gt_classification_defect_108 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_105, defect=cls.defect_101
        )
        cls.gt_classification_defect_108 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_106, defect=cls.defect_101
        )
        cls.gt_classification_defect_108 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_106, defect=cls.defect_102
        )

        cls.model_classification_101 = ModelClassification.objects.create(file=cls.file_101, ml_model=cls.ml_model_101)
        cls.model_classification_102 = ModelClassification.objects.create(file=cls.file_102, ml_model=cls.ml_model_101)
        cls.model_classification_103 = ModelClassification.objects.create(file=cls.file_103, ml_model=cls.ml_model_101)
        cls.model_classification_104 = ModelClassification.objects.create(file=cls.file_104, ml_model=cls.ml_model_101)
        cls.model_classification_105 = ModelClassification.objects.create(file=cls.file_105, ml_model=cls.ml_model_101)
        cls.model_classification_106 = ModelClassification.objects.create(file=cls.file_106, ml_model=cls.ml_model_102)

        cls.model_classification_defect_101 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_101, defect=cls.defect_101, confidence=0.96
        )
        cls.model_classification_defect_102 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_101, defect=cls.defect_102, confidence=0.96
        )
        cls.model_classification_defect_103 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_102, defect=cls.defect_101, confidence=0.96
        )
        cls.model_classification_defect_105 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_102, defect=cls.defect_103, confidence=0.96
        )
        cls.model_classification_defect_106 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_103, defect=cls.defect_102, confidence=0.16
        )
        cls.model_classification_defect_107 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_103, defect=cls.defect_103, confidence=0.96
        )
        cls.model_classification_defect_108 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_105, defect=cls.defect_101, confidence=0.16
        )
        cls.model_classification_defect_109 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_106, defect=cls.defect_101, confidence=0.16
        )
        cls.model_classification_defect_109 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_106, defect=cls.defect_102, confidence=0.96
        )

        # TODO: Best approach is to make confidence_threshold and wafer_threshold non Nullable.
        # single label usecase without threshold_percentage

        # use_case - model - wafer - file - file_created - gt_defect - model_defect, confidence (N means null, confidence_threshold=N, wafer_threshold=N)
        # 1 - 1 - 1 - 1 - 2030-10-11 - 1  - 1  - 0.96 : total=0, auto_classified=0 : no confidence and wafer threshold
        cls.use_case_201 = UseCase.objects.create(
            name="test-usecase-201",
            type="CLASSIFICATION",
            subscription=cls.subscription,
            classification_type="SINGLE_LABEL",
        )

        cls.ml_model_201 = MlModel.objects.create(
            name="test-model-201",
            code="test-code-201",
            version=1,
            status="deployed_in_prod",
            is_stable=True,
            subscription=cls.subscription,
            use_case=cls.use_case_201,
        )
        cls.upload_session_201 = UploadSession.objects.create(
            name="test-session-201", subscription=cls.subscription, use_case=cls.use_case_201
        )

        cls.defect_201 = Defect.objects.create(
            name="test-defect-201", code="test-code-201", subscription=cls.subscription
        )

        cls.wafer_map_201 = WaferMap.objects.create(organization_wafer_id="charfiled-201")

        cls.file_set_201 = FileSet.objects.create(
            upload_session=cls.upload_session_201,
            subscription=cls.subscription,
            meta_info={"tray_id": "abcd"},
            wafer=cls.wafer_map_201,
            use_case=cls.use_case_201,
        )

        cls.file_201 = File.objects.create(
            file_set=cls.file_set_201, name="test-file-name-201", path="test/test-path-201"
        )
        cls.file_201.created_ts = "2030-10-11 00:00:00+00:00"
        cls.file_201.save()

        cls.gt_classification_201 = GTClassification.objects.create(file=cls.file_201)
        cls.gt_classification_defect_201 = GTClassificationDefect.objects.create(
            classification=cls.gt_classification_201, defect=cls.defect_201
        )

        cls.model_classification_201 = ModelClassification.objects.create(file=cls.file_201, ml_model=cls.ml_model_201)
        cls.model_classification_defect_201 = ModelClassificationDefect.objects.create(
            classification=cls.model_classification_201, defect=cls.defect_201, confidence=0.96
        )

    def test_confusion_matrix(self):

        url = "/api/v1/classif-ai/classification/metrics/confusion_matrix/?date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("confusion matrix needs one usecase", str(response.data[0]))

        url = "/api/v1/classif-ai/classification/metrics/confusion_matrix/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=51"
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("use case does not exist", str(response.data[0]))

        url = "/api/v1/classif-ai/classification/metrics/confusion_matrix/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=1"
        response = self.authorized_client.get(url)

        self.assertEquals(400, response.status_code)
        self.assertEquals("confusion matrix needs single label classification data", str(response.data[0]))

        url = "/api/v1/classif-ai/classification/metrics/confusion_matrix/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=2"
        response = self.authorized_client.get(url)

        self.assertEquals(response.status_code, 200)
        self.assertEquals([1, -1, 2, 3], list(response.data.keys()))
        self.assertEquals(2, response.data.get(1).get("model_defects").get(1).get("matched_count"))
        self.assertEquals(1, response.data.get(1).get("model_defects").get(-1).get("matched_count"))
        self.assertEquals(1, response.data.get(2).get("model_defects").get(3).get("matched_count"))
        self.assertEquals(1, response.data.get(3).get("model_defects").get(2).get("matched_count"))

    def test_auto_classification_file_level(self):

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(14, response.data.get("total"))
        self.assertEquals(9, response.data.get("auto_classified"))
        self.assertEquals(64, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(8, response.data.get("total"))
        self.assertEquals(5, response.data.get("auto_classified"))
        self.assertEquals(62, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL&use_case_id__in=2"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(8, response.data.get("total"))
        self.assertEquals(5, response.data.get("auto_classified"))
        self.assertEquals(62, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL&use_case_id__in=2850"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, response.data.get("total"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=MULTI_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(6, response.data.get("total"))
        self.assertEquals(4, response.data.get("auto_classified"))
        self.assertEquals(66, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2029-01-01&date__lte=2031-01-01&ml_model_id__in=2&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(2, response.data.get("total"))
        self.assertEquals(2, response.data.get("auto_classified"))
        self.assertEquals(100, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&upload_session_id__in=2&is_bookmarked=true"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, response.data.get("total"))
        self.assertEquals(0, response.data.get("auto_classified"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&meta_info__tray_id__in=1"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, response.data.get("total"))
        self.assertEquals(0, response.data.get("auto_classified"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&meta_info__tray_id__in=abcd"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(13, response.data.get("total"))
        self.assertEquals(8, response.data.get("auto_classified"))

        # random key
        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&meta_info__xyz__in=abcd"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, response.data.get("total"))
        self.assertEquals(0, response.data.get("auto_classified"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&ground_truth_label__in=3"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, response.data.get("total"))
        self.assertEquals(1, response.data.get("auto_classified"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&train_type__in=TRAIN"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, response.data.get("total"))
        self.assertEquals(1, response.data.get("auto_classified"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level/?date__gte=2020-01-01&date__lte=2021-01-01&train_type__in=TEST"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, response.data.get("total"))
        self.assertEquals(0, response.data.get("auto_classified"))

    def test_auto_classification_file_level_timeseries(self):
        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(8, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(100, response.data[1].get("percentage"))
        self.assertEquals(100, response.data[2].get("percentage"))
        self.assertEquals(0, response.data[3].get("percentage"))
        self.assertEquals(100, response.data[4].get("percentage"))
        self.assertEquals(0, response.data[5].get("percentage"))
        self.assertEquals(100, response.data[6].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=MULTI_LABEL"
        response = self.authorized_client.get(url)
        self.assertEquals(200, response.status_code)
        self.assertEquals(6, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(100, response.data[1].get("percentage"))
        self.assertEquals(100, response.data[2].get("percentage"))
        self.assertEquals(0, response.data[3].get("percentage"))
        self.assertEquals(0, response.data[4].get("percentage"))
        self.assertEquals(100, response.data[5].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/file_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL&use_case_id__in=2850"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, len(response.data))

    def test_accuracy_defect_level(self):
        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(10, response.data.get("total"))
        self.assertEquals(6, response.data.get("accurate"))
        self.assertEquals(60, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(4, response.data.get("total"))
        self.assertEquals(2, response.data.get("accurate"))
        self.assertEquals(50, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL&use_case_id__in=2"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(4, response.data.get("total"))
        self.assertEquals(2, response.data.get("accurate"))
        self.assertEquals(50, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&ml_model_id__in=1&classification_type=SINGLE_LABEL&use_case_id__in=2"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(3, response.data.get("total"))
        self.assertEquals(1, response.data.get("accurate"))
        self.assertEquals(33, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL&use_case_id__in=28492"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, response.data.get("total"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=MULTI_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(6, response.data.get("total"))
        self.assertEquals(4, response.data.get("accurate"))
        self.assertEquals(66, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&upload_session_id__in=2"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(2, response.data.get("total"))
        self.assertEquals(0, response.data.get("accurate"))
        self.assertEquals(0, response.data.get("percentage"))

    def test_accuracy_defect_level_timeseries(self):

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(5, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(33, response.data[1].get("percentage"))
        self.assertEquals(0, response.data[2].get("percentage"))
        self.assertEquals(50, response.data[3].get("percentage"))
        self.assertEquals(100, response.data[4].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(4, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(0, response.data[1].get("percentage"))
        self.assertEquals(0, response.data[2].get("percentage"))
        self.assertEquals(100, response.data[3].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=2&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(4, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(0, response.data[1].get("percentage"))
        self.assertEquals(0, response.data[2].get("percentage"))
        self.assertEquals(100, response.data[3].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=191&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, len(response.data))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=MULTI_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(3, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(50, response.data[1].get("percentage"))
        self.assertEquals(50, response.data[2].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/defect_level_timeseries/?date__gte=2029-01-01&date__lte=2031-01-01&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))

    def test_accuracy_wafer_level(self):
        url = "/api/v1/classif-ai/classification/metrics/accuracy/wafer_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, response.data.get("total"))
        self.assertEquals(1, response.data.get("accurate"))
        self.assertEquals(100, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/wafer_level/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=19&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, response.data.get("total"))

    def test_accuracy_wafer_level_timeseries(self):
        url = "/api/v1/classif-ai/classification/metrics/accuracy/wafer_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(4, len(response.data))
        self.assertEquals("2020-10-11", response.data[0].get("effective_date"))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals("2020-10-12", response.data[1].get("effective_date"))
        self.assertEquals(None, response.data[1].get("percentage"))
        self.assertEquals("2020-10-13", response.data[2].get("effective_date"))
        self.assertEquals(None, response.data[2].get("percentage"))
        self.assertEquals("2020-10-18", response.data[3].get("effective_date"))
        self.assertEquals(100, response.data[3].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/wafer_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=19&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, len(response.data))

        url = "/api/v1/classif-ai/classification/metrics/accuracy/wafer_level_timeseries/?date__gte=2029-01-01&date__lte=2031-01-01&ml_model_id__in=2&classification_type=SINGLE_LABEL"

        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))

    def test_auto_classification_wafer_level(self):
        url = "/api/v1/classif-ai/classification/metrics/auto_classification/wafer_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(2, response.data.get("total"))
        self.assertEquals(1, response.data.get("auto_classified"))
        self.assertEquals(50, response.data.get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/wafer_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL&upload_session_id__in=2"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, response.data.get("total"))
        self.assertEquals(1, response.data.get("auto_classified"))
        self.assertEquals(100, response.data.get("percentage"))

    def test_auto_classification_wafer_level_timeseries(self):
        url = "/api/v1/classif-ai/classification/metrics/auto_classification/wafer_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(8, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(100, response.data[1].get("percentage"))
        self.assertEquals(100, response.data[2].get("percentage"))
        self.assertEquals(0, response.data[3].get("percentage"))
        self.assertEquals(100, response.data[4].get("percentage"))
        self.assertEquals(0, response.data[5].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/wafer_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=2&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(8, len(response.data))
        self.assertEquals(100, response.data[0].get("percentage"))
        self.assertEquals(100, response.data[1].get("percentage"))
        self.assertEquals(100, response.data[2].get("percentage"))
        self.assertEquals(0, response.data[3].get("percentage"))
        self.assertEquals(0, response.data[5].get("percentage"))

        url = "/api/v1/classif-ai/classification/metrics/auto_classification/wafer_level_timeseries/?date__gte=2020-01-01&date__lte=2021-01-01&use_case_id__in=19&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, len(response.data))

    def test_missclassification_defect_level(self):
        url = "/api/v1/classif-ai/classification/metrics/missclassification/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(2, len(response.data))
        self.assertEquals(50, response.data[0].get("miss_classification_percentage"))
        self.assertEquals(2, response.data[0].get("total_miss_classifications"))
        self.assertEquals(50, response.data[1].get("miss_classification_percentage"))
        self.assertEquals(2, response.data[1].get("total_miss_classifications"))

        url = "/api/v1/classif-ai/classification/metrics/missclassification/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&ml_model_id__in=2&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(0, len(response.data))

    def test_classwise_metrics_defect_level(self):
        url = "/api/v1/classif-ai/classification/metrics/classwise/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(5, len(response.data))
        for row in response.data:
            if row.get("gt_defect_id") == 1:
                self.assertEquals(3, row.get("total"))
                self.assertEquals(2, row.get("auto_classified"))
                self.assertEquals(2, row.get("accurate"))
                self.assertEquals(0, row.get("extra"))
                self.assertEquals(0, row.get("missed"))
                self.assertEquals(67, row.get("auto_classified_percentage"))
                self.assertEquals(100, row.get("accuracy_percentage"))
                self.assertEquals(0, row.get("extra_percentage"))
                self.assertEquals(0, row.get("missed_percentage"))
            elif row.get("gt_defect_id") in [2, 3]:
                self.assertEquals(1, row.get("total"))
                self.assertEquals(1, row.get("auto_classified"))
                self.assertEquals(0, row.get("accurate"))
                self.assertEquals(1, row.get("extra"))
                self.assertEquals(1, row.get("missed"))
                self.assertEquals(100, row.get("missed_percentage"))
            elif row.get("gt_defect_id") == 4:
                self.assertEquals(1, row.get("total"))
                self.assertEquals(0, row.get("auto_classified"))
                self.assertEquals(0, row.get("accurate"))
                self.assertEquals(0, row.get("extra"))
                self.assertEquals(0, row.get("missed"))
                self.assertEquals(0, row.get("auto_classified_percentage"))
                self.assertEquals(None, row.get("accuracy_percentage"))
                self.assertEquals(None, row.get("extra_percentage"))
                self.assertEquals(None, row.get("missed_percentage"))

        url = "/api/v1/classif-ai/classification/metrics/classwise/defect_level/?date__gte=2020-01-01&date__lte=2021-01-01&ml_model_id__in=2938&classification_type=MULTI_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(0, len(response.data))

    def test_classwise_metrics_use_case_level(self):
        url = "/api/v1/classif-ai/classification/metrics/classwise/use_case_level/?date__gte=2020-01-01&date__lte=2021-01-01&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, len(response.data))
        self.assertEquals("single-label-test-usecase", response.data[0].get("use_case_name"))
        self.assertEquals(6, response.data[0].get("total"))
        self.assertEquals(4, response.data[0].get("auto_classified"))
        self.assertEquals(66, response.data[0].get("auto_classified_percentage"))
        self.assertEquals(2, response.data[0].get("accurate"))
        self.assertEquals(50, response.data[0].get("accuracy_percentage"))
        self.assertEquals(33, response.data[0].get("auto_classification_drop"))
        self.assertEquals(50, response.data[0].get("accuracy_drop"))

        url = "/api/v1/classif-ai/classification/metrics/classwise/use_case_level/?date__gte=2020-01-01&date__lte=2021-01-01&ml_model_id__in=2&classification_type=SINGLE_LABEL"
        response = self.authorized_client.get(url)

        self.assertEquals(200, response.status_code)
        self.assertEquals(1, len(response.data))
        self.assertEquals("single-label-test-usecase", response.data[0].get("use_case_name"))
        self.assertEquals(3, response.data[0].get("total"))
        self.assertEquals(2, response.data[0].get("auto_classified"))
        self.assertEquals(66.0, response.data[0].get("auto_classified_percentage"))
        self.assertEquals(2, response.data[0].get("accurate"))
        self.assertEquals(100, response.data[0].get("accuracy_percentage"))
        self.assertEquals(33, response.data[0].get("auto_classification_drop"))
        self.assertEquals(0, response.data[0].get("accuracy_drop"))

        # Note: MUTLI_LABEL gives erroneous results
