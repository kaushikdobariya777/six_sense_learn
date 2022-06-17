from django.core.management import BaseCommand

from apps.classif_ai.models import Defect


class Command(BaseCommand):
    def handle(self, **options):
        defects = Defect.objects.all()
        for defect in defects:
            if not defect.code:
                defect.code = defect.name
                if Defect.objects.filter(code=defect.name).count() > 0:
                    defect.code = ""
                defect.save()
