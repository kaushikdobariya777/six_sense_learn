import base64
import errno
from calendar import monthrange
import importlib
import os
import uuid
import pytz
import json
from datetime import datetime, timedelta

from xml.dom import minidom
from xml.parsers.expat import ExpatError
from common.services import SqsService

import environ
from django.db import models, connection, transaction
from django.db.models import Q, Subquery, OuterRef
from django.utils.text import slugify

from apps.subscriptions.models import Subscription
from sixsense.settings import BASE_DIR, PROJECT_START_DATE, IMAGE_HANDLER_QUEUE_URL


def get_env():
    env = environ.Env()
    if env.bool("DJANGO_READ_DOT_ENV_FILE", default=True):
        env_file = str(os.path.join(BASE_DIR, ".env"))
        if os.path.exists(env_file):
            env.read_env(env_file)
    return env


def add_uuid_to_file_name(complete_file_name):
    split = complete_file_name.split(".")
    file_name = ".".join(split[0:-1])
    extension = split[-1]
    return file_name + "--" + uuid.uuid4().hex[:10] + "." + extension


def infineon_get_use_case_id(data):
    from apps.classif_ai.models import UseCase

    file_name = data["files"][0]["name"]
    use_case = None
    if "Backlight Burr" in file_name:
        use_case = UseCase.objects.filter(name="Bottom Lead").first()
    if "Top Lead Contam" in file_name:
        use_case = UseCase.objects.filter(name="Top Lead").first()
    if "SMI HS" in file_name:
        use_case = UseCase.objects.filter(name="Heatsink").first()
    if use_case:
        return use_case.id


def infineon_populate_meta_info(data):
    infineon_separator = "_"
    file_name = data["files"][0]["name"]
    # 84PN1S60X03_Tray008_R002C004_BCF2MCF10_Backlight Burr Backlight Burr 1.bmp
    # 84PN8K84X04_Tray003_R009C003_BCF2MCF10_Bottom SMI HS Scratch.bmp
    # 84PP1X47A13_C0000202_BC24MCF1_TopSMI Alignment Lead Tip_TopSMI Top Lead Contam.bmp
    arr = file_name.split(infineon_separator)
    data["meta_info"] = {}
    data["meta_info"]["lot_id"] = arr[0]
    if "SMI HS" in file_name:
        data["meta_info"]["application"] = "Heatsink"
        data["meta_info"]["tray_id"] = arr[1]
        data["meta_info"]["row_and_col_id"] = arr[2]
    if "Top Lead Contam" in file_name:
        data["meta_info"]["application"] = "Top Lead"
    if "Backlight Burr" in file_name:
        data["meta_info"]["application"] = "Bottom Lead"
        data["meta_info"]["tray_id"] = arr[1]
        data["meta_info"]["row_and_col_id"] = arr[2]
    # data['meta_info']['application'] = arr[-1]
    # if "Burr" in file_name:
    # 	data['meta_info']['lot_id'] = arr[0]
    # 	data['meta_info']['tray_id'] = arr[1]
    # 	data['meta_info']['row_and_col_id'] = arr[2]
    # 	data['meta_info']['application'] = arr[-1]
    # elif "HS" in file_name and "Scratch" in file_name:
    # 	data['meta_info']['lot_id'] = arr[0]
    # 	data['meta_info']['tray_id'] = arr[1]
    # 	data['meta_info']['row_and_col_id'] = arr[2]
    # 	data['meta_info']['application'] = arr[-1]
    # elif "Top" in file_name and "Lead" in file_name:
    # 	data['meta_info']['lot_id'] = arr[0]
    # 	data['meta_info']['tray_id'] = arr[1]
    # 	data['meta_info']['row_and_col_id'] = arr[2]
    # 	data['meta_info']['application'] = arr[-1]

    # if len(arr) == 6:
    # 	data['meta_info']['lot_id'] = arr[0]
    # 	data['meta_info']['tray_id'] = arr[1]
    # 	data['meta_info']['row_and_col_id'] = arr[2]
    # 	data['meta_info']['application'] = arr[5]
    # elif len(arr) == 5:
    # 	data['meta_info']['lot_id'] = arr[0]
    # 	data['meta_info']['tray_id'] = "TRAY"
    # 	data['meta_info']['row_and_col_id'] = arr[1]
    # 	data['meta_info']['application'] = arr[4]
    # elif len(arr) == 8:
    # 	data['meta_info']['lot_id'] = arr[0]
    # 	data['meta_info']['tray_id'] = arr[1]
    # 	data['meta_info']['row_and_col_id'] = arr[1]
    # 	data['meta_info']['application'] = arr[4] + arr[5] + arr[6] + arr[7]
    return data


