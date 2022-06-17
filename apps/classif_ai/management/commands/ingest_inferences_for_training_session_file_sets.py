import json

from django.core.management import BaseCommand

from apps.classif_ai.helpers import ingest_training_data_inferences_from_json_file


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("ml_model_id", type=int)
        parser.add_argument("inference_outputs_json_file_path", type=str)

    def handle(self, *args, **options):
        inference_outputs = json.load(open(options["inference_outputs_json_file_path"]))
        ingest_training_data_inferences_from_json_file(options["ml_model_id"], inference_outputs)
