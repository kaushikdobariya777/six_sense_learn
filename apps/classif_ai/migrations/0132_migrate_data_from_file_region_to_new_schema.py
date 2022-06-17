from decimal import Decimal

from django.contrib.gis.geos import Polygon
from django.db import migrations, IntegrityError, transaction
from django.db.models import Q


# Note: AnalysisService isn't used anywhere in this file because it could be removed or modified at any time and
# the migrations shouldn't break because of that
# def copy_classification_file_regions(apps, schema_editor, db_alias):
#     MlModel = apps.get_model("classif_ai", "MlModel")
#     FileRegion = apps.get_model("classif_ai", "FileRegion")
#     User = apps.get_model("user_auth", "User")
#     UserClassification = apps.get_model("classif_ai", "UserClassification")
#     UserClassificationDefect = apps.get_model("classif_ai", "UserClassificationDefect")
#     ModelClassification = apps.get_model("classif_ai", "ModelClassification")
#     ModelClassificationDefect = apps.get_model("classif_ai", "ModelClassificationDefect")
#
#     ml_models = MlModel.objects.using(db_alias).filter(use_case__type='CLASSIFICATION')
#     user = User.objects.using(db_alias).first()
#     for ml_model in ml_models:
#         file_regions = FileRegion.objects.using(db_alias).filter(ml_model=ml_model).order_by('id')
#         batch_size = 10000
#         total = file_regions.count()
#         for start in range(0, total, batch_size):
#             end = min(start + batch_size, total)
#             for file_region in file_regions[start:end]:
#                 if file_region.is_user_feedback is True and file_region.is_removed is False:
#                     user_classification = UserClassification.objects.using(db_alias).get_or_create(
#                         user=user,
#                         file_id=file_region.file_id
#                     )[0]
#                     try:
#                         with transaction.atomic():
#                             UserClassificationDefect.objects.using(db_alias).create(
#                                 classification=user_classification,
#                                 defect_id=list(file_region.defects.keys())[0]
#                             )
#                     except IntegrityError:
#                         pass
#                 elif file_region.is_user_feedback is False:
#                     model_classification = ModelClassification.objects.using(db_alias).get_or_create(
#                         file_id=file_region.file_id,
#                         ml_model_id=file_region.ml_model_id
#                     )[0]
#                     confidence = file_region.defects[list(file_region.defects.keys())[0]].get('confidence', None)
#                     ModelClassificationDefect.objects.using(db_alias).create(
#                         classification=model_classification,
#                         defect_id=list(file_region.defects.keys())[0],
#                         confidence=Decimal(confidence)
#                     )
#                     if file_region.classification_correctness is True:
#                         user_classification = UserClassification.objects.using(db_alias).get_or_create(
#                             user=user,
#                             file_id=file_region.file_id
#                         )[0]
#                         try:
#                             with transaction.atomic():
#                                 UserClassificationDefect.objects.using(db_alias).create(
#                                     classification=user_classification,
#                                     defect_id=list(file_region.defects.keys())[0]
#                                 )
#                         except IntegrityError:
#                             pass