def calculate_iou(boxA, boxB):
    # # determine the (x, y)-coordinates of the intersection rectangle
    # xA = max(boxA[0], boxB[0])
    # yA = max(boxA[1], boxB[1])
    # xB = min(boxA[2], boxB[2])
    # yB = min(boxA[3], boxB[3])
    # # compute the area of intersection rectangle
    # interArea = max(0, xB - xA + 1) * max(0, yB - yA + 1)
    # # compute the area of both the prediction and ground-truth
    # # rectangles
    # boxAArea = (boxA[2] - boxA[0] + 1) * (boxA[3] - boxA[1] + 1)
    # boxBArea = (boxB[2] - boxB[0] + 1) * (boxB[3] - boxB[1] + 1)
    # # compute the intersection over union by taking the intersection
    # # area and dividing it by the sum of prediction + ground-truth
    # # areas - the interesection area
    # iou = interArea / float(boxAArea + boxBArea - interArea)
    # # return the intersection over union value
    # return iou
    # dx = min(a.xmin + a.w, b.xmin + b.w) - max(a.xmin, b.xmin)
    # dy = min(a.ymin + a.h, b.ymin + b.h) - max(a.ymin, b.ymin)
    dx = min(boxA[2], boxB[2]) - max(boxA[0], boxB[0])
    dy = min(boxA[3], boxB[3]) - max(boxA[1], boxB[1])
    intersection_area = 0
    if (dx >= 0) and (dy >= 0):
        intersection_area = dx * dy
    union_area = (
        ((boxA[2] - boxA[0]) * (boxA[3] - boxA[1])) + ((boxB[2] - boxB[0]) * (boxB[3] - boxB[1])) - intersection_area
    )
    return intersection_area / union_area


class JSONBSet(models.Func):
    """
    Update the value of a JSONField for a specific key.
    Works with nested JSON fields as well.
    """

    function = "JSONB_SET"
    arity = 4
    output_field = models.CharField()


def infineon_header_xml_to_dict(meta_file_path, subscription_id):
    try:
        xmldoc = minidom.parseString(meta_file_path)
    except (TypeError, ExpatError):
        xmldoc = minidom.parse(meta_file_path)
    header_nodes = xmldoc.getElementsByTagName("HeaderData")
    meta_info = {}
    file_set_meta_info = Subscription.objects.get(id=subscription_id).file_set_meta_info
    allowed_meta_tags = []
    for el in file_set_meta_info:
        allowed_meta_tags.append(el["field"])
    for m in header_nodes:
        if len(m.childNodes) > 0:
            for tag in m.childNodes:
                if tag.nodeType != tag.TEXT_NODE:
                    for text in tag.childNodes:
                        if tag.tagName in allowed_meta_tags:
                            if tag.tagName.endswith("Date"):
                                text.data = datetime.strptime(text.data, "%Y-%m-%dT%H:%M:%S")
                            if tag.tagName == "RunTime":
                                text.data = int(text.data)
                            meta_info[tag.tagName] = text.data
    return meta_info


