import glob
import glob
import json
import logging
import os
import shutil
import sys
import tempfile
import uuid
from datetime import datetime
from functools import reduce
from operator import ior

import boto3
import requests
from django.contrib.gis.geos import Polygon
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.contrib.postgres.fields.jsonb import KeyTextTransform
from django.core.exceptions import ValidationError
from django.db import transaction, connection
from django.db.models import Count
from django.db.models import Q, Min
from django.db.models.functions import TruncWeek, TruncMonth, TruncDay
from sixsense.settings import IMAGE_HANDLER_QUEUE_URL, INFERENCE_QUEUE_REGION

from apps.classif_ai.helpers import (
    build_query,
    calculate_iou,
    inference_output_queue,
    is_same_region,
    convert_datetime_to_str,
    get_env,
    create_celery_format_message,
)
from apps.classif_ai.models import (
    UseCase,
    FileRegion,
    File,
    FileSetInferenceQueue,
    MlModel,
    Defect,
    FileSet,
    JsonKeys,
    MlModelDeploymentHistory,
    UploadSession,
    TrainingSession,
    ModelClassification,
    ModelDetection,
    ModelClassificationDefect,
    ModelDetectionRegion,
    ModelDetectionRegionDefect,
    UserClassification,
    UserClassificationDefect,
    UserDetection,
    UserDetectionRegion,
    UserDetectionRegionDefect,
    UseCaseDefect,
    GTClassification,
    GTDetection,
    WaferMap,
)
from apps.classif_ai.serializers import FileSetCreateSerializer
from common.services import S3Service
from sixsense import settings
from sixsense.settings import (
    GF7_DATA_PREP_PATH,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_STORAGE_BUCKET_NAME,
    INFERENCE_METHOD,
    INFERENCE_QUEUE,
)

logger = logging.getLogger(__name__)


class FileRegionService:
    def find_matching_region(self, source_regions, target_region, model_type):
        matching_region = None
        for source_region in source_regions:
            if model_type == "CLASSIFICATION":
                if list(target_region.defects)[0] == list(source_region.defects)[0]:
                    matching_region = [source_region, None]
            else:
                iou = calculate_iou(
                    [
                        source_region.region["coordinates"]["x"],
                        source_region.region["coordinates"]["y"],
                        source_region.region["coordinates"]["x"] + source_region.region["coordinates"]["w"],
                        source_region.region["coordinates"]["y"] + source_region.region["coordinates"]["h"],
                    ],
                    [
                        target_region.region["coordinates"]["x"],
                        target_region.region["coordinates"]["y"],
                        target_region.region["coordinates"]["x"] + target_region.region["coordinates"]["w"],
                        target_region.region["coordinates"]["y"] + target_region.region["coordinates"]["h"],
                    ],
                )
                if iou > FileRegion.IOU_THRESHOLD_FOR_DETECTION_CORRECTNESS:
                    if matching_region:
                        if matching_region[1] < iou:
                            matching_region = [source_region, iou]
                    else:
                        matching_region = [source_region, iou]
        if matching_region:
            return matching_region[0]


class CopyFeedbackService:
    def __init__(self, from_ml_model_ids, to_ml_model_id):
        self.from_ml_model_ids = from_ml_model_ids
        self.to_ml_model_id = to_ml_model_id

    def copy(self, file_set_id):
        analysis_service = AnalysisService(
            file_set_filters={"id__in": [file_set_id]}, ml_model_filters={"id__in": self.from_ml_model_ids}
        )
        to_model_analysis_service = AnalysisService(
            file_set_filters={"id__in": [file_set_id]}, ml_model_filters={"id__in": [self.to_ml_model_id]}
        )
        all_gt_regions = analysis_service.gt_regions().order_by("-updated_ts")
        model_type = MlModel.objects.get(id=self.to_ml_model_id).type
        if all_gt_regions.first():
            if all_gt_regions.first().ml_model_id == self.to_ml_model_id:
                return
            # What if there are ai regions which were marked as correct because of the
            # all_gt_regions.filter(ml_model_id=self.to_ml_model_id, is_user_feedback=True) regions?
            for reg in to_model_analysis_service.gt_regions().filter(ml_model_id=self.to_ml_model_id):
                if reg.is_user_feedback is True:
                    reg.is_removed = True
                    reg.save()
                else:
                    reg.is_removed = False
                    reg.classification_correctness = None
                    reg.detection_correctness = None
                    reg.save()

            source_gt_regions = all_gt_regions.filter(ml_model_id=all_gt_regions.first().ml_model_id)
            for source_gt_region in source_gt_regions:
                target_gt_region = FileRegion(
                    ml_model_id=self.to_ml_model_id,
                    file_id=source_gt_region.file_id,
                    defects=source_gt_region.defects,
                    region=source_gt_region.region,
                    is_user_feedback=True,
                )
                target_ai_regions = FileRegion.objects.filter(
                    is_user_feedback=False, ml_model_id=self.to_ml_model_id, file_id=source_gt_region.file_id
                )
                matching_region = FileRegionService().find_matching_region(
                    target_ai_regions, target_gt_region, model_type
                )
                if matching_region and model_type == "CLASSIFICATION":
                    matching_region.classification_correctness = True
                    matching_region.save()
                elif matching_region:
                    if (
                        is_same_region(target_gt_region.region, matching_region.region)
                        and target_gt_region.defects.keys() == matching_region.defects.keys()
                    ):
                        matching_region.classification_correctness = True
                        matching_region.detection_correctness = True
                        matching_region.save()
                    else:
                        target_gt_region.ai_region = matching_region
                        target_gt_region.save()
                else:
                    target_gt_region.save()
            extra_target_ai_regions = FileRegion.objects.filter(
                detection_correctness__isnull=True,
                classification_correctness__isnull=True,
                is_user_feedback=False,
                ml_model_id=self.to_ml_model_id,
                file__in=File.objects.filter(file_set_id=file_set_id),
            )
            for region in extra_target_ai_regions:
                if model_type == "CLASSIFICATION":
                    region.classification_correctness = False
                    region.is_removed = True
                    region.save()
                else:
                    region.detection_correctness = False
                    region.classification_correctness = False
                    region.is_removed = True
                    region.save()