# def copy_detection_file_regions(apps, schema_editor, db_alias):
#     MlModel = apps.get_model("classif_ai", "MlModel")
#     FileRegion = apps.get_model("classif_ai", "FileRegion")
#     User = apps.get_model("user_auth", "User")
#     UserDetection = apps.get_model("classif_ai", "UserDetection")
#     UserDetectionRegion = apps.get_model("classif_ai", "UserDetectionRegion")
#     UserDetectionRegionDefect = apps.get_model("classif_ai", "UserDetectionRegionDefect")
#     ModelDetection = apps.get_model("classif_ai", "ModelDetection")
#     ModelDetectionRegion = apps.get_model("classif_ai", "ModelDetectionRegion")
#     ModelDetectionRegionDefect = apps.get_model("classif_ai", "ModelDetectionRegionDefect")
#
#     ml_models = MlModel.objects.using(db_alias).filter(use_case__type='CLASSIFICATION_AND_DETECTION')
#     user = User.objects.using(db_alias).first()
#     for ml_model in ml_models:
#         file_regions = FileRegion.objects.using(db_alias).filter(
#             ml_model=ml_model
#         ).prefetch_related('ai_region').order_by('id')
#         batch_size = 10000
#         total = file_regions.count()
#         for start in range(0, total, batch_size):
#             end = min(start + batch_size, total)
#             for file_region in file_regions[start:end]:
#                 coordinates = file_region.region["coordinates"]
#                 minx = coordinates["x"]
#                 miny = coordinates["y"]
#                 maxx = coordinates["x"] + coordinates["w"]
#                 maxy = coordinates["y"] + coordinates["h"]
#                 if file_region.is_user_feedback is True and file_region.is_removed is False:
#                     user_detection = UserDetection.objects.using(db_alias).get_or_create(
#                         user=user,
#                         file_id=file_region.file_id
#                     )[0]
#                     try:
#                         with transaction.atomic():
#                             detection_region = UserDetectionRegion.objects.using(db_alias).create(
#                                 detection=user_detection,
#                                 region=Polygon(((minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny), (minx, miny)),),
#                             )
#                     except IntegrityError:
#                         print(f"FileID: {file_region.file_id}, UserID: {file_region.ml_model_id}: "
#                               f"detection region creation IntegrityError")
#                         continue
#                     for defect_id in file_region.defects:
#                         UserDetectionRegionDefect.objects.using(db_alias).create(
#                             detection_region=detection_region,
#                             defect_id=int(defect_id)
#                         )
#                 elif file_region.is_user_feedback is False:
#                     # Create model detection
#                     model_detection = ModelDetection.objects.using(db_alias).get_or_create(
#                         ml_model_id=file_region.ml_model_id,
#                         file_id=file_region.file_id
#                     )[0]
#                     try:
#                         with transaction.atomic():
#                             detection_region = ModelDetectionRegion.objects.using(db_alias).create(
#                                 detection=model_detection,
#                                 region=Polygon(((minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny), (minx, miny)), ),
#                                 model_output_meta_info=file_region.model_output_meta_info
#                             )
#                             for defect_id, val in file_region.defects.items():
#                                 confidence = val.get('confidence', None)
#                                 if confidence:
#                                     confidence = Decimal(confidence)
#                                 try:
#                                     with transaction.atomic():
#                                         ModelDetectionRegionDefect.objects.using(db_alias).create(
#                                             detection_region=detection_region,
#                                             defect_id=int(defect_id),
#                                             confidence=confidence
#                                         )
#                                 except IntegrityError:
#                                     pass
#                     except IntegrityError:
#                         print(f"FileID: {file_region.file_id}, ModelID: {file_region.ml_model_id}: "
#                               f"detection region creation IntegrityError")
#                     if (
#                             file_region.detection_correctness is True and
#                             file_region.classification_correctness is True and
#                             FileRegion.objects.filter(ai_region=file_region).exists() is False
#                     ):
#                         user_detection = UserDetection.objects.using(db_alias).get_or_create(
#                             user=user,
#                             file_id=file_region.file_id
#                         )[0]
#                         try:
#                             with transaction.atomic():
#                                 detection_region = UserDetectionRegion.objects.using(db_alias).create(
#                                     detection=user_detection,
#                                     region=Polygon(((minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny), (minx, miny)), ),
#                                 )
#                         except IntegrityError:
#                             print(f"FileID: {file_region.file_id}, UserID: {file_region.ml_model_id}: "
#                                   f"detection region creation IntegrityError")
#                             continue
#                         for defect_id in file_region.defects:
#                             try:
#                                 with transaction.atomic():
#                                     UserDetectionRegionDefect.objects.using(db_alias).create(
#                                         detection_region=detection_region,
#                                         defect_id=int(defect_id)
#                                     )
#                             except IntegrityError:
#                                 pass


