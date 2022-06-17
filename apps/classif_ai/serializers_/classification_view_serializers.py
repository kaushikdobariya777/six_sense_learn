from rest_framework import serializers


class AccuracyResponse(serializers.Serializer):
    total = serializers.IntegerField()
    accurate = serializers.IntegerField()
    percentage = serializers.FloatField()


class AccuracyTimeseriesResponse(AccuracyResponse):
    effective_date = serializers.DateField()


class AutoClassificationResponse(serializers.Serializer):
    total = serializers.IntegerField()
    auto_classified = serializers.IntegerField()
    percentage = serializers.FloatField()
    manual = serializers.IntegerField(required=False)  # TODO: remove required in future
    on_hold = serializers.IntegerField(required=False)


class AutoClassificationTimeseriesResponse(AutoClassificationResponse):
    effective_date = serializers.DateField()


# TODO: add nested fields, usecase should have id and name, autoclasified should have metrics, accuracy should have metrics.
class ClasswiseMetricsUseCaseLevelResponse(serializers.Serializer):
    use_case_id = serializers.IntegerField()
    use_case_name = serializers.CharField()
    total = serializers.IntegerField()
    auto_classified = serializers.IntegerField()
    auto_classified_percentage = serializers.FloatField()
    accurate = serializers.IntegerField()
    accuracy_percentage = serializers.FloatField()
    total_defects = serializers.IntegerField()
    total_auto_classified = serializers.IntegerField()
    auto_classification_drop = serializers.FloatField()
    accuracy_drop = serializers.FloatField()


class MissclassificationDefectLevelResponse(serializers.Serializer):
    gt_defect_id = serializers.IntegerField()
    model_defect_id = serializers.IntegerField()
    gt_defect_name = serializers.CharField()
    model_defect_name = serializers.CharField()
    miss_classifications = serializers.IntegerField()
    total_miss_classifications = serializers.IntegerField()
    miss_classification_percentage = serializers.FloatField()


class AutoClassificationDefectDistributionResponse(serializers.Serializer):
    defect_id = serializers.IntegerField()
    total = serializers.IntegerField()
    defects = serializers.IntegerField()
    auto_classified = serializers.IntegerField()


class ClasswiseMetricsDefectLevelResponse(serializers.Serializer):
    gt_defect_id = serializers.IntegerField()
    gt_defect_name = serializers.CharField()
    total = serializers.IntegerField(default=0)
    auto_classified = serializers.IntegerField(default=0)
    auto_classified_percentage = serializers.FloatField(allow_null=True)
    accurate = serializers.IntegerField(default=0)
    accuracy_percentage = serializers.FloatField(allow_null=True)
    missed = serializers.IntegerField(default=0)
    missed_percentage = serializers.FloatField(allow_null=True)
    extra = serializers.IntegerField(default=0)
    extra_percentage = serializers.FloatField(allow_null=True)
    total_gt_defects = serializers.IntegerField(default=0)
    total_model_defects = serializers.IntegerField(default=0)
    recall_percentage = serializers.FloatField(allow_null=True)
    precision_percentage = serializers.FloatField(allow_null=True)


class AutoClassificationTimeSeriesResponse(serializers.Serializer):
    effective_date = serializers.DateField()
    percentage = serializers.FloatField(allow_null=True)
    auto_classified = serializers.IntegerField(default=0)
    manual = serializers.IntegerField(default=0)
    total = serializers.IntegerField(default=0)


class UseCaseAutoClassificationTimeSeriesResponse(serializers.Serializer):
    use_case_id = serializers.IntegerField()
    time_series_data = AutoClassificationTimeSeriesResponse(many=True)