class InferenceService:
    def __init__(self, ml_model_id: int, file_set_id: int):
        self.ml_model_id = ml_model_id
        self.file_set_id = file_set_id
        self._file_set = None
        self._ml_model = None
        self._file_set_inference_queue = None

    def file_set(self):
        if self._file_set:
            return self._file_set
        self._file_set: FileSet = (
            FileSet.objects.select_related("wafer")
            .defer("wafer__meta_data", "wafer__coordinate_meta_info")
            .get(id=self.file_set_id)
        )
        return self._file_set

    def ml_model(self):
        if self._ml_model:
            return self._ml_model
        self._ml_model: MlModel = MlModel.objects.filter(id=self.ml_model_id).prefetch_related("use_case").first()
        return self._ml_model

    def file_set_inference_queue(self):
        if self._file_set_inference_queue:
            return self._file_set_inference_queue
        self._file_set_inference_queue: FileSetInferenceQueue = (
            self.file_set()
            .file_set_inference_queues.filter(ml_model_id=self.ml_model_id)
            .exclude(status="FAILED")
            .first()
        )
        return self._file_set_inference_queue

    def update_queue_status(self, status: str, inference_id: str = None):
        queue = self.file_set_inference_queue()
        queue.status = status
        if inference_id is not None:
            queue.inference_id = inference_id
        # ToDo: Sai try catch block here is added for debugging purpose. It should be removed asap
        try:
            queue.save()
        except Exception as e:
            logger.error("Could not update the status of file set inference queue with ID: " + str(queue.id))
            raise e

    def predict(self):
        ml_model = self.ml_model()
        file_set_data = FileSetCreateSerializer(instance=self.file_set())
        logger.info(f"Model Input: {file_set_data.data}")
        # TODO: Remove this when possible.
        if ml_model.code == "bottom_lead" and ml_model.version == 2:
            model_output: dict = requests.post(
                settings.BOTTOM_LEAD_INFERENCE_LINK,
                data=json.dumps(file_set_data.data),
                headers={"Content-Type": "application/json"},
            ).json()
        else:
            if (
                MlModel.models.get(connection.tenant.schema_name, None) is None
                or MlModel.models[connection.tenant.schema_name].get(ml_model.id, None) is None
            ):
                MlModel.load_model(ml_model.id)
            model_output: dict = MlModel.models[connection.tenant.schema_name][ml_model.id].predict(file_set_data.data)
        logger.info("model Output:")
        logger.info(model_output)
        return model_output

    def create_classification_ml_model_annotations(self, model_output: dict):
        for file in model_output["files"]:
            is_no_defect = False
            if len(file["file_regions"]) == 0:
                is_no_defect = True
            classification = ModelClassification.objects.create(
                file_id=file["id"], ml_model_id=self.ml_model_id, is_no_defect=is_no_defect
            )
            for file_region in file["file_regions"]:
                for defect_id, info in file_region["defects"].items():
                    saved_classification = ModelClassificationDefect.objects.create(
                        classification=classification, defect_id=defect_id, confidence=info["confidence"]
                    )
                    organization_defect_code = saved_classification.defect.organization_defect_code
                    if organization_defect_code:
                        file_region["defects"][defect_id]["organization_defect_code"] = organization_defect_code
        return model_output

    def create_detection_ml_model_annotations(self, model_output: dict):
        for file in model_output["files"]:
            is_no_defect = False
            if len(file["file_regions"]) == 0:
                is_no_defect = True
            detection = ModelDetection.objects.create(
                file_id=file["id"], ml_model_id=self.ml_model_id, is_no_defect=is_no_defect
            )
            for file_region in file["file_regions"]:
                coordinates = file_region["region"]["coordinates"]
                minx = coordinates["x"]
                miny = coordinates["y"]
                maxx = coordinates["x"] + coordinates["w"]
                maxy = coordinates["y"] + coordinates["h"]
                detection_region = ModelDetectionRegion.objects.create(
                    detection=detection,
                    region=Polygon(
                        ((minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny), (minx, miny)),
                    ),
                    model_output_meta_info=file_region.get("model_output_meta_info", {}),
                )
                for defect_id, info in file_region["defects"].items():
                    saved_detection_defect = ModelDetectionRegionDefect.objects.create(
                        detection_region=detection_region, defect_id=defect_id, confidence=info["confidence"]
                    )
                    organization_defect_code = saved_detection_defect.defect.organization_defect_code
                    if organization_defect_code:
                        file_region["defects"][defect_id]["organization_defect_code"] = organization_defect_code

        return model_output

    def validate(self):
        if self.file_set_inference_queue() is None:
            raise ValidationError(
                {"FileSetInferenceQueue": "FileSetInferenceQueue for the given model and file set doesn't exist"}
            )
        if self.file_set_inference_queue().status != "PENDING":
            raise ValidationError({"file": "This file was already inferenced with the required model."})

    def validate_model_output(self, model_output: dict):
        for file in model_output["files"]:
            if len(file["file_regions"]) > 1:
                if self.ml_model().classification_type == "SINGLE_LABEL":
                    raise ValidationError("Can't insert multiple defects for a single label use case.")

    def create_sagemaker_request_file_in_s3(self):
        file_set_serializer = FileSetCreateSerializer(instance=self.file_set())
        body = {
            "file_set": file_set_serializer.data,
            "ml_model": {
                "id": self.ml_model_id,
                "classification_type": self.ml_model().classification_type,
                "type": self.ml_model().type,
                "name": self.ml_model().name,
            },
            "creds": {"bucket": AWS_STORAGE_BUCKET_NAME},
        }
        s3_key = os.path.join(
            settings.MEDIA_ROOT,
            connection.tenant.schema_name,
            "inference_requests",
            str(self.file_set_id),
            str(self.ml_model_id),
            str(uuid.uuid1().hex),
        )
        s3_service = S3Service()
        temp_file = tempfile.NamedTemporaryFile()
        with open(temp_file.name, "w") as fp:
            json.dump(body, fp)
        s3_service.upload_file(temp_file.name, s3_key)
        return s3_key

    def perform_sagemaker_async_inference(self):
        file_set_serializer = FileSetCreateSerializer(instance=self.file_set())
        file_set_data = file_set_serializer.data
        body = {
            "file_set": file_set_data,
            "ml_model": {
                "id": self.ml_model_id,
                "classification_type": self.ml_model().classification_type,
                "type": self.ml_model().type,
                "name": self.ml_model().name,
                "url": self.ml_model().artifact_path,
                "endpoint": self.ml_model().inference_endpoint,
            },
            "file_set_inference_queue_id": self.file_set_inference_queue().id,
            "creds": {"bucket": AWS_STORAGE_BUCKET_NAME},
            "defect_pattern_info": self.file_set().wafer.defect_pattern_info if self.file_set().wafer else None,
        }
        # ToDo: Use celery signature to push the message instead of manually creating the message
        message = create_celery_format_message("main.run_inference", args=[json.dumps(body)])
        client = boto3.client("sqs", region_name=INFERENCE_QUEUE_REGION)
        try:
            resp = client.send_message(
                QueueUrl=INFERENCE_QUEUE,
                MessageBody=message,
            )
            self.update_queue_status(status="PROCESSING", inference_id=resp["MessageId"])
        except (client.exceptions.InvalidMessageContents, client.exceptions.UnsupportedOperation) as e:
            self.update_queue_status("FAILED")
            raise
        # broker_config = {
        #     # 'broker_url': f"sqs://{AWS_ACCESS_KEY_ID}:{AWS_SECRET_ACCESS_KEY}@",
        #     'broker_url': "sqs://",
        #     "broker_transport_options": {
        #         "region": INFERENCE_QUEUE_REGION,
        #         "predefined_queues": {
        #             "celery": {
        #                 "access_key_id": AWS_ACCESS_KEY_ID,
        #                 "secret_access_key": AWS_SECRET_ACCESS_KEY,
        #                 "url": INFERENCE_QUEUE,
        #                 "region": INFERENCE_QUEUE_REGION,
        #             }
        #         }
        #     }
        # }
        # inference_celery_app = Celery('__main__')
        # inference_celery_app.conf.update(broker_config)
        # run_inference = inference_celery_app.signature("main.run_inference")
        # run_inference.delay(json.dumps(body))
        # try:
        #     r = requests.post(
        #         INFERENCE_ASYNC_SELF_HOSTED_URL,
        #         data=json.dumps(body),
        #         headers={"Content-Type": "application/json"}
        #     )
        #     r.raise_for_status()
        #     response = r.json()
        #     self.update_queue_status(status="PROCESSING")
        #     return response
        # except requests.exceptions.RequestException as e:
        #     self.update_queue_status("FAILED")
        #     raise

    # def perform_sagemaker_async_inference(self):
    #     s3_key = self.create_sagemaker_request_file_in_s3()
    #     input_location = f"s3://{AWS_STORAGE_BUCKET_NAME}/{s3_key}"
    #     inference_endpoint = self.ml_model().inference_endpoint
    #     sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=self.ml_model().inference_endpoint_region)
    #     try:
    #         inference_id, _ = sagemaker_runtime.invoke_endpoint_async(
    #             EndpointName=inference_endpoint, InputLocation=input_location
    #         )
    #         self.update_queue_status(status="PROCESSING", inference_id=inference_id)
    #     except (
    #         sagemaker_runtime.exceptions.InternalFailure,
    #         sagemaker_runtime.exceptions.ServiceUnavailable,
    #         sagemaker_runtime.exceptions.ValidationError,
    #     ) as exc:
    #         self.update_queue_status("FAILED")
    #         raise

    def perform(self):
        self.validate()
        if INFERENCE_METHOD == "SAGEMAKER_ASYNC":
            self.perform_sagemaker_async_inference()
        else:
            self.update_queue_status("PROCESSING")
            try:
                model_output = self.predict()
                self.validate_model_output(model_output)
                with transaction.atomic():
                    if self.ml_model().type == "CLASSIFICATION":
                        model_output = self.create_classification_ml_model_annotations(model_output)
                    else:
                        model_output = self.create_detection_ml_model_annotations(model_output)
                    self.update_queue_status("FINISHED")
                    if IMAGE_HANDLER_QUEUE_URL:
                        model_output["type"] = "model_inference"
                        transaction.on_commit(lambda: inference_output_queue(model_output))
            except Exception as e:
                self.update_queue_status("FAILED")
                raise e


