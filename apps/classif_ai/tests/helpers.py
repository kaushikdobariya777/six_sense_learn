from apps.classif_ai.serializers import FileRegionSerializer
from apps.classif_ai.models import TrainingSessionFileSet


# ToDo: Think of a better name?
def prepare_training_session_file_set(training_session, file_set, file_id, file_region):
    data = FileRegionSerializer(instance=file_region).data
    defects = {file_id: [data]}
    training_session_file_set = TrainingSessionFileSet(
        training_session=training_session, file_set=file_set, defects=defects
    )
    return training_session_file_set
