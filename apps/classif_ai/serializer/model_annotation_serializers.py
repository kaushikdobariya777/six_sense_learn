from django.contrib.gis.geos import Polygon
from django.db import transaction
from apps.classif_ai.helpers import inference_output_setup_and_send
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from sixsense.settings import IMAGE_HANDLER_QUEUE_URL

from apps.classif_ai.models import (
    File,
    ModelClassification,
    ModelClassificationDefect,
    UseCase,
    ModelDetectionRegionDefect,
    ModelDetectionRegion,
    ModelDetection,
    FileSetInferenceQueue,
)
from apps.classif_ai.serializers import DefectSerializer


class MlModelClassificationDefectSerializer(serializers.ModelSerializer):
    defect = DefectSerializer(read_only=True)

    class Meta:
        model = ModelClassificationDefect
        fields = ["id", "defect", "confidence"]


class MLModelClassificationSerializer(serializers.ModelSerializer):
    classification_defects = MlModelClassificationDefectSerializer(
        source="model_classification_annotations", many=True, read_only=True
    )

    def validate(self, attrs):
        # ToDo: We are adding this logic to validate single label from multi label everywhere
        #  Eg. It's repeated in services as well. It needs to be some how moved to a single place like models
        #  or managers
        defects = self.context.get("defects", None)
        if defects:
            if attrs.get("is_no_defect", None) is True:
                raise ValidationError("Can't insert defects and set is_no_defect as True.")
            if len(defects) > 1:
                use_case_classification_type = attrs["ml_model"].use_case.classification_type
                # use_case_type = UseCase.objects.get(file_sets__files__id=attrs["file_id"]).classification_type
                if use_case_classification_type == "SINGLE_LABEL":
                    raise ValidationError("Can't insert multiple defects for a single label use case type.")

        return super(MLModelClassificationSerializer, self).validate(attrs)

    def create(self, validated_data):
        with transaction.atomic():
            model_classification = super().create(validated_data)
            defects = self.context.get("defects", None)
            if model_classification.is_no_defect is False and defects:
                model_classification_defects = []
                for defect in defects:
                    model_classification_defects.append(
                        ModelClassificationDefect(
                            classification=model_classification,
                            defect_id=defect["defect_id"],
                            confidence=defect["confidence"],
                        )
                    )
                classification_defects = ModelClassificationDefect.objects.bulk_create(model_classification_defects)
            FileSetInferenceQueue.objects.filter(
                file_set_id=model_classification.file.file_set_id,
                ml_model=validated_data["ml_model"],
                status="PROCESSING",
            ).update(status="FINISHED")
            if IMAGE_HANDLER_QUEUE_URL:
                transaction.on_commit(lambda: inference_output_setup_and_send(validated_data, classification_defects))
        return model_classification

    class Meta:
        model = ModelClassification
        fields = ["id", "file", "ml_model", "is_no_defect", "classification_defects"]


class MlModelDetectionRegionDefectSerializer(serializers.ModelSerializer):
    defect = DefectSerializer(read_only=True)

    class Meta:
        model = ModelDetectionRegionDefect
        fields = ["id", "confidence", "defect"]


class MlModelDetectionRegionSerializer(serializers.ModelSerializer):
    region = serializers.SerializerMethodField(read_only=True)
    region_defects = MlModelDetectionRegionDefectSerializer(many=True, read_only=True)

    def get_region(self, instance):
        coords = instance.region.coords
        return {
            "type": "box",
            "coordinates": {
                "x": coords[0][0][0],
                "y": coords[0][0][1],
                "h": coords[0][2][1] - coords[0][0][1],
                "w": coords[0][2][0] - coords[0][0][0],
            },
        }

    class Meta:
        model = ModelDetectionRegion
        fields = ["id", "region_defects", "region"]


class MLModelDetectionSerializer(serializers.ModelSerializer):
    detection_regions = MlModelDetectionRegionSerializer(many=True, read_only=True)

    class Meta:
        model = ModelDetection
        fields = ["id", "file", "ml_model", "is_no_defect", "detection_regions"]

    def validate(self, attrs):
        # ToDo: We are adding this logic to validate single label from multi label everywhere
        #  Eg. It's repeated in services as well. It needs to be some how moved to a single place like models
        #  or managers
        detection_regions = self.context.get("detection_regions", None)
        if detection_regions:
            if attrs.get("is_no_defect", None) is True:
                raise ValidationError("Can't insert defects and set is_no_defect as True.")
        return super(MLModelDetectionSerializer, self).validate(attrs)

    def create(self, validated_data):
        with transaction.atomic():
            model_detection = super().create(validated_data)
            if model_detection.is_no_defect is False and self.context.get("detection_regions", None):
                detection_regions = self.context.get("detection_regions")
                for detection_region_data in detection_regions:
                    region = detection_region_data["region"]["coordinates"]
                    detection_region = ModelDetectionRegion.objects.create(
                        region=Polygon(
                            (
                                (region["x"], region["y"]),
                                (region["x"] + region["w"], region["y"]),
                                (region["x"] + region["w"], region["y"] + region["h"]),
                                (region["x"], region["y"] + region["h"]),
                                (region["x"], region["y"]),
                            )
                        ),
                        detection=model_detection,
                    )
                    model_detection_defects = []
                    for defect in detection_region_data["defects"]:
                        model_detection_defects.append(
                            ModelDetectionRegionDefect(
                                detection_region=detection_region,
                                defect_id=defect["defect_id"],
                                confidence=defect["confidence"],
                            )
                        )
                    ModelDetectionRegionDefect.objects.bulk_create(model_detection_defects)
            FileSetInferenceQueue.objects.filter(
                file_set_id=model_detection.file.file_set_id, ml_model=validated_data["ml_model"], status="PROCESSING"
            ).update(status="FINISHED")
            return model_detection