def infineon_yield_xml_to_dict(meta_file_path, subscription_id):
    try:
        xmldoc = minidom.parseString(meta_file_path)
    except (TypeError, ExpatError):
        xmldoc = minidom.parse(meta_file_path)
    header_node = xmldoc.getElementsByTagName("YieldData")[0]
    meta_info = {}
    file_set_meta_info = Subscription.objects.get(id=subscription_id).file_set_meta_info
    allowed_meta_tags = []
    for el in file_set_meta_info:
        allowed_meta_tags.append(el["field"])
    for tag in header_node.childNodes:
        for text in tag.childNodes:
            if tag.tagName in allowed_meta_tags and tag.tagName != "FailCount":
                meta_info[tag.tagName] = text.data
    return meta_info


def build_query(filters):
    if filters is None:
        filters = {}
    query = Q()
    if filters:
        for key, val in filters.items():
            expr = {key: val}
            query &= Q(**expr)
    return query


def infineon_get_default_model_for_file_set(file_set):
    from apps.classif_ai.models import MlModel

    if "SMI HS" in file_set.files.first().name:
        return MlModel.objects.filter(code="heatsink", is_stable=True).first()
    if "Top Lead Contam" in file_set.files.first().name:
        return MlModel.objects.filter(code="top_lead", is_stable=True).first()
    if "Backlight Burr" in file_set.files.first().name:
        return MlModel.objects.filter(code="bottom_lead", is_stable=True).first()
    return None


def get_default_model_for_file_set(file_set):
    helpers_module = importlib.import_module("apps.classif_ai.helpers")
    return getattr(helpers_module, connection.tenant.schema_name + "_get_default_model_for_file_set")(file_set)


# def get_callable_from_string(name):
#     components = name.split('.')
#     mod = __import__(components[0])
#     for comp in components[1:]:
#         mod = getattr(mod, comp)
#     return mod


def generate_code(name):
    code = slugify(name)
    code += "-" + uuid.uuid4().hex[:10]
    return code


def is_same_region(region1, region2):
    if region1["type"] != region2["type"]:
        return False
    if region1["type"] == "box":
        try:
            if (
                region1["coordinates"]["x"] == region2["coordinates"]["x"]
                and region1["coordinates"]["y"] == region2["coordinates"]["y"]
                and region1["coordinates"]["w"] == region2["coordinates"]["w"]
                and region1["coordinates"]["h"] == region2["coordinates"]["h"]
            ):
                return True
            else:
                return False
        except Exception as e:
            return False
    return False


def convert_datetime_to_str(time_val, time_format=None):
    time_str = time_val.strftime("%Y-%m-%d")
    if time_format == "monthly":
        year = time_val.year
        month = time_val.month
        last_date = monthrange(year, month)[1]
        time_str = f"{time_str} : {year}-{month}-{last_date}"
    elif time_format == "weekly":
        end_date = time_val + timedelta(days=7)
        time_str = f"{time_str} : {end_date.strftime('%Y-%m-%d')}"

    return time_str


def ingest_training_data_inferences_from_json_file(ml_model_id: int, inference_outputs: dict) -> None:
    from apps.classif_ai.models import File, TrainingSessionFileSet, FileSetInferenceQueue
    from apps.classif_ai.serializers import FileRegionSerializer

    # inference_outputs = json.load(open(inference_outputs_json_file_path))
    with transaction.atomic():
        files_list = File.objects.filter(
            name__in=list(inference_outputs.keys()),
            file_set_id__in=TrainingSessionFileSet.objects.filter(training_session__new_model_id=ml_model_id).values(
                "file_set_id"
            ),
        ).values("id", "name", "file_set_id")
        files = {}
        for file in files_list:
            files[file["name"]] = file
        queue_objs = []
        for file_name, model_output in inference_outputs.items():
            file = files.get(file_name, None)
            if file is None:
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file_name)
            model_output["ml_model"] = ml_model_id
            model_output["file"] = file["id"]
            model_output["is_user_feedback"] = False
            queue_objs.append(
                FileSetInferenceQueue(status="FINISHED", file_set_id=file["file_set_id"], ml_model_id=ml_model_id)
            )
            serializer = FileRegionSerializer(data=model_output)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        FileSetInferenceQueue.objects.bulk_create(queue_objs)