def copy_classification_file_regions(apps, schema_editor, db_alias):
    MlModel = apps.get_model("classif_ai", "MlModel")
    File = apps.get_model("classif_ai", "File")
    FileSetInferenceQueue = apps.get_model("classif_ai", "FileSetInferenceQueue")
    FileRegion = apps.get_model("classif_ai", "FileRegion")
    User = apps.get_model("user_auth", "User")
    UserClassification = apps.get_model("classif_ai", "UserClassification")
    UserClassificationDefect = apps.get_model("classif_ai", "UserClassificationDefect")
    ModelClassification = apps.get_model("classif_ai", "ModelClassification")
    ModelClassificationDefect = apps.get_model("classif_ai", "ModelClassificationDefect")

    user = User.objects.using(db_alias).first()
    files = File.objects.filter(file_set__use_case__type='CLASSIFICATION').prefetch_related('file_set').order_by('id')
    ml_models = MlModel.objects.all()
    ml_model_ids_grouped_by_use_case_id = {}
    for ml_model in ml_models:
        if ml_model_ids_grouped_by_use_case_id.get(ml_model.use_case_id, None) is None:
            ml_model_ids_grouped_by_use_case_id[ml_model.use_case_id] = []
        ml_model_ids_grouped_by_use_case_id[ml_model.use_case_id].append(ml_model.id)
    batch_size = 10000
    total = files.count()
    count = 0
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        for file in files[start:end]:
            print_progress(count, total, prefix=f" {count}", suffix=str(total))
            count += 1
            # Pick all valid models for the file
            # ml_model_ids = FileSetInferenceQueue.objects.filter(
            #     file_set_id=file.file_set_id, status='FINISHED'
            # ).values_list('ml_model_id').distinct()
            ml_model_ids = ml_model_ids_grouped_by_use_case_id.get(file.file_set.use_case_id, [])

            # Find the model on which latest feedback is given
            latest_user_file_region = FileRegion.objects.filter(
                Q(
                    classification_correctness=True,
                    is_user_feedback=False,
                    file_regions=None,
                )
                | Q(is_user_feedback=True, is_removed=False),
                file_id=file.id,
                ml_model_id__in=ml_model_ids
            ).order_by('-updated_ts').first()
            gt_model_id = None
            if latest_user_file_region:
                gt_model_id = latest_user_file_region.ml_model_id
            # Create Model classification
            inferenced_ml_model_ids = FileSetInferenceQueue.objects.filter(
                file_set_id=file.file_set_id,
                status='FINISHED',
                ml_model_id__in=ml_model_ids,
            ).values_list('ml_model_id', flat=True).distinct()
            for ml_model_id in inferenced_ml_model_ids:
                file_regions = FileRegion.objects.filter(
                    ml_model_id=ml_model_id, is_user_feedback=False, file_id=file.id
                )
                if file_regions.exists():
                    is_no_defect = False
                else:
                    is_no_defect = True
                model_classification = ModelClassification.objects.using(db_alias).get_or_create(
                    file_id=file.id,
                    ml_model_id=ml_model_id,
                    is_no_defect=is_no_defect
                )[0]
                for file_region in file_regions:
                    confidence = file_region.defects[list(file_region.defects.keys())[0]].get('confidence', None)
                    try:
                        with transaction.atomic():
                            ModelClassificationDefect.objects.using(db_alias).create(
                                classification=model_classification,
                                defect_id=list(file_region.defects.keys())[0],
                                confidence=Decimal(confidence)
                            )
                    except IntegrityError:
                        print(f"FileId: {file.id}, ModelID: {ml_model_id}, "
                              f"Creating ModelClassificationDefect defect failed with IntegrityError")
                        pass
            if gt_model_id is not None:
                # Create user classification
                gt_file_regions = FileRegion.objects.filter(
                    Q(
                        classification_correctness=True,
                        is_user_feedback=False,
                        file_regions=None,
                    ) |
                    Q(
                        is_user_feedback=True,
                        is_removed=False
                    ),
                    file_id=file.id,
                    ml_model_id=gt_model_id
                )
                user_classification = UserClassification.objects.using(db_alias).get_or_create(
                    file_id=file.id,
                    user=user
                )[0]
                for file_region in gt_file_regions:
                    try:
                        with transaction.atomic():
                            UserClassificationDefect.objects.using(db_alias).create(
                                classification=user_classification,
                                defect_id=list(file_region.defects.keys())[0]
                            )
                    except IntegrityError:
                        print(f"FileId: {file.id}, ModelID: {gt_model_id}, "
                              f"Creating UserClassificationDefect defect failed with IntegrityError")
                        pass
    print()