class AnalysisService:
    def __init__(self, file_set_filters=None, ml_model_filters=None, auto_model=False):
        self._auto_model = auto_model
        self.file_set_filters = file_set_filters
        self.ml_model_filters = ml_model_filters
        self._file_sets = None
        self._file_sets_model_filtered = None
        self._file_sets_with_feedback = None
        self._files = None
        self._ml_models = None
        self._file_regions = None
        self._ai_regions = None
        self._ai_regions_with_feedback = None
        self._true_positives_count = None
        self._false_negatives_count = None
        self._false_positives_count = None
        self._gt_regions = None
        self._detected_file_regions = None
        self._overall_metrics = None

    def file_sets(self, filter_models=False):
        """gets the distinct collection of file_set based on pre-defined filter criteria.
        If the fileset is pre-calculated, then that is used

        Args:
            filter_models (bool, optional): True implies filesets of ml models should be used. Defaults to False.

        Returns:
            [FileSet]: collection of file_set
        """
        if self._file_sets is not None:
            return self._file_sets
        # file_set_filters = dict((k, v.split(',')) for k, v in self.file_set_filters.items())
        file_set_query = build_query(self.file_set_filters)
        self._file_sets = FileSet.objects.filter(file_set_query)
        if filter_models:
            self._file_sets = self._file_sets.filter(files__file_regions__ml_model__in=self.ml_models())
        self._file_sets = self._file_sets.distinct()
        return self._file_sets

    def file_sets_filtered_by_models(self):
        if self._file_sets_model_filtered is not None:
            return self._file_sets_model_filtered
        file_set_query = build_query(self.file_set_filters)
        self._file_sets_model_filtered = (
            FileSet.objects.filter(file_set_query)
            .filter(files__file_regions__ml_model__in=self.ml_models())
            .distinct()
        )
        return self._file_sets_model_filtered

    def file_sets_with_feedback(self):
        if self._file_sets_with_feedback is not None:
            return self._file_sets_with_feedback
        feedback_filter = (
            Q(detection_correctness__isnull=False)
            | Q(classification_correctness__isnull=False)
            | (Q(is_user_feedback=True) & Q(is_removed=False))
        )
        file_regions_with_feedback = self.file_regions().filter(feedback_filter)
        self._file_sets_with_feedback = FileSet.objects.filter(
            files__file_regions__in=file_regions_with_feedback
        ).distinct()
        return self._file_sets_with_feedback

    def files(self, filter_models=False):
        """gets the distinct collection of file based on pre-defined filter criteria.
        If the file is pre-calculated, then that is used

        Args:
            filter_models (bool, optional): True implies files of ml models should be used. Defaults to False.

        Returns:
            [File]: collection of file
        """
        if self._files is not None:
            return self._files
        # file_query = Q()
        # if self.file_set_filters:
        #     file_filters = dict((f"file_set__{k}", v) for k, v in self.file_set_filters.items())
        #     file_query = build_query(file_filters)
        self._files = File.objects.filter(file_set__in=self.file_sets())
        if filter_models:
            self._files = self._files.filter(file_regions__ml_model__in=self.ml_models())
        self._files = self._files.distinct()
        return self._files

    def ml_models(self):
        if self._ml_models is not None:
            return self._ml_models
        model_query = Q()
        if self.ml_model_filters:
            # ml_model_filters = dict((k, v.split(',')) for k, v in self.ml_model_filters.items())
            model_query = build_query(self.ml_model_filters)
        self._ml_models = MlModel.objects.filter(model_query)
        return self._ml_models

    def get_auto_model_file_set_ids_map(self):
        file_set_model_ids = list(
            FileSetInferenceQueue.objects.filter(file_set__in=self.file_sets())
            .values("file_set_id")
            .annotate(model_ids=ArrayAgg("ml_model_id", ordering=("-created_ts")))
        )
        model_id_file_set_map = {}
        last_deployed_model = MlModelDeploymentHistory.objects.values_list("ml_model_id", flat=True).order_by(
            "-starts_at"
        )

        for ele in file_set_model_ids:
            for dep_model in last_deployed_model:
                if dep_model in ele["model_ids"]:
                    ele["model_id"] = dep_model
                    break
            else:
                ele["model_id"] = ele["model_ids"][0]

        for ele in file_set_model_ids:
            if model_id_file_set_map.get(ele["model_id"], None) is None:
                model_id_file_set_map[ele["model_id"]] = []
            model_id_file_set_map[ele["model_id"]].append(ele["file_set_id"])
        return model_id_file_set_map

    def file_regions(self):
        if self._file_regions is not None:
            return self._file_regions
        if not self._auto_model:
            self._file_regions = FileRegion.objects.filter(file__in=self.files(), ml_model__in=self.ml_models())
        else:
            filters = []
            model_id_file_set_map = self.get_auto_model_file_set_ids_map()
            for model_id, file_set_ids in model_id_file_set_map.items():
                file_set_ids = list(file_set_ids)
                filters.append((Q(ml_model_id=model_id) & Q(file__file_set_id__in=file_set_ids)))
            or_filters = reduce(ior, filters)
            self._file_regions = FileRegion.objects.filter(or_filters)

        return self._file_regions

    def ai_regions(self):
        if self._ai_regions is not None:
            return self._ai_regions
        self._ai_regions = self.file_regions().filter(is_user_feedback=False)
        return self._ai_regions

    def ai_regions_with_feedback(self):
        if self._ai_regions_with_feedback is not None:
            return self._ai_regions_with_feedback
        self._ai_regions_with_feedback = self.ai_regions().filter(
            Q(detection_correctness__isnull=False) | Q(classification_correctness__isnull=False)
        )
        return self._ai_regions_with_feedback

    def gt_regions(self):
        if self._gt_regions is not None:
            return self._gt_regions
        self._gt_regions = self.file_regions().filter(
            Q(
                Q(detection_correctness=True) | Q(classification_correctness=True),
                is_user_feedback=False,
                file_regions=None,
            )
            | Q(is_user_feedback=True, is_removed=False)
        )
        return self._gt_regions

    def detected_file_regions(self):
        if self._detected_file_regions is not None:
            return self._detected_file_regions
        ml_models_grouped_by_type = {}
        for ml_model in self.ml_models():
            if ml_models_grouped_by_type.get(ml_model.type, None) is None:
                ml_models_grouped_by_type[ml_model.type] = []
            ml_models_grouped_by_type[ml_model.type].append(ml_model.id)
        classification_and_detection_detected_file_regions = FileRegion.objects.none()
        classification_detected_file_regions = FileRegion.objects.none()
        for model_type, model_ids in ml_models_grouped_by_type.items():
            if model_type == "CLASSIFICATION_AND_DETECTION":
                classification_and_detection_detected_file_regions = (
                    self.file_regions()
                    .filter(
                        # Q(detection_correctness__isnull=True) &
                        # Q(classification_correctness__isnull=False) |
                        Q(detection_correctness=True)
                    )
                    .filter(ml_model_id__in=model_ids)
                )
            elif model_type == "CLASSIFICATION":
                classification_detected_file_regions = self.file_regions().filter(
                    classification_correctness__isnull=False
                )
        detected_file_regions = (
            classification_and_detection_detected_file_regions | classification_detected_file_regions
        )
        self._detected_file_regions = detected_file_regions
        return self._detected_file_regions

    def true_positives_count(self):
        if self._true_positives_count is not None:
            return self._true_positives_count
        # detected_file_regions = self.file_regions().filter(Q(detection_correctness__isnull=True) & Q(classification_correctness__isnull=False) | Q(detection_correctness=True))
        detected_file_regions = self.detected_file_regions()
        correctly_classified_defects = detected_file_regions.filter(classification_correctness=True).values("defects")
        self._true_positives_count = 0
        for defect in correctly_classified_defects:
            for _ in defect["defects"]:
                self._true_positives_count += 1
        incorrect_classified_regions = detected_file_regions.filter(classification_correctness=False)
        # ToDo: user_feedback_regions_for_incorrect_ai_regions should have a separate method as its used multiple times
        user_feedback_regions_for_incorrect_ai_regions = FileRegion.objects.filter(
            ai_region__in=incorrect_classified_regions
        )
        for region in user_feedback_regions_for_incorrect_ai_regions:
            for def_id in region.defects:
                if def_id in region.ai_region.defects:
                    self._true_positives_count += 1
        print("TP COUNT:" + str(self._true_positives_count))
        return self._true_positives_count

    def false_negatives_count(self):
        if self._false_negatives_count is not None:
            return self._false_negatives_count
        # calculate false negatives
        self._false_negatives_count = 0
        # detected_file_regions = self.file_regions().filter(Q(detection_correctness__isnull=True) & Q(classification_correctness__isnull=False) | Q(detection_correctness=True))
        ml_models_grouped_by_type = {}
        for ml_model in self.ml_models():
            if ml_models_grouped_by_type.get(ml_model.type, None) is None:
                ml_models_grouped_by_type[ml_model.type] = []
            ml_models_grouped_by_type[ml_model.type].append(ml_model.id)
        classification_and_detection_detected_file_regions = FileRegion.objects.none()
        classification_detected_file_regions = FileRegion.objects.none()
        for model_type, model_ids in ml_models_grouped_by_type.items():
            if model_type == "CLASSIFICATION_AND_DETECTION":
                classification_and_detection_detected_file_regions = (
                    self.file_regions()
                    .filter(
                        # Q(detection_correctness__isnull=True) &
                        # Q(classification_correctness__isnull=False) |
                        Q(detection_correctness=True)
                    )
                    .filter(ml_model_id__in=model_ids)
                )
            elif model_type == "CLASSIFICATION":
                classification_detected_file_regions = self.file_regions().filter(
                    Q(classification_correctness__isnull=False) | Q(is_user_feedback=True)
                )
        detected_file_regions = (
            classification_and_detection_detected_file_regions | classification_detected_file_regions
        )
        under_detected_regions = detected_file_regions.filter(ai_region__isnull=True, is_user_feedback=True).values(
            "defects"
        )
        for region in under_detected_regions:
            for def_id in region["defects"]:
                self._false_negatives_count += 1
        user_feedback_regions_for_incorrect_ai_regions = (
            self.file_regions()
            .filter(ai_region__in=FileRegion.objects.filter(classification_correctness=False))
            .select_related("ai_region")
        )
        for region in user_feedback_regions_for_incorrect_ai_regions:
            for def_id in region.defects:
                if def_id not in region.ai_region.defects:
                    self._false_negatives_count += 1
        print("FN COUNT:" + str(self._false_negatives_count))
        return self._false_negatives_count

    def false_positives_count(self):
        if self._false_positives_count is not None:
            return self._false_positives_count

        # calculate false positives
        self._false_positives_count = 0
        # detected_file_regions = self.file_regions().filter(Q(detection_correctness__isnull=True) & Q(classification_correctness__isnull=False) | Q(detection_correctness=True))
        ml_models_grouped_by_type = {}
        for ml_model in self.ml_models():
            if ml_models_grouped_by_type.get(ml_model.type, None) is None:
                ml_models_grouped_by_type[ml_model.type] = []
            ml_models_grouped_by_type[ml_model.type].append(ml_model.id)
        classification_and_detection_detected_file_regions = FileRegion.objects.none()
        classification_detected_file_regions = FileRegion.objects.none()
        for model_type, model_ids in ml_models_grouped_by_type.items():
            if model_type == "CLASSIFICATION_AND_DETECTION":
                classification_and_detection_detected_file_regions = (
                    self.file_regions()
                    .filter(
                        # Q(detection_correctness__isnull=True) &
                        # Q(classification_correctness__isnull=False) |
                        Q(detection_correctness=True)
                    )
                    .filter(ml_model_id__in=model_ids)
                )
            elif model_type == "CLASSIFICATION":
                classification_detected_file_regions = self.file_regions().filter(
                    classification_correctness__isnull=False
                )
        # detected_file_regions = classification_and_detection_detected_file_regions | classification_detected_file_regions
        incorrect_classified_combined_file_regions = classification_and_detection_detected_file_regions.filter(
            classification_correctness=False
        )
        incorrect_classified_classification_file_regions = classification_detected_file_regions.filter(
            classification_correctness=False
        )
        self._false_positives_count = incorrect_classified_classification_file_regions.count()
        for region in incorrect_classified_combined_file_regions:
            for def_id in region.defects:
                try:
                    if def_id not in region.file_regions.first().defects:
                        self._false_positives_count += 1
                except:
                    continue
        # ff = detected_file_regions.filter(classification_correctness=False)
        # detected_file_region_ids = []
        # for fr in ff:
        #     detected_file_region_ids.append(fr.id)
        # if model_type == 'CLASSIFICATION_AND_DETECTION':
        #     for region in ff:
        #         for def_id in region.defects:
        #             try:
        #                 if def_id not in region.file_regions.first().defects:
        #                     self._false_positives_count += 1
        #             except:
        #                 continue
        # elif model_type == 'CLASSIFICATION':
        #     self._false_positives_count = ff.count()
        print("FP COUNT:" + str(self._false_positives_count))
        return self._false_positives_count

    def true_negatives_count(self):
        all_defect_ids = (
            self.detected_file_regions()
            .annotate(defect_ids=JsonKeys("defects"))
            .values_list("defect_ids", flat=True)
            .distinct()
        )
        true_negatives = 0
        for defect_id in all_defect_ids:
            true_negatives += (
                self.detected_file_regions()
                .filter(classification_correctness=True)
                .exclude(defects__has_key=str(defect_id))
                .annotate(defect_ids=JsonKeys("defects"))
                .count()
            )

            true_negatives += (
                self.detected_file_regions()
                .filter(is_user_feedback=True)
                .exclude(defects__has_key=str(defect_id), ai_region__defects__has_key=str(defect_id))
                .annotate(defect_ids=JsonKeys("defects"))
                .count()
            )

        return true_negatives

    def classification_accuracy(self):
        if self.ml_models().count() > 1:
            return "N/A"
        if self.ml_models()[0].classification_type == "MULTI_LABEL":
            try:
                return round(
                    ((self.true_positives_count() + self.true_negatives_count()) * 100)
                    / (
                        self.true_positives_count()
                        + self.true_negatives_count()
                        + self.false_negatives_count()
                        + self.false_positives_count()
                    ),
                    2,
                )
            except ZeroDivisionError as e:
                return "N/A"
        elif self.ml_models()[0].classification_type == "SINGLE_LABEL":
            try:
                return round(
                    (self.detected_file_regions().filter(classification_correctness=True).count() * 100)
                    / self.detected_file_regions().count()
                )
            except ZeroDivisionError as e:
                return "N/A"
        else:
            return "N/A"

    def total_ai_region_count(self):
        return self.ai_regions_with_feedback().filter(detection_correctness__isnull=False).count()

    def new_region_count(self):
        return self.file_regions().filter(ai_region__isnull=True, is_user_feedback=True, is_removed=False).count()

    def correct_detection_count(self):
        return self.file_regions().filter(detection_correctness=True).count()

    def ground_truth_count(self):
        return (
            self.file_regions().filter(detection_correctness=True, is_user_feedback=False, file_regions=None).count()
            + self.file_regions().filter(is_user_feedback=True, is_removed=False).count()
        )

    def detection_accuracy(self):
        try:
            return round(
                (100 * self.correct_detection_count()) / (self.total_ai_region_count() + self.new_region_count()), 2
            )
        except ZeroDivisionError as e:
            return "N/A"

    def overall_accuracy(self):
        ai_defects = self.ai_regions_with_feedback().values_list("defects", flat=True)
        total_defects_count = 0
        for defect in ai_defects:
            total_defects_count += len(defect.keys())
        new_region_defects = (
            self.file_regions()
            .filter(ai_region__isnull=True, is_user_feedback=True, is_removed=False)
            .values_list("defects", flat=True)
        )
        for defect in new_region_defects:
            total_defects_count += len(defect.keys())
        modified_regions = (
            self.file_regions()
            .filter(ai_region__isnull=False, is_user_feedback=True, is_removed=False)
            .select_related("ai_region")
        )
        for region in modified_regions:
            for defect_id in region.defects.keys():
                if defect_id not in region.ai_region.defects:
                    total_defects_count += 1

        try:
            return round((100 * self.true_positives_count()) / (total_defects_count), 2)
        except ZeroDivisionError as e:
            return "N/A"

    def class_wise_matrix_data(self):
        # model_type = MlModel.objects.get(id=ml_model_ids[0]).type
        defects = Defect.objects.filter(ml_models__in=self.ml_models())
        data = []
        for defect in defects:
            true_positives_count = self.true_positive_file_regions_for_defect(defect.id).count()
            false_positives_count = self.false_positive_file_regions_for_defect(defect.id).count()
            false_negatives_count = self.false_negative_file_regions_for_defect(defect.id).count()
            try:
                precision = true_positives_count / (true_positives_count + false_positives_count)
                precision = round(precision * 100, 2)
                recall = true_positives_count / (true_positives_count + false_negatives_count)
                recall = round(recall * 100, 2)
            except ZeroDivisionError as e:
                precision = None
                recall = None
            data.append(
                {
                    "defect": {"id": defect.id, "name": defect.name},
                    "true_positives": {"count": true_positives_count, "file_set_ids": []},
                    "false_positives": {"count": false_positives_count, "file_set_ids": []},
                    "false_negatives": {"count": false_negatives_count, "file_set_ids": []},
                    "precision": precision,
                    "recall": recall,
                }
            )
        return data
        # if model_type == 'CLASSIFICATION':
        #     for defect in defects:
        #         true_positives = File.objects.filter(file_regions__in=file_regions.filter(
        #             defects__has_key=str(defect.id), classification_correctness=True, is_user_feedback=False
        #         ))
        #         true_positives_count = true_positives.count()
        #         tp_file_set_ids = list(true_positives.values_list('file_set_id', flat=True).distinct())
        #         false_positives = File.objects.filter(file_regions__in=file_regions.filter(
        #             defects__has_key=str(defect.id), classification_correctness=False, is_user_feedback=False
        #         ))
        #         false_positives_count = false_positives.count()
        #         fp_file_set_ids = list(false_positives.values_list('file_set_id', flat=True).distinct())
        #
        #         fn_file_ids = []
        #         # false_negatives = File.objects.filter(file_regions__in=file_regions.filter(
        #         #     defects__has_key=str(defect.id), is_user_feedback=True, is_removed=False
        #         # ))
        #         # for fn_file in false_negatives:
        #         #     for fr in fn_file.file_regions.all():
        #         #         if not fr.classification_correctness:
        #         #             fn_file_ids.append(fn_file.id)
        #         # false_negatives = File.objects.filter(id__in=fn_file_ids)
        #         # false_negatives_count = false_negatives.count()
        #         false_negatives = File.objects.filter(
        #             file_regions__in=file_regions.filter(
        #                 ~Q(ai_region__defects__has_key=str(defect.id)),
        #                 is_user_feedback=True, is_removed=False,
        #                 defects__has_key=str(defect.id),
        #             )
        #         )
        #         false_negatives_count = false_negatives.count()
        #         fn_file_set_ids = list(false_negatives.values_list('file_set_id', flat=True).distinct())
        #
        #         try:
        #             precision = true_positives.count() / (true_positives.count() + false_positives.count())
        #             precision = round(precision * 100, 2)
        #             recall = true_positives.count() / (true_positives.count() + false_negatives.count())
        #             recall = round(recall * 100, 2)
        #         except ZeroDivisionError as e:
        #             precision = None
        #             recall = None
        #
        #         data.append(
        #             {
        #                 "defect": {
        #                     "id": defect.id,
        #                     "name": defect.name
        #                 },
        #                 "true_positives": {"count": true_positives_count, "file_set_ids": tp_file_set_ids},
        #                 "false_positives": {"count": false_positives_count, "file_set_ids": fp_file_set_ids},
        #                 "false_negatives": {"count": false_negatives_count, "file_set_ids": fn_file_set_ids},
        #                 "precision": precision,
        #                 "recall": recall
        #             }
        #         )
        #
        # if model_type == 'CLASSIFICATION_AND_DETECTION':
        #     for defect in defects:
        #         true_positives = file_regions.filter(
        #             defects__has_key=str(defect.id),
        #             classification_correctness=True,
        #             is_user_feedback=False,
        #             detection_correctness=True
        #         )
        #         true_positives_count = true_positives.count()
        #         tp_file_set_ids = list(true_positives.values_list('file__file_set_id', flat=True))
        #
        #         false_positives = file_regions.filter(
        #             defects__has_key=str(defect.id),
        #             classification_correctness=False,
        #             is_user_feedback=False,
        #             detection_correctness=True
        #         )
        #         false_positives_count = 0
        #         fp_file_set_ids = set()
        #         for false_positive in false_positives:
        #             if str(defect.id) not in false_positive.file_regions.first().defects:
        #                 false_positives_count += 1
        #                 fp_file_set_ids.add(false_positive.file.file_set_id)
        #         # false_positives_count = false_positives.count()
        #         # fp_file_set_ids = list(false_positives.values_list('file__file_set_id', flat=True))
        #         fp_file_set_ids = list(fp_file_set_ids)
        #
        #         # ToDo: Definition of false negatives should change. We should calculate class wise matrix only
        #         #  on correctly detected regions
        #         false_negatives = file_regions.filter(
        #             ~Q(ai_region__defects__has_key=str(defect.id)),
        #             defects__has_key=str(defect.id),
        #             is_user_feedback=True,
        #             is_removed=False,
        #             ai_region__isnull=False
        #         )
        #         false_negatives_count = false_negatives.count()
        #         fn_file_set_ids = list(false_negatives.values_list('file__file_set_id', flat=True))
        #
        #         try:
        #             precision = true_positives.count() / (true_positives.count() + false_positives.count())
        #             precision = round(precision * 100, 2)
        #             recall = true_positives.count() / (true_positives.count() + false_negatives.count())
        #             recall = round(recall * 100, 2)
        #         except ZeroDivisionError as e:
        #             precision = None
        #             recall = None
        #
        #         data.append(
        #             {
        #                 "defect": {
        #                     "id": defect.id,
        #                     "name": defect.name
        #                 },
        #                 "true_positives": {"count": true_positives_count, "file_set_ids": tp_file_set_ids},
        #                 "false_positives": {"count": false_positives_count, "file_set_ids": fp_file_set_ids},
        #                 "false_negatives": {"count": false_negatives_count, "file_set_ids": fn_file_set_ids},
        #                 "precision": precision,
        #                 "recall": recall
        #             }
        #         )
        #
        # return data

    def calculate_yield_loss(self, imp_defects):
        # ToDo: Based on self.file_sets(), Group all file sets based on the machine.
        # Count number of file_sets rejected by AI?
        machine_defective_file_set_counts = (
            self.file_sets()
            .filter(
                files__file_regions__is_user_feedback=False,
                files__file_regions__defects__has_any_keys=imp_defects,
                meta_info__lot_id__isnull=False,
                meta_info__InitialTotal__isnull=False,
                meta_info__has_keys=["InitialTotal", "lot_id"],
            )
            .values("meta_info__MachineNo")
            .annotate(total=Count("id", distinct=True))
        )
        machine_lot_total_pass = (
            self.file_sets()
            .filter(
                file_set_inference_queues__status="FINISHED",
                meta_info__lot_id__isnull=False,
                meta_info__InitialTotal__isnull=False,
                meta_info__has_keys=["InitialTotal", "lot_id"],
            )
            .values("meta_info__MachineNo", "meta_info__lot_id")
            .annotate(initial_total=Min(KeyTextTransform("InitialTotal", "meta_info")))
        )
        machine_total_pass = {}
        for el in machine_lot_total_pass:
            if machine_total_pass.get(el["meta_info__MachineNo"], None) is None:
                machine_total_pass[el["meta_info__MachineNo"]] = 0
            machine_total_pass[el["meta_info__MachineNo"]] += int(el["initial_total"])
        yield_loss = {}
        for el in machine_defective_file_set_counts:
            yield_loss[el["meta_info__MachineNo"]] = {
                "percentage": round((100 * el["total"]) / machine_total_pass[el["meta_info__MachineNo"]], 2),
                "ai_reject_count": el["total"],
                "total_unit_count": machine_total_pass[el["meta_info__MachineNo"]],
            }
        return yield_loss

    def yield_loss_trend_grouped_by_defect(self, defect_id_map, imp_defects, time_format="daily", priority=False):
        defective_file_sets = (
            self.file_sets()
            .filter(
                files__file_regions__defects__has_any_keys=imp_defects,
                meta_info__lot_id__isnull=False,
                meta_info__InitialTotal__isnull=False,
                meta_info__has_keys=["InitialTotal", "lot_id"],
                files__file_regions__is_user_feedback=False,
            )
            .values("id")
            .annotate(defect=JsonKeys("files__file_regions__defects"))
            .distinct()
        )

        distinct_initial_total = (
            self.file_sets()
            .filter(
                file_set_inference_queues__status="FINISHED",
                meta_info__InitialTotal__isnull=False,
                meta_info__has_keys=["InitialTotal"],
            )
            .values("meta_info__lot_id", "meta_info__InitialTotal")
            .distinct()
        )

        if time_format == "monthly":
            defective_file_sets = defective_file_sets.annotate(time_val=TruncMonth("created_ts"))
            distinct_initial_total = distinct_initial_total.annotate(time_val=TruncMonth("created_ts"))
        elif time_format == "weekly":
            defective_file_sets = defective_file_sets.annotate(time_val=TruncWeek("created_ts"))
            distinct_initial_total = distinct_initial_total.annotate(time_val=TruncWeek("created_ts"))
        else:
            defective_file_sets = defective_file_sets.annotate(time_val=TruncDay("created_ts"))
            distinct_initial_total = distinct_initial_total.annotate(time_val=TruncDay("created_ts"))

        defective_file_sets = list(defective_file_sets)
        time_val_initial_total = {}
        for obj in distinct_initial_total:
            time_val = obj["time_val"]
            if time_val not in time_val_initial_total:
                time_val_initial_total[time_val] = 0
            time_val_initial_total[time_val] += int(obj["meta_info__InitialTotal"])

        defect_time_val_file_sets = {}
        file_set_id_defect_ids = {}

        ordered_defect_ids = get_env().list("ORDERED_DEFECT_IDS", cast=int, default=[1, 2, 4, 5, 3, 6])

        ordered_defect_ids = ordered_defect_ids + list(
            Defect.objects.exclude(id__in=ordered_defect_ids).order_by("created_ts").values_list("id", flat=True)
        )

        if priority:
            for obj in defective_file_sets:
                if obj["id"] not in file_set_id_defect_ids:
                    file_set_id_defect_ids[obj["id"]] = set()
                file_set_id_defect_ids[obj["id"]].add(int(obj["defect"]))
            for file_set_id, defect_ids in file_set_id_defect_ids.items():
                for defect_id in ordered_defect_ids:
                    if defect_id in defect_ids:
                        defect_ids.remove(defect_id)
                        break
                for i, obj in enumerate(defective_file_sets):
                    if obj["id"] == file_set_id and int(obj["defect"]) in defect_ids:
                        defective_file_sets.pop(i)

        for obj in defective_file_sets:
            defect_id = int(obj["defect"])
            if defect_id in defect_id_map:
                time_val = obj["time_val"]
                if defect_id not in defect_time_val_file_sets:
                    defect_time_val_file_sets[defect_id] = {}
                    defect_time_val_file_sets[defect_id][time_val] = [obj["id"]]
                else:
                    if time_val not in defect_time_val_file_sets[defect_id]:
                        defect_time_val_file_sets[defect_id][time_val] = [obj["id"]]
                    else:
                        defect_time_val_file_sets[defect_id][time_val].append(obj["id"])

        response = {}

        for defect_id in defect_time_val_file_sets:
            if defect_id not in response:
                response[defect_id] = {"name": defect_id_map[defect_id]}
                for time_val in defect_time_val_file_sets[defect_id]:
                    num = len(defect_time_val_file_sets[defect_id][time_val])
                    den = time_val_initial_total[time_val]
                    percentage = round(num * 100 / den, 2)
                    time_str = convert_datetime_to_str(time_val, time_format)
                    response[defect_id][time_str] = {
                        "percentage": percentage,
                        "ai_reject_count": num,
                        "total_unit_count": den,
                    }

        return response

    def calculate_yield_loss_scatter_plot(self, imp_defects, time_format="daily"):
        machine_defective_file_set_counts = (
            self.file_sets()
            .filter(
                files__file_regions__is_user_feedback=False,
                files__file_regions__defects__has_any_keys=imp_defects,
                meta_info__lot_id__isnull=False,
                meta_info__InitialTotal__isnull=False,
                meta_info__has_keys=["InitialTotal", "lot_id"],
            )
            .values("meta_info__MachineNo", "meta_info__lot_id", "meta_info__InitialTotal")
            .annotate(total=Count("id", distinct=True))
        )

        # machine_lot_total_pass = self.file_sets().filter(
        #     files__file_regions__isnull=False,
        #     meta_info__lot_id__isnull=False, meta_info__InitialTotal__isnull=False,
        #     meta_info__has_keys=['InitialTotal', 'lot_id']
        # ).values(
        #     'meta_info__MachineNo', 'meta_info__lot_id', 'meta_info__InitialTotal'
        # ).distinct()

        if time_format == "monthly":
            machine_defective_file_set_counts = machine_defective_file_set_counts.annotate(
                time_val=TruncMonth("created_ts")
            )
            # machine_lot_total_pass = machine_lot_total_pass.annotate(time_val=TruncMonth('created_ts'))
        elif time_format == "weekly":
            machine_defective_file_set_counts = machine_defective_file_set_counts.annotate(
                time_val=TruncWeek("created_ts")
            )
            # machine_lot_total_pass = machine_lot_total_pass.annotate(time_val=TruncWeek('created_ts'))
        else:
            machine_defective_file_set_counts = machine_defective_file_set_counts.annotate(
                time_val=TruncDay("created_ts")
            )
            # machine_lot_total_pass = machine_lot_total_pass.annotate(time_val=TruncDay('created_ts'))

        machine_defective_file_set_counts = list(machine_defective_file_set_counts)
        # machine_lot_total_pass = list(machine_lot_total_pass)
        # seen_machine_lots = []
        #
        # for item in machine_lot_total_pass:
        #     machine_lot = (item['meta_info__MachineNo'], item['meta_info__lot_id'])
        #     if machine_lot in seen_machine_lots:
        #         machine_lot_total_pass.remove(item)
        #     seen_machine_lots.append(machine_lot)

        # machine_total_pass = {}
        # for el in machine_lot_total_pass:
        #     time_val = el['time_val']
        #     machine = el['meta_info__MachineNo']
        #     if machine_total_pass.get(time_val, None) is None:
        #         machine_total_pass[time_val] = [{machine: int(el['meta_info__InitialTotal'])}]
        #     else:
        #         try:
        #             idx = next(i for i, item in enumerate(machine_total_pass[time_val]) if machine in item)
        #             machine_total_pass[time_val][idx][machine] += int(el['meta_info__InitialTotal'])
        #         except StopIteration:
        #             machine_total_pass[time_val].append({machine : int(el['meta_info__InitialTotal'])})

        yield_loss = {}
        for el in machine_defective_file_set_counts:
            time_val = el["time_val"]
            time_str = convert_datetime_to_str(time_val, time_format)
            if yield_loss.get(time_str, None) is None:
                yield_loss[time_str] = []
            # machine = el['meta_info__MachineNo']
            # den = next(item['meta_info__InitialTotal']
            #            for item in machine_lot_total_pass if item['meta_info__lot_id'] == el['meta_info__lot_id'])
            yield_loss[time_str].append(
                {
                    "machine_no": el["meta_info__MachineNo"],
                    "lot_id": el["meta_info__lot_id"],
                    "percentage": round((100 * el["total"]) / int(el["meta_info__InitialTotal"]), 2),
                    "ai_reject_count": el["total"],
                    "total_unit_count": el["meta_info__InitialTotal"],
                }
            )
        return yield_loss

    def defect_v_count(self, defect_id, defect_name, machine, defect_v_count):
        if not any(item["id"] == defect_id for item in defect_v_count):
            defect_v_count.append(
                {"id": defect_id, "name": defect_name, "count_grouped_by_machine": [{"machine": machine, "count": 1}]}
            )
        else:
            result = next(item for _, item in enumerate(defect_v_count) if defect_id == item["id"])
            if not any(val["machine"] == machine for val in result["count_grouped_by_machine"]):
                result["count_grouped_by_machine"].append({"machine": machine, "count": 1})
            else:
                idx = next(
                    i for i, item in enumerate(result["count_grouped_by_machine"]) if item["machine"] == machine
                )
                result["count_grouped_by_machine"][idx]["count"] += 1
        return defect_v_count

    def timeseries_defect_count(self, time_val, defect_name, timeseries_data, machine):

        if defect_name not in timeseries_data:
            timeseries_data[defect_name] = {}
            timeseries_data[defect_name][time_val] = [{"machine": machine, "count": 1}]

        if defect_name in timeseries_data:
            if time_val in timeseries_data[defect_name]:
                for idx, val in enumerate(timeseries_data[defect_name][time_val]):
                    if machine in val.values():
                        timeseries_data[defect_name][time_val][idx]["count"] += 1
                        break
                else:
                    timeseries_data[defect_name][time_val].append({"machine": machine, "count": 1})
            else:
                timeseries_data[defect_name][time_val] = [{"machine": machine, "count": 1}]
        return timeseries_data

    def confusion_matrix(self, otrue_regions, opred_regions, defect_mapping):
        i = 0
        j = 0
        true_regions = []
        pred_regions = []
        while i < len(otrue_regions) and j < len(opred_regions):
            if otrue_regions[i]["file_id"] == opred_regions[j]["file_id"]:
                true_regions.append(otrue_regions[i])
                pred_regions.append(opred_regions[j])
                i += 1
                j += 1
            elif otrue_regions[i]["file_id"] > opred_regions[j]["file_id"]:
                j += 1
            else:
                i += 1

        result = {}

        for i in range(len(true_regions)):
            gt_defect_id = int(list(true_regions[i]["defects"].keys())[0])
            if not result.get(gt_defect_id, None):
                result[gt_defect_id] = {
                    "defect": defect_mapping[gt_defect_id],
                    "precision": 0,
                    "recall": 0,
                    "total_gt_count": 0,
                    "total_ai_predicted_count": 0,
                    "ai_predictions": {},
                }
            pred_defect_id = int(list(pred_regions[i]["defects"].keys())[0])
            if not result.get(pred_defect_id, None):
                result[pred_defect_id] = {
                    "defect": defect_mapping[pred_defect_id],
                    "precision": 0,
                    "recall": 0,
                    "total_gt_count": 0,
                    "total_ai_predicted_count": 0,
                    "ai_predictions": {},
                }
            if result[gt_defect_id]["ai_predictions"].get(pred_defect_id, None) is None:
                result[gt_defect_id]["ai_predictions"][pred_defect_id] = {
                    "defect": defect_mapping[pred_defect_id],
                    "count": 0,
                    "file_set_ids": [],
                }
            result[gt_defect_id]["ai_predictions"][pred_defect_id]["count"] += 1
            result[gt_defect_id]["ai_predictions"][pred_defect_id]["file_set_ids"].append(
                pred_regions[i]["file__file_set_id"]
            )
            result[gt_defect_id]["total_gt_count"] += 1
            result[pred_defect_id]["total_ai_predicted_count"] += 1

        for gt_defect_id in result:
            num = 0
            for defect_id in result[gt_defect_id]["ai_predictions"]:
                if defect_id == gt_defect_id:
                    num = result[gt_defect_id]["ai_predictions"][defect_id]["count"]
            try:
                result[gt_defect_id]["recall"] = round((num / result[gt_defect_id]["total_gt_count"]) * 100, 2)
            except ZeroDivisionError as e:
                result[gt_defect_id]["recall"] = "N/A"
            try:
                result[gt_defect_id]["precision"] = round(
                    (num / result[gt_defect_id]["total_ai_predicted_count"]) * 100, 2
                )
            except ZeroDivisionError as e:
                result[gt_defect_id]["precision"] = "N/A"

        return result

    def correct_detection_region_extra_label_count(self):
        extra_label_count = 0
        if self.ml_models()[0].type == "CLASSIFICATION":
            extra_label_count += (
                self.detected_file_regions()
                .prefetch_related("file_regions")
                .filter(classification_correctness=False)
                .count()
            )
        elif self.ml_models()[0].type == "CLASSIFICATION_AND_DETECTION":
            detected_file_regions = (
                self.detected_file_regions().prefetch_related("file_regions").filter(classification_correctness=False)
            )
            for detected_file_region in detected_file_regions:
                for defect_id in detected_file_region.defects.keys():
                    for child_region in detected_file_region.file_regions.all():
                        # Assuming there cannot be more than one valid child region
                        if child_region.is_removed:
                            next
                        if defect_id not in child_region.defects.keys():
                            extra_label_count += 1
        return extra_label_count

    def correct_detection_region_missed_label_count(self):
        missed_label_count = 0
        detected_file_regions = (
            self.detected_file_regions().prefetch_related("file_regions").filter(classification_correctness=False)
        )
        if self.ml_models()[0].type == "CLASSIFICATION":
            missed_label_count = self.gt_regions().filter(is_user_feedback=True).count()
        elif self.ml_models()[0].type == "CLASSIFICATION_AND_DETECTION":
            for detected_file_region in detected_file_regions:
                for child_region in detected_file_region.file_regions.all():
                    # Assuming there cannot be more than one valid child region
                    if child_region.is_removed:
                        next
                    for defect_id in child_region.defects.keys():
                        if defect_id not in child_region.defects.keys():
                            missed_label_count += 1
        return missed_label_count

    def overall_metrics(self):
        if self._overall_metrics is not None:
            return self._overall_metrics
        total_gt_labels = self.gt_regions().annotate(defect_id=JsonKeys("defects")).values("defect_id").count()
        try:
            percentage_defects_identified = round((100 * self.true_positives_count()) / total_gt_labels, 2)
        except ZeroDivisionError:
            percentage_defects_identified = "N/A"
        extra_count = self.correct_detection_region_extra_label_count()
        extra_count += (
            self.ai_regions()
            .filter(detection_correctness=False)
            .annotate(defect_id=JsonKeys("defects"))
            .values("defect_id")
            .count()
        )
        try:
            percentage_defects_extra = round(
                (100 * extra_count)
                / self.ai_regions_with_feedback().annotate(defect_id=JsonKeys("defects")).values("defect_id").count(),
                2,
            )
        except ZeroDivisionError:
            percentage_defects_extra = "N/A"
        # missed_count = self.correct_detection_region_missed_label_count()
        # if self.ml_models()[0].type == 'CLASSIFICATION_AND_DETECTION':
        #     missed_count += self.file_regions().filter(
        #         is_user_feedback=True,
        #         ai_region__isnull=True,
        #         is_removed=False
        #     ).annotate(defect_id=JsonKeys('defects')).values('defect_id').count()
        try:
            # percentage_defects_missed = round(
            #     (100 * missed_count) / total_gt_labels,
            #     2
            # )
            percentage_defects_missed = round(100 - percentage_defects_identified, 2)
        except (ZeroDivisionError, TypeError):
            percentage_defects_missed = "N/A"
        self._overall_metrics = {
            "percentage_defects_identified": percentage_defects_identified,
            "percentage_defects_extra": percentage_defects_extra,
            "percentage_defects_missed": percentage_defects_missed,
        }
        return self._overall_metrics

    def classification_metrics(self):
        total_gt_labels_in_detected_file_regions = (
            self.detected_file_regions()
            .filter(classification_correctness=True)
            .annotate(defect_id=JsonKeys("defects"))
            .values("defect_id")
            .count()
        )
        total_gt_labels_in_detected_file_regions += (
            FileRegion.objects.filter(
                ai_region__in=self.detected_file_regions().filter(classification_correctness=False)
            )
            .annotate(defect_id=JsonKeys("defects"))
            .values("defect_id")
            .count()
        )
        try:
            if self.ml_models()[0].type == "CLASSIFICATION":
                percentage_defects_identified = self.overall_metrics()["percentage_defects_identified"]
            elif self.ml_models()[0].type == "CLASSIFICATION_AND_DETECTION":
                percentage_defects_identified = round(
                    (100 * self.true_positives_count()) / total_gt_labels_in_detected_file_regions, 2
                )
            else:
                percentage_defects_identified = "N/A"
        except ZeroDivisionError:
            percentage_defects_identified = "N/A"
        try:
            percentage_defects_extra = round(
                (100 * self.correct_detection_region_extra_label_count())
                / self.detected_file_regions().annotate(defect_id=JsonKeys("defects")).values("defect_id").count()
            )
        except ZeroDivisionError:
            percentage_defects_extra = "N/A"
        try:
            percentage_defects_missed = round(100 - percentage_defects_identified, 2)
            # if self.ml_models()[0].type == "CLASSIFICATION":
            #     percentage_defects_missed = self.overall_metrics()["percentage_defects_missed"]
            # elif self.ml_models()[0].type == "CLASSIFICATION_AND_DETECTION":
            #     percentage_defects_missed = round(
            #         (100 * self.correct_detection_region_missed_label_count()) / total_gt_labels_in_detected_file_regions,
            #         2
            #     )
            # else:
            #     percentage_defects_missed = "N/A"
        except (ZeroDivisionError, TypeError):
            percentage_defects_missed = "N/A"
        return {
            "percentage_defects_identified": percentage_defects_identified,
            "percentage_defects_extra": percentage_defects_extra,
            "percentage_defects_missed": percentage_defects_missed,
        }

    def detection_metrics(self):
        try:
            percentage_regions_identified = round(
                (100 * self.detected_file_regions().count()) / self.gt_regions().count(), 2
            )
        except ZeroDivisionError:
            percentage_regions_identified = "N/A"
        try:
            percentage_regions_extra = round(
                (100 * self.file_regions().filter(detection_correctness=False).count())
                / self.ai_regions_with_feedback().count(),
                2,
            )
        except ZeroDivisionError:
            percentage_regions_extra = "N/A"
        try:
            percentage_regions_missed = round(100 - percentage_regions_identified, 2)
            # percentage_regions_missed = round(
            #     (
            #             100 * self.gt_regions().filter(is_user_feedback=True, ai_region__isnull=True, is_removed=False).count()
            #     ) / self.gt_regions().count(),
            #     2
            # )
        except (ZeroDivisionError, TypeError):
            percentage_regions_missed = "N/A"
        return {
            "percentage_regions_identified": percentage_regions_identified,
            "percentage_regions_extra": percentage_regions_extra,
            "percentage_regions_missed": percentage_regions_missed,
        }

    def true_positive_file_regions_for_defect(self, defect_id):
        detected_file_regions = self.detected_file_regions()
        return detected_file_regions.filter(
            Q(classification_correctness=True, defects__has_key=str(defect_id))
            | Q(
                classification_correctness=False,
                defects__has_key=str(defect_id),
                file_regions__defects__has_key=str(defect_id),
                file_regions__is_removed=False,
            )
        )
        # correctly_classified_regions = detected_file_regions.filter(
        #     classification_correctness=True,
        #     defects__has_key=str(defect_id)
        # )
        # incorrect_classified_regions = detected_file_regions.filter(
        #     classification_correctness=False,
        #     defects__has_key=str(defect_id),
        #     file_regions__defects__has_key=str(defect_id),
        #     file_regions__is_removed=False
        # )
        # return correctly_classified_regions | incorrect_classified_regions

    def true_positive_files_for_defect(self, defect_id):
        return File.objects.filter(file_regions__in=self.true_positive_file_regions_for_defect(defect_id)).distinct()

    def true_positive_file_sets_for_defect(self, defect_id):
        return FileSet.objects.filter(files__in=self.true_positive_files_for_defect(defect_id)).distinct()

    def ml_models_grouped_by_type(self):
        _ml_models_grouped_by_type = {}
        for ml_model in self.ml_models():
            if _ml_models_grouped_by_type.get(ml_model.type, None) is None:
                _ml_models_grouped_by_type[ml_model.type] = []
            _ml_models_grouped_by_type[ml_model.type].append(ml_model.id)
        return _ml_models_grouped_by_type

    def false_positive_file_regions_for_defect(self, defect_id):
        classification_fp_file_regions = FileRegion.objects.none()
        classification_and_detection_fp_file_regions = FileRegion.objects.none()
        for model_type, ml_models in self.ml_models_grouped_by_type().items():
            if model_type == "CLASSIFICATION":
                classification_fp_file_regions = self.detected_file_regions().filter(
                    classification_correctness=False, defects__has_key=str(defect_id)
                )
            elif model_type == "CLASSIFICATION_AND_DETECTION":
                classification_and_detection_fp_file_regions = self.detected_file_regions().filter(
                    ~Q(file_regions__defects__has_key=str(defect_id)),
                    classification_correctness=False,
                    defects__has_key=str(defect_id),
                    is_removed=False,
                )
        return classification_fp_file_regions | classification_and_detection_fp_file_regions

    def false_positive_files_for_defect(self, defect_id):
        return File.objects.filter(file_regions__in=self.false_positive_file_regions_for_defect(defect_id)).distinct()

    def false_positive_file_sets_for_defect(self, defect_id):
        return FileSet.objects.filter(files__in=self.false_positive_files_for_defect(defect_id)).distinct()

    def false_negative_file_regions_for_defect(self, defect_id):
        classification_fn_file_regions = FileRegion.objects.none()
        classification_and_detection_fn_file_regions = FileRegion.objects.none()
        for model_type, ml_model_ids in self.ml_models_grouped_by_type().items():
            if model_type == "CLASSIFICATION":
                classification_fn_file_regions = self.file_regions().filter(
                    file_regions=None, is_user_feedback=True, defects__has_key=str(defect_id), is_removed=False
                )
            elif model_type == "CLASSIFICATION_AND_DETECTION":
                classification_and_detection_fn_file_regions = self.detected_file_regions().filter(
                    ~Q(defects__has_key=str(defect_id)),
                    file_regions__defects__has_key=str(defect_id),
                    classification_correctness=False,
                    is_removed=False,
                )
        return classification_fn_file_regions | classification_and_detection_fn_file_regions

    def false_negative_files_for_defect(self, defect_id):
        return File.objects.filter(file_regions__in=self.false_negative_file_regions_for_defect(defect_id)).distinct()

    def false_negative_file_sets_for_defect(self, defect_id):
        return FileSet.objects.filter(files__in=self.false_negative_files_for_defect(defect_id)).distinct()