def get_filters_from_request_object(request):
    file_set_filters = {}
    ml_model_filters = {}
    use_case_filters = {}
    upload_session_filters = {}
    time_format = "daily"
    date__gte = PROJECT_START_DATE
    date__lte = datetime.now()
    file_set_filters["created_ts__gte"] = date__gte
    file_set_filters["created_ts__lte"] = date__lte

    for key, val in request.query_params.items():
        if key == "ml_model_id__in":
            ml_model_filters["id__in"] = val.split(",")
        elif key == "use_case_id__in":
            use_case_filters["id__in"] = val.split(",")
        elif key == "subscription_id":
            file_set_filters["subscription_id__in"] = val.split(",")
        elif key == "upload_session_id__in":
            upload_session_filters["id__in"] = val.split(",")
        elif key == "time_format":
            time_format = val
        elif key == "date__gte":
            file_set_filters["created_ts__gte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
        elif key == "date__lte":
            file_set_filters["created_ts__lte"] = datetime(*list(map(int, (val.split("-")))), tzinfo=pytz.UTC)
        elif key == "train_type__in":
            file_set_filters["trainingsessionfileset__dataset_train_type__in"] = val.split(",")
        else:
            file_set_filters[key] = val.split(",")
    return {
        "file_set_filters": file_set_filters,
        "ml_model_filters": ml_model_filters,
        "time_format": time_format,
        "use_case_filters": use_case_filters,
        "upload_session_filters": upload_session_filters,
    }


def get_auto_model_query(model_status_list):
    from apps.classif_ai.models import ModelClassification

    if model_status_list:
        status_filter = Q(ml_model__status__in=model_status_list.split(","))
    else:
        status_filter = Q()

    sub_query = Subquery(
        ModelClassification.objects.filter(Q(file=OuterRef("files")) & status_filter)
        .order_by("-created_ts")
        .values("ml_model")[:1]
    )
    return sub_query


def _auto_model_filter(self):
    ml_model_ids = self.request.query_params.get("ml_model_id__in", None)
    ml_model_status__in = self.request.query_params.get("ml_model_status__in", None)
    if ml_model_ids:
        automodel_filter = Q(files__model_classifications__ml_model__in=ml_model_ids.split(","))
        if ml_model_status__in:
            automodel_filter = automodel_filter & Q(
                files__model_classifications__ml_model__status__in=ml_model_status__in.split(",")
            )
    else:
        sub_query = get_auto_model_query(ml_model_status__in)
        automodel_filter = Q(files__model_classifications__ml_model__in=sub_query)
    return automodel_filter

    # from apps.classif_ai.models import FileSetInferenceQueue
    # sub_query = Subquery(
    #     FileSetInferenceQueue.objects.filter(Q(file_set=OuterRef("id")) & Q(status__in=["FINISHED", "FAILED"]) & status_filter)
    #     .order_by("-created_ts")
    #     .values("ml_model")[:1]
    # )
    # queryset = queryset.filter(file_set_inference_queues__ml_model__in=sub_query)
    # return queryset


def inference_output_queue(message):
    """
    Takes the message, creates json string of it and then pushes it to image handler queue.
    Right now, this is specific to sqs, would need to figure out a way to make is queue independent.
    Had tried celery but could not get a solution
    TODO: make this code sqs independent
    """
    message = json.dumps(message)
    sqs = SqsService(IMAGE_HANDLER_QUEUE_URL)
    sqs.send_message(message)


def inference_output_setup_and_send(classification, classification_defects):
    defects = {
        classification_defect.defect.id: {
            "confidence": classification_defect.confidence,
            "organization_defect_code": classification_defect.defect.organization_defect_code,
        }
        for classification_defect in classification_defects
    }
    files = {"file_set": classification.get("file").file_set_id, "file_regions": [{"defects": defects}]}
    message = {}
    message["id"] = classification.get("file").file_set_id
    message["files"] = [files]
    message["type"] = "model_inference"
    return inference_output_queue(message)


def create_celery_format_message(task, args=None, kwargs=None):
    if args is None:
        args = []
    if kwargs is None:
        kwargs = {}
    body = [args, kwargs, {"callbacks": None, "errbacks": None, "chain": None, "chord": None}]
    task_id = str(uuid.uuid1())
    payload = {
        "body": base64.b64encode(json.dumps(body).encode("ascii")).decode("utf-8"),
        "content-encoding": "utf-8",
        "content-type": "application/json",
        "headers": {
            "lang": "py",
            "task": task,
            "id": task_id,
            "shadow": None,
            "eta": None,
            "expires": None,
            "group": None,
            "group_index": None,
            "retries": 0,
            "timelimit": [None, None],
            "root_id": task_id,
            "parent_id": None,
            "argsrepr": "('{}',)",
            "kwargsrepr": "{}",
        },
        "properties": {
            "correlation_id": task_id,
            "reply_to": str(uuid.uuid1()),
            "delivery_mode": 2,
            "delivery_info": {"exchange": "", "routing_key": "celery"},
            "priority": 0,
            "body_encoding": "base64",
            "delivery_tag": str(uuid.uuid1()),
        },
    }
    return base64.b64encode(json.dumps(payload).encode("ascii")).decode("utf-8")


def get_region_coordinates(coordinates):
    return {
        "type": "box",
        "coordinates": {
            "x": coordinates[0][0][0],
            "y": coordinates[0][0][1],
            "h": coordinates[0][2][1] - coordinates[0][0][1],
            "w": coordinates[0][2][0] - coordinates[0][0][0],
        },
    }


def prepare_detection_defects(file_set):
    from apps.classif_ai.models import GTClassification

    defect = {"id": file_set.id, "files": []}
    defects_on_files = []
    for file in file_set.files.all():
        try:
            defect_on_file = {
                "id": file.id,
                "gt_detection": {
                    "is_no_defect": file.gt_detections.is_no_defect,
                    "detection_regions": [],
                },
            }
            detection_regions = []
            for detection_region in file.gt_detections.detection_regions.all():
                coordinates = detection_region.region.coords
                region = get_region_coordinates(coordinates)
                detection_regions.append(
                    {
                        "region": region,
                        "defects": list(
                            detection_region.gt_detection_region_annotation.values_list("defect_id", flat=True)
                        ),
                    }
                )
            defect_on_file["gt_detection"]["detection_regions"] = detection_regions
            defects_on_files.append(defect_on_file)
        except GTClassification.DoesNotExist:
            pass
    defect["files"] = defects_on_files
    return defect


def prepare_classification_defects(file_set):
    from apps.classif_ai.models import GTClassification

    defect = {"id": file_set.id, "files": []}
    defects_on_files = []
    for file in file_set.files.all():
        try:
            defect_on_file = {
                "id": file.id,
                "gt_classification": {
                    "is_no_defect": file.gt_classifications.is_no_defect,
                    "defects": list(file.gt_classifications.defects.values_list("id", flat=True)),
                },
            }
            defects_on_files.append(defect_on_file)
        except GTClassification.DoesNotExist:
            pass
    defect["files"] = defects_on_files
    return defect


def prepare_training_session_defects_json(file_set, use_case_type):
    defect_json = {}
    # file_set.use_case.type
    if use_case_type == "CLASSIFICATION_AND_DETECTION":
        defect_json = prepare_detection_defects(file_set)
    elif use_case_type == "CLASSIFICATION":
        defect_json = prepare_classification_defects(file_set)
    return defect_json
