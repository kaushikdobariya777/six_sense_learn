import boto3
from django.core.exceptions import ValidationError
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.classif_ai.models import TrainingSession, MlModelDefect, TrainingSessionFileSet
from apps.classif_ai.serializers import TrainingSessionSerializer
from apps.classif_ai.services import TrainingTerminator
from common.views import BaseViewSet
from sixsense.settings import RETRAINING_QUEUE_REGION_NAME


class TrainingSessionViewSet(BaseViewSet):
    queryset = TrainingSession.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TrainingSessionSerializer

    def get_serializer_context(self):
        context = super(TrainingSessionViewSet, self).get_serializer_context()
        context.update({"request": self.request})
        return context

    def partial_update(self, request, *args, **kwargs):
        new_status = request.data.get("status", {})
        if not new_status:
            return Response("The request body must contain new_status", status=status.HTTP_400_BAD_REQUEST)
        training_session = TrainingSession.objects.get(id=kwargs["pk"])
        training_session.status = new_status
        training_session.save()
        serializer = TrainingSessionSerializer(instance=training_session)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["POST"])
    def start(self, request, pk):
        client = boto3.client("sqs", region_name=RETRAINING_QUEUE_REGION_NAME)
        try:
            training_session = TrainingSession.objects.prefetch_related("new_ml_model").get(id=pk)
            if training_session.new_ml_model.status != "draft":
                return Response({"msg": "This training cannot be started"}, status=status.HTTP_400_BAD_REQUEST)
            training_session.start()
            return Response({"msg": "Training will start soon"}, status=status.HTTP_200_OK)
        except TrainingSession.DoesNotExist:
            return Response({"msg": "Training Session Not found"}, status=status.HTTP_400_BAD_REQUEST)
        except (client.exceptions.InvalidMessageContents, client.exceptions.UnsupportedOperation) as e:
            return Response(
                {"msg": "Training couldn't be started. Please try again later"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["POST"])
    def terminate(self, request, pk):
        service = TrainingTerminator(session_id=pk)
        try:
            service.terminate()
            return Response({"msg": "Training terminated successfully"}, status=status.HTTP_200_OK)
        except TrainingSession.DoesNotExist as e:
            return Response({"msg": "Training session id provided is invalid"}, status=status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return Response({"msg": e.message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_name="summary", url_path="summary")
    def summary(self, request, pk):
        try:
            training_session = TrainingSession.objects.get(id=pk)
        except TrainingSession.DoesNotExist:
            return Response(
                {"msg": "Training session id {} is invalid".format(pk)}, status=status.HTTP_400_BAD_REQUEST
            )

        defect_summary = self.get_defect_summary(training_session)
        data_summary = self.get_file_summary(training_session)

        response = {"defect_summary": defect_summary, "data_summary": data_summary}
        return Response(response, status=status.HTTP_200_OK)

    def get_defect_summary(self, training_session):
        new_model_defects = MlModelDefect.objects.filter(ml_model_id=training_session.new_ml_model).values("defect")
        old_model_defects = MlModelDefect.objects.filter(ml_model_id=training_session.old_ml_model).values("defect")
        return {
            "total_defect_in_training": new_model_defects.count(),
            "defects_imported_from_base_model": new_model_defects.intersection(old_model_defects).count(),
            "newly_added_defect": new_model_defects.difference(old_model_defects).count(),
            "removed_defect_from_base_model": old_model_defects.difference(new_model_defects).count(),
        }

    def get_file_summary(self, training_session):
        new_training_images = TrainingSessionFileSet.objects.filter(
            training_session__new_ml_model=training_session.new_ml_model
        ).values("file_set")
        old_training_images = TrainingSessionFileSet.objects.filter(
            training_session__new_ml_model=training_session.old_ml_model
        ).values("file_set")
        return {
            "total_images_in_training": new_training_images.count(),
            "total_imported_from_base_model": new_training_images.intersection(old_training_images).count(),
            "newly_added_images": new_training_images.difference(old_training_images).count(),
            "removed_images_from_base_model": old_training_images.difference(new_training_images).count(),
        }