def copy_detection_file_regions(apps, schema_editor, db_alias):
    MlModel = apps.get_model("classif_ai", "MlModel")
    File = apps.get_model("classif_ai", "File")
    FileSetInferenceQueue = apps.get_model("classif_ai", "FileSetInferenceQueue")
    FileRegion = apps.get_model("classif_ai", "FileRegion")
    User = apps.get_model("user_auth", "User")
    UserDetection = apps.get_model("classif_ai", "UserDetection")
    UserDetectionRegion = apps.get_model("classif_ai", "UserDetectionRegion")
    UserDetectionRegionDefect = apps.get_model("classif_ai", "UserDetectionRegionDefect")
    ModelDetection = apps.get_model("classif_ai", "ModelDetection")
    ModelDetectionRegion = apps.get_model("classif_ai", "ModelDetectionRegion")
    ModelDetectionRegionDefect = apps.get_model("classif_ai", "ModelDetectionRegionDefect")

    ml_models = MlModel.objects.all()
    ml_model_ids_grouped_by_use_case_id = {}
    for ml_model in ml_models:
        if ml_model_ids_grouped_by_use_case_id.get(ml_model.use_case_id, None) is None:
            ml_model_ids_grouped_by_use_case_id[ml_model.use_case_id] = []
        ml_model_ids_grouped_by_use_case_id[ml_model.use_case_id].append(ml_model.id)

    user = User.objects.using(db_alias).first()
    files = File.objects.filter(file_set__use_case__type='CLASSIFICATION_AND_DETECTION').order_by('id')
    batch_size = 10000
    total = files.count()
    count = 0
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        for file in files[start:end]:
            print_progress(count, total, prefix=f" {count}", suffix=str(total))
            count += 1
            ml_model_ids = ml_model_ids_grouped_by_use_case_id.get(file.file_set.use_case_id, [])
            latest_user_file_region = FileRegion.objects.filter(
                Q(
                    Q(detection_correctness=True) | Q(classification_correctness=True),
                    is_user_feedback=False,
                    file_regions=None,
                )
                | Q(is_user_feedback=True, is_removed=False),
                file_id=file.id,
                ml_model_id__in=ml_model_ids
            ).order_by('-updated_ts').first()
            gt_model_id = None
            if latest_user_file_region:
                gt_model_id = latest_user_file_region.ml_model_id

            # Create Model detections
            inferenced_ml_model_ids = FileSetInferenceQueue.objects.filter(
                file_set_id=file.file_set_id,
                status='FINISHED',
                ml_model_id__in=ml_model_ids
            ).values_list('ml_model_id', flat=True).distinct()
            for ml_model_id in inferenced_ml_model_ids:
                file_regions = FileRegion.objects.filter(
                    ml_model_id=ml_model_id, is_user_feedback=False, file_id=file.id
                )
                if file_regions.exists():
                    is_no_defect = False
                else:
                    is_no_defect = True
                model_detection = ModelDetection.objects.using(db_alias).get_or_create(
                    file_id=file.id,
                    ml_model_id=ml_model_id,
                    is_no_defect=is_no_defect
                )[0]
                for file_region in file_regions:
                    coordinates = file_region.region["coordinates"]
                    minx = coordinates["x"]
                    miny = coordinates["y"]
                    maxx = coordinates["x"] + coordinates["w"]
                    maxy = coordinates["y"] + coordinates["h"]
                    detection_region = ModelDetectionRegion.objects.using(db_alias).create(
                        detection=model_detection,
                        region=Polygon(((minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny), (minx, miny)), ),
                        model_output_meta_info=file_region.model_output_meta_info
                    )
                    for defect_id, val in file_region.defects.items():
                        confidence = val.get('confidence', None)
                        if confidence:
                            confidence = Decimal(confidence)
                        ModelDetectionRegionDefect.objects.using(db_alias).create(
                            detection_region=detection_region,
                            defect_id=int(defect_id),
                            confidence=confidence
                        )
            if gt_model_id is not None:
                # Create user classification
                gt_file_regions = FileRegion.objects.filter(
                    Q(
                        Q(detection_correctness=True) | Q(classification_correctness=True),
                        is_user_feedback=False,
                        file_regions=None,
                    ) |
                    Q(
                        is_user_feedback=True,
                        is_removed=False
                    ),
                    file_id=file.id,
                    ml_model_id=gt_model_id
                )
                user_detection = UserDetection.objects.using(db_alias).get_or_create(
                    file_id=file.id,
                    user=user
                )[0]
                for file_region in gt_file_regions:
                    if not file_region.defects:
                        print(f"FileID: {file_region.file_id}, ModelID: {file_region.ml_model_id}: "
                              f"A file region exists with defects as empty dict")
                        continue
                    coordinates = file_region.region["coordinates"]
                    minx = coordinates["x"]
                    if minx is None:
                        print(f"FileID: {file_region.file_id}, ModelID: {file_region.ml_model_id}: "
                              f"Region invalid. x is None")
                        continue
                    miny = coordinates["y"]
                    maxx = coordinates["x"] + coordinates["w"]
                    maxy = coordinates["y"] + coordinates["h"]
                    try:
                        with transaction.atomic():
                            detection_region = UserDetectionRegion.objects.using(db_alias).create(
                                detection=user_detection,
                                region=Polygon(((minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny), (minx, miny)), ),
                            )
                    except IntegrityError:
                        print(f"FileID: {file_region.file_id}, ModelID: {file_region.ml_model_id}: "
                              f"UserDetectionRegion creation IntegrityError")
                        continue
                    for defect_id, val in file_region.defects.items():
                        UserDetectionRegionDefect.objects.using(db_alias).create(
                            detection_region=detection_region,
                            defect_id=int(defect_id),
                        )
    print()

