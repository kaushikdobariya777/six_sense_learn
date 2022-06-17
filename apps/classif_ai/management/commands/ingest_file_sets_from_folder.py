import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.classif_ai.models import FileSet, File, UploadSession
from apps.classif_ai.serializers import FileSetInferenceQueueSerializer
from common.services import S3Service


class Command(BaseCommand):
    def ingest_fileset(self, subscription_id, use_case_id, upload_session_id, file_paths, ml_model_id=None):
        with transaction.atomic():
            file_set = FileSet.objects.create(
                upload_session_id=upload_session_id, subscription_id=subscription_id, use_case_id=use_case_id
            )
            for file_path in file_paths:
                file = File(name=os.path.basename(file_path), file_set=file_set)
                file.save()
                s3_service = S3Service()
                s3_service.upload_file(file_path, file.path)
            if ml_model_id:
                inference_queue_serializer = FileSetInferenceQueueSerializer(
                    data={"file_set": file_set.id, "ml_model": ml_model_id}
                )
                inference_queue_serializer.is_valid(raise_exception=True)
                inference_queue_serializer.save()

    def create_upload_session(self, subscription_id, use_case_id, name):
        return UploadSession.objects.create(subscription_id=subscription_id, use_case_id=use_case_id, name=name)

    def handle(self, **options):
        subscription_id = int(input("Please enter the subscription_id: "))
        use_case_id = int(input("Please enter the use_case_id: "))
        folder_path = input("Please enter the folder_path: ")
        ui_folder_name = input("Please enter the ui_folder_name: ")
        ml_model_id = input(
            "Please enter the model id using which inference needs to be performed. Click enter if inference is not needed: "
        )
        output_file_path = input("Please enter the output file path: ")
        if ml_model_id:
            ml_model_id = int(ml_model_id)
        else:
            ml_model_id = None
        file_count = 0
        success_file_paths = []
        failed_file_paths = []
        upload_session = self.create_upload_session(subscription_id, use_case_id, ui_folder_name)
        for filename in os.listdir(folder_path):
            try:
                self.ingest_fileset(
                    subscription_id, use_case_id, upload_session.id, [os.path.join(folder_path, filename)], ml_model_id
                )
                file_count += 1
                print(file_count)
                success_file_paths.append(filename)
            except:
                failed_file_paths.append(filename)
        f = open(output_file_path, "a")
        f.write("successful file names:")
        f.write(str(success_file_paths))
        f.write("failed file names:")
        f.write(str(failed_file_paths))
        f.close()