class StitchImageService:
    def stitch(self, upload_session_id):
        sys.path.append(GF7_DATA_PREP_PATH)
        from create_ui_folder import combine_images

        file_paths = File.objects.filter(
            file_set__in=FileSet.objects.filter(upload_session_id=upload_session_id)
        ).values_list("path", flat=True)
        old_upload_session = UploadSession.objects.get(id=upload_session_id)
        tm = datetime.now()
        new_upload_session = UploadSession.objects.create(
            name=old_upload_session.name + " stitched " + str(tm.time()),
            subscription_id=old_upload_session.subscription_id,
            use_case_id=old_upload_session.use_case_id,
        )
        all_new_local_files = combine_images(
            file_paths,
            os.path.join(str(upload_session_id), str(uuid.uuid1().hex)),
            {
                "aws_access_key_id": AWS_ACCESS_KEY_ID,
                "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
                "bucket": AWS_STORAGE_BUCKET_NAME,
            },
        )
        for name, path in all_new_local_files.items():
            file_set = FileSet.objects.create(
                upload_session=new_upload_session, subscription_id=old_upload_session.subscription_id
            )
            file = File(name=name, file_set=file_set)
            file.save()
            s3_service = S3Service()
            s3_service.upload_file(path, file.path)
        return


class BulkFeedbackService:
    def __init__(self, ml_model_id):
        self.ml_model = MlModel.objects.get(id=ml_model_id)
        if self.ml_model.type != "CLASSIFICATION" or self.ml_model.classification_type != "SINGLE_LABEL":
            raise ValidationError("Ml Model should be of Single Label Classification only")

    def update_feedback(self, file_set_filters, assign_defect_ids=None, remove_defect_ids=None):
        if self.ml_model.classification_type == "SINGLE_LABEL":
            self.update_feedback_for_single_label_model(file_set_filters, assign_defect_ids, remove_defect_ids)
        else:
            self.update_feedback_for_multi_label_model(file_set_filters, assign_defect_ids, remove_defect_ids)

    def update_feedback_for_single_label_model(self, file_set_filters, assign_defect_ids=None, remove_defect_ids=None):
        if assign_defect_ids:
            defect_id = int(assign_defect_ids[0])
            analysis_service = AnalysisService(
                file_set_filters=file_set_filters, ml_model_filters={"id__in": [self.ml_model.id]}
            )
            with transaction.atomic():
                files = analysis_service.files()
                for file in files:
                    current_gt_region = analysis_service.gt_regions().filter(file=file).first()
                    ai_region = FileRegion.objects.filter(
                        ml_model=self.ml_model, file=file, is_user_feedback=False
                    ).first()
                    if not current_gt_region:
                        if ai_region and int(list(ai_region.defects.keys())[0]) == defect_id:
                            ai_region.classification_correctness = True
                            ai_region.save()
                        elif ai_region and int(list(ai_region.defects.keys())[0]) != defect_id:
                            ai_region.classification_correctness = False
                            ai_region.save()
                            FileRegion.objects.create(
                                file=file,
                                is_user_feedback=True,
                                ml_model=self.ml_model,
                                defects={defect_id: {}},
                            )
                        else:
                            FileRegion.objects.create(
                                file=file,
                                is_user_feedback=True,
                                ml_model=self.ml_model,
                                defects={defect_id: {}},
                            )
                    elif current_gt_region and int(list(current_gt_region.defects.keys())[0]) != defect_id:
                        current_gt_region.is_removed = True
                        current_gt_region.save()
                        if ai_region and int(list(ai_region.defects.keys())[0]) == defect_id:
                            ai_region.classification_correctness = True
                            ai_region.save()
                        elif ai_region and int(list(ai_region.defects.keys())[0]) != defect_id:
                            ai_region.classification_correctness = False
                            ai_region.save()
                            FileRegion.objects.create(
                                file=file,
                                is_user_feedback=True,
                                ml_model=self.ml_model,
                                defects={defect_id: {}},
                            )
                        else:
                            FileRegion.objects.create(
                                file=file,
                                is_user_feedback=True,
                                ml_model=self.ml_model,
                                defects={defect_id: {}},
                            )
        if remove_defect_ids:
            raise NotImplementedError("Bulk remove defect isn't yet supported")

    def update_feedback_for_multi_label_model(self, file_set_filters, assign_defect_ids=None, remove_defect_ids=None):
        raise NotImplementedError("Bulk feedback for multi label models isn't yet supported")