def copy_gt_classification(apps, schema_editor, db_alias):

    UserClassification = apps.get_model("classif_ai", "UserClassification")
    GTClassification = apps.get_model("classif_ai", "GTClassification")
    GTClassificationDefect = apps.get_model("classif_ai", "GTClassificationDefect")

    user_classifications = UserClassification.objects.using(db_alias).all().order_by('id').prefetch_related('user_classification_annotations')
    batch_size = 10000
    count = 0
    total = user_classifications.count()
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        for user_classification in user_classifications[start:end]:
            print_progress(count, total, prefix=f" {count}", suffix=str(total))
            count+=1
            gt_classification = GTClassification.objects.using(db_alias).create(is_no_defect=user_classification.is_no_defect, file_id=user_classification.file_id, created_by=user_classification.user, updated_by=user_classification.user)
        
            user_classification_defects = user_classification.user_classification_annotations.all()
            for user_classification_defect in user_classification_defects:
                GTClassificationDefect.objects.using(db_alias).create(classification=gt_classification, defect=user_classification_defect.defect, created_by=gt_classification.created_by, updated_by=gt_classification.updated_by)
    print('done')

def copy_gt_detection(apps, schema_editor, db_alias):
    UserDetection = apps.get_model("classif_ai", "UserDetection")
    GTDetection = apps.get_model("classif_ai", "GTDetection")
    GTDetectionRegion = apps.get_model("classif_ai", "GTDetectionRegion")
    GTDetectionRegionDefect = apps.get_model("classif_ai", "GTDetectionRegionDefect")

    user_detections = UserDetection.objects.using(db_alias).order_by('id').prefetch_related('detection_regions', 'detection_regions__user_detection_region_annotations')
    batch_size = 10000
    count = 0
    total = user_detections.count()
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        for user_detection in user_detections[start:end]:
            print_progress(count, total, prefix=f" {count}", suffix=str(total))
            count+=1
            gt_detection = GTDetection.objects.using(db_alias).create(is_no_defect=user_detection.is_no_defect, file_id=user_detection.file_id, created_by=user_detection.user, updated_by=user_detection.user)

            user_detection_regions = user_detection.detection_regions.all()
            for user_detection_region in user_detection_regions:
                gt_detection_region = GTDetectionRegion.objects.using(db_alias).create(detection=gt_detection, region=user_detection_region.region, created_by=gt_detection.created_by, updated_by=gt_detection.updated_by)
            
                user_detection_region_defects = user_detection_region.user_detection_region_annotations.all()
                for user_detection_region_defect in user_detection_region_defects:
                    GTDetectionRegionDefect.objects.using(db_alias).create(detection_region=gt_detection_region, defect=user_detection_region_defect.defect, created_by=gt_detection.created_by, updated_by=gt_detection.updated_by)
    
    print('done')

def forwards_func(apps, schema_editor):
    print("Starting the migration of file regions")
    db_alias = schema_editor.connection.alias
    print("Schema is {}".format(schema_editor.connection.schema_name))
    print("Part 1 starting")
    copy_classification_file_regions(apps, schema_editor, db_alias)
    print("Part 2 starting")
    copy_detection_file_regions(apps, schema_editor, db_alias)
    print("Part 3 starting")
    copy_gt_classification(apps, schema_editor, db_alias)
    print("Part 4 starting")
    copy_gt_detection(apps, schema_editor, db_alias)
    print("Ended the migration of file regions")
    # ToDo: Copy for those files in which ai inferenced but no file regions were created


def backwards_func(apps, schema_editor):
    pass


def print_progress(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█', printEnd="\r"):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=printEnd)
    # Print New Line on Complete
    if iteration == total:
        print()


class Migration(migrations.Migration):

    dependencies = [
        ('classif_ai', '0131_wafer_fields'),
    ]

    operations = [
        migrations.RunPython(forwards_func, backwards_func, atomic=True),
    ]
