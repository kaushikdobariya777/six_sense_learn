import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sixsense.settings")

from sixsense.settings import INFERENCE_QUEUE, RETRAINING_QUEUE

app = Celery("sixsense")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.conf.update(result_extended=True)
app.conf.task_routes = {
    "apps.classif_ai.tasks.perform_file_set_inference": {"queue": INFERENCE_QUEUE},
    "apps.classif_ai.tasks.perform_retraining": {"queue": RETRAINING_QUEUE},
}