class TrainingTerminator:
    def __init__(self, session_id):
        self.training_session_id = session_id
        self._training_session = None

    def terminate(self):
        with transaction.atomic():
            training_session = self.training_session()
            ml_model = training_session.new_ml_model
            # ToDo: If the training is in the last step, terminate training isn't possible.
            #  So, add that validation as well
            if ml_model.status != "training":
                raise ValidationError("The model training is not in progress to terminate")
            ml_model.status = "user_terminated"
            ml_model.save()
            training_session.finished_at = datetime.utcnow()
            training_session.save()
            self.remove_training_folders()

    def training_session(self):
        if self._training_session:
            return self._training_session
        self._training_session = TrainingSession.objects.get(id=self.training_session_id)
        return self._training_session

    def remove_training_folders(self):
        folders = glob.glob(f"/home/ubuntu/models/data/retraining_data/prod/{self.training_session_id}_*")
        for folder in folders:
            try:
                shutil.rmtree(folder)
            except FileNotFoundError as e:
                print("Folder not found : ", folder)


class UserAnnotationBulkActionService:
    def __init__(self, request_data):
        self.request_data = request_data

    # @staticmethod
    # def filtered_data(filters):
    #     use_case_filter = filters.get("use_case_filters").get("id__in")
    #     if use_case_filter is not None and use_case_filter != [""]:
    #         use_case_filter = Q(file_set__use_case__in=list(use_case_filter))
    #     else:
    #         use_case_filter = Q(Cast(Value(False), BooleanField()))

    #     upload_session_filter = filters.get("upload_session_filters").get("id__in")
    #     if upload_session_filter is not None and upload_session_filter != [""]:
    #         upload_session_filter = Q(file_set__upload_session__in=list(upload_session_filter))
    #     else:
    #         upload_session_filter = Q(Cast(Value(False), BooleanField()))

    #     file_set_filter = filters.get("file_set_filters").get("id__in")
    #     if file_set_filter is not None and file_set_filter != [""]:
    #         file_set_filter = Q(file_set__in=list(file_set_filter))
    #     else:
    #         file_set_filter = Q(Cast(Value(False), BooleanField()))

    #     file_query_result = File.objects.filter(
    #         Q(created_ts__gte=filters.get("file_set_filters").get("created_ts__gte"))
    #         & Q(created_ts__lte=filters.get("file_set_filters").get("created_ts__lte"))
    #         & use_case_filter
    #         & upload_session_filter
    #         & file_set_filter
    #     )
    #     return file_query_result

    # def classification_bulk_create(self, filters):
    def classification_bulk_create(
        self, file_ids, defect_ids, user_id, is_no_defect=False, replace_existing_labels=False
    ):
        # ToDo: Refactor all the bulk labelling actions
        with transaction.atomic():
            # files = self.filtered_data(filters)
            if not file_ids:
                raise ValidationError("File ids are mandatory")
            if is_no_defect is not False and is_no_defect is not True:
                raise ValidationError("is_no_defect should either be true or false")
            if is_no_defect is False and not defect_ids:
                raise ValidationError("Defect ids are mandatory if is no defect is not set to True")
            if is_no_defect is True and defect_ids:
                raise ValidationError("defect ids should not be there if is_no_defect is True")
            # ToDo: Bulk create should accept file set or file filters instead of accepting just file ids
            files = File.objects.filter(id__in=file_ids)
            defect_ids = list(set(defect_ids))
            all_use_cases = UseCase.objects.filter(
                id__in=files.values_list("file_set__use_case_id", flat=True).distinct()
            ).values("id", "type")
            for use_case in all_use_cases:
                if UseCaseDefect.objects.filter(use_case=use_case["id"], defect_id__in=defect_ids).count() != len(
                    defect_ids
                ):
                    raise ValidationError("Usecase not tagged to all defects provided in the request")
            all_use_case_types = all_use_cases.values_list("classification_type", flat=True).distinct()
            if len(all_use_case_types) > 1:
                raise ValidationError("We don't support bulk create for different use case type file sets")
            # defect_ids = self.request_data.get("defects", None)
            if "SINGLE_LABEL" in all_use_case_types and len(defect_ids) > 1:
                raise ValidationError("Multiple defects are not allowed for single label usecases")

            single_label = False
            if "SINGLE_LABEL" in all_use_case_types:
                single_label = True
            # user_id = self.request_data["user"]
            # is_no_defect = self.request_data["is_no_defect"]
            user_classification_objects = []
            user_classification_instances = []
            existing_user_classifications = UserClassification.objects.filter(user_id=user_id, file_id__in=file_ids)
            existing_file_ids = existing_user_classifications.values_list("file_id", flat=True)
            new_file_ids = list(set(file_ids) - set(existing_file_ids))
            for file_id in new_file_ids:
                user_classification = UserClassification(file_id=file_id, user_id=user_id, is_no_defect=is_no_defect)
                user_classification_objects.append(user_classification)
            if user_classification_objects:
                user_classification_instances = UserClassification.objects.bulk_create(user_classification_objects)

            if is_no_defect is True and replace_existing_labels is True:
                existing_user_classifications.update(is_no_defect=is_no_defect)
                UserClassificationDefect.objects.filter(classification__in=existing_user_classifications).delete()
                user_classifications = list(existing_user_classifications) + user_classification_instances
            elif is_no_defect is True and replace_existing_labels is False:
                user_classifications = user_classification_instances
            elif is_no_defect is False and replace_existing_labels is True:
                UserClassificationDefect.objects.filter(classification__in=existing_user_classifications).delete()
                user_classifications = list(existing_user_classifications) + user_classification_instances
            else:
                # Case where defect_ids is not empty, is no defect is False and replace is False
                if single_label is False:
                    user_classifications = list(existing_user_classifications) + user_classification_instances
                else:
                    existing_user_classifications = existing_user_classifications.filter(is_no_defect=True)
                    if existing_user_classifications:
                        existing_user_classifications.filter(is_no_defect=True).update(is_no_defect=False)
                        user_classifications = list(existing_user_classifications) + user_classification_instances
                    else:
                        user_classifications = user_classification_instances

            if user_classifications and defect_ids:
                user_classification_defects = []
                for user_classification in user_classifications:
                    for defect_id in defect_ids:
                        user_classification_defects.append(
                            UserClassificationDefect(classification=user_classification, defect_id=defect_id)
                        )
                UserClassificationDefect.objects.bulk_create(user_classification_defects, ignore_conflicts=True)

            # ToDo: The following code to copy to GT should be removed once the UI has a feature to assign the GT
            for user_classification in user_classifications:
                user_classification.copy_to_gt()

    def classification_bulk_replace(self, file_ids, original_defect, new_defect, user_id):
        with transaction.atomic():
            if not file_ids:
                raise ValidationError("File ids are mandatory")
            if not (original_defect or new_defect):
                raise ValidationError("Original and new defect are mandatory")
            # ToDo: What happens if user classification defect for one file contains both new and old defect
            UserClassificationDefect.objects.filter(
                classification__file_id__in=file_ids, classification__user_id=user_id, defect_id=original_defect
            ).update(defect_id=new_defect)
            user_classifications = UserClassification.objects.filter(
                file_id__in=file_ids,
                user_id=user_id,
            )
            # ToDo: The following code to copy to GT should be removed once the UI has a feature to assign the GT
            for user_classification in user_classifications:
                user_classification.copy_to_gt()

    def classification_bulk_remove(self, file_ids, defect_ids, user_id, remove_all=False):
        with transaction.atomic():
            if not file_ids:
                raise ValidationError("File ids are mandatory")
            if remove_all is not True and remove_all is not False:
                raise ValidationError("remove_all should either be true or false")
            if remove_all and defect_ids:
                raise ValidationError("defect ids should not be passed if remove_all is true")
            if remove_all is False and not defect_ids:
                raise ValidationError("defect ids are required if remove_all is false")
            if remove_all is True:
                UserClassification.objects.filter(
                    file_id__in=file_ids,
                    user_id=user_id,
                ).delete()
                # ToDo: The following code to copy to GT should be removed once the UI has a feature to assign the GT
                # Also, the following code won't work well if we create more than one user for creating annotations
                GTClassification.objects.filter(
                    file_id__in=file_ids,
                ).delete()
                return
            if defect_ids:
                UserClassificationDefect.objects.filter(
                    classification__file_id__in=file_ids, classification__user_id=user_id, defect_id__in=defect_ids
                ).delete()

                # After deleting user classification defects, there could be user classifications without any
                #  defects. We delete them completely.
                UserClassification.objects.filter(
                    file_id__in=file_ids,
                    user_id=user_id,
                    is_no_defect=False,
                    user_classification_annotations__isnull=True,
                ).delete()

                user_classifications = UserClassification.objects.filter(
                    file_id__in=file_ids,
                    user_id=user_id,
                )
                # ToDo: The following code to copy to GT should be removed once the UI has a feature to assign the GT
                GTClassification.objects.filter(file_id__in=file_ids).delete()
                if user_classifications.exists():
                    for user_classification in user_classifications:
                        user_classification.copy_to_gt()

    def detection_bulk_remove(self, file_ids, defect_ids, user_id, remove_all=False):
        with transaction.atomic():
            if not file_ids:
                raise ValidationError("File ids are mandatory")
            if remove_all is not True and remove_all is not False:
                raise ValidationError("remove_all should either be true or false")
            if remove_all and defect_ids:
                raise ValidationError("defect ids should not be passed if remove_all is true")
            if remove_all is False and not defect_ids:
                raise ValidationError("defect ids are required if remove_all is false")
            if remove_all is True:
                UserDetection.objects.filter(
                    file_id__in=file_ids,
                    user_id=user_id,
                ).delete()
                # ToDo: The following code to copy to GT should be removed once the UI has a feature to assign the GT
                GTDetection.objects.filter(
                    file_id__in=file_ids,
                ).delete()
                # GTDetectionRegionDefect.objects.filter(
                #     detection_region__detection__file_id__in=file_ids
                # ).delete()
            if defect_ids:
                UserDetectionRegionDefect.objects.filter(
                    detection_region__detection__file_id__in=file_ids,
                    detection_region__detection__user_id=user_id,
                    defect_id__in=defect_ids,
                ).delete()
                # ToDo: After the above query, there could be regions without any defects, We need to delete them as
                #  well. And after we delete the regions, it could be that zero regions on files.
                #  So, we delete entire user detection - Decision from Avni
                UserDetectionRegion.objects.filter(
                    detection__file_id__in=file_ids,
                    detection__user_id=user_id,
                    user_detection_region_annotations__isnull=True,
                ).delete()
                UserDetection.objects.filter(
                    file_id__in=file_ids, user_id=user_id, is_no_defect=False, detection_regions__isnull=True
                ).delete()
                user_detections = UserDetection.objects.filter(
                    file_id__in=file_ids,
                    user_id=user_id,
                )
                # ToDo: The following code to copy to GT should be removed once the UI has a feature to assign the GT
                GTDetection.objects.filter(file_id__in=file_ids).delete()
                if user_detections.exists():
                    for user_detection in user_detections:
                        user_detection.copy_to_gt()

    def detection_bulk_replace(self, file_ids, original_defect, new_defect, user_id):
        if not file_ids:
            raise ValidationError("File ids are mandatory")
        if not (original_defect or new_defect):
            raise ValidationError("Original and new defect are mandatory")
        with transaction.atomic():
            UserDetectionRegionDefect.objects.filter(
                detection_region__detection__file_id__in=file_ids,
                detection_region__detection__user_id=user_id,
                defect_id=original_defect,
            ).update(defect_id=new_defect)
            user_detections = UserDetection.objects.filter(
                file_id__in=file_ids,
                user_id=user_id,
            )
            # ToDo: The following code to copy to GT should be removed once the UI has a feature to assign the GT
            for user_detection in user_detections:
                user_detection.copy_to_gt()
