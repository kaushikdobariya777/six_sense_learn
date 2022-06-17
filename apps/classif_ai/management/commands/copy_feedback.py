from django.core.management import BaseCommand
from django.db import transaction

from apps.classif_ai.helpers import calculate_iou
from apps.classif_ai.models import FileRegion, MlModel
from apps.classif_ai.services import AnalysisService


class Command(BaseCommand):
    def copy_feedback(self, upload_session_id, old_model_id, new_model_id):
        with transaction.atomic():
            service = AnalysisService(
                file_set_filters={"upload_session_id__in": [upload_session_id]},
                ml_model_filters={"id__in": [old_model_id]},
            )
            new_ml_model = MlModel.objects.get(id=new_model_id)
            for region in service.gt_regions():
                new_region = FileRegion(
                    ml_model_id=new_model_id,
                    file_id=region.file_id,
                    defects=region.defects,
                    region=region.region,
                    is_user_feedback=True,
                )
                new_ai_regions = FileRegion.objects.filter(
                    is_user_feedback=False, ml_model_id=new_model_id, file_id=region.file_id
                )
                matching_region = None

                for new_ai_region in new_ai_regions:
                    if new_ml_model.type == "CLASSIFICATION":
                        if list(new_ai_region.defects)[0] == list(new_region.defects)[0]:
                            matching_region = [new_ai_region, None]
                    else:
                        iou = calculate_iou(
                            [
                                new_region.region["coordinates"]["x"],
                                new_region.region["coordinates"]["y"],
                                new_region.region["coordinates"]["x"] + new_region.region["coordinates"]["w"],
                                new_region.region["coordinates"]["y"] + new_region.region["coordinates"]["h"],
                            ],
                            [
                                new_ai_region.region["coordinates"]["x"],
                                new_ai_region.region["coordinates"]["y"],
                                new_ai_region.region["coordinates"]["x"] + new_ai_region.region["coordinates"]["w"],
                                new_ai_region.region["coordinates"]["y"] + new_ai_region.region["coordinates"]["h"],
                            ],
                        )
                        if iou > 0.4:
                            if matching_region:
                                if matching_region[1] < iou:
                                    matching_region = [new_ai_region, iou]
                            else:
                                matching_region = [new_ai_region, iou]
                if matching_region and new_ml_model.type == "CLASSIFICATION":
                    matching_region[0].classification_correctness = True
                    matching_region[0].save()
                elif matching_region:
                    # ToDo: Compare if new_region and matching region are exactly same.
                    #  If same, then save matching region with classificaiton and detection correctness as true and
                    #  dont save new region at all
                    new_region.ai_region_id = matching_region[0].id
                    new_region.save()
                else:
                    new_region.save()
            all_new_ai_regions = FileRegion.objects.filter(
                is_user_feedback=False, ml_model_id=new_model_id, file__in=service.files()
            )
            print("all_new_ai_regions: " + str(all_new_ai_regions.count()))
            for ai_region in all_new_ai_regions:
                if new_ml_model.type == "CLASSIFICATION" and ai_region.classification_correctness == None:
                    ai_region.classification_correctness = False
                    ai_region.save()
                elif new_ml_model.type != "CLASSIFICATION" and ai_region.detection_correctness == None:
                    ai_region.is_removed = True
                    ai_region.classification_correctness = False
                    ai_region.detection_correctness = False
                    ai_region.save()
        return

    def handle(self, **options):
        upload_session_id = int(input("Please enter the upload_session_id: "))
        old_model_id = input("Please enter the old_model id: ")
        new_model_id = input("Please enter the new_model_id: ")
        self.copy_feedback(upload_session_id, old_model_id, new_model_id)
