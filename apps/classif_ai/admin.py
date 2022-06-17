from tenant_admin_site import admin_site
from django.contrib import admin

from apps.classif_ai.models import (
    MlModel,
    Defect,
    MlModelDefect,
    FileSet,
    File,
    FileRegion,
    FileRegionHistory,
    UploadSession,
    UseCase,
    UseCaseDefect,
    UserClassification,
    UserClassificationDefect,
    UserDetectionRegion,
    UserDetection,
    UserDetectionRegionDefect,
    ModelClassification,
    ModelClassificationDefect,
    ModelDetection,
    ModelDetectionRegion,
    ModelDetectionRegionDefect,
    GTClassification,
    GTClassificationDefect,
    GTDetection,
    GTDetectionRegion,
    GTDetectionRegionDefect,
    TrainingSession,
    TrainingSessionFileSet
)

# these inlines are being used for many-to-many intermediary models(through models)
class MlModelDefectInline(admin.TabularInline):
    model = MlModelDefect
    extra = 1  # number of new entries to show on the page


class UseCaseDefectInline(admin.TabularInline):
    model = UseCaseDefect
    extra = 1
    # TODO: add pagination, excluding as it loads all the files at once
    exclude = ["reference_files"]


class MlModelAdmin(admin.ModelAdmin):
    inlines = (MlModelDefectInline,)


class DefectAdmin(admin.ModelAdmin):
    inlines = (
        MlModelDefectInline,
        UseCaseDefectInline,
    )
    # TODO: add pagination, excluding as it loads all the files at once
    exclude = ["reference_files"]


class UseCaseAdmin(admin.ModelAdmin):
    inlines = (UseCaseDefectInline,)


class UseCaseDefectAdmin(admin.ModelAdmin):
    # TODO: add pagination, excluding as it loads all the files at once
    exclude = ["reference_files"]


admin_site.register(MlModel, MlModelAdmin)
admin_site.register(Defect, DefectAdmin)
admin_site.register(MlModelDefect)
admin_site.register(FileSet)
admin_site.register(File)
admin_site.register(FileRegion)
admin_site.register(FileRegionHistory)
admin_site.register(UseCase, UseCaseAdmin)
admin_site.register(UploadSession)
admin_site.register(UseCaseDefect, UseCaseDefectAdmin)
admin_site.register(UserClassification)
admin_site.register(UserClassificationDefect)
admin_site.register(UserDetection)
admin_site.register(UserDetectionRegion)
admin_site.register(UserDetectionRegionDefect)
admin_site.register(ModelClassification)
admin_site.register(ModelClassificationDefect)
admin_site.register(ModelDetection)
admin_site.register(ModelDetectionRegion)
admin_site.register(ModelDetectionRegionDefect)
admin_site.register(GTClassification)
admin_site.register(GTClassificationDefect)
admin_site.register(GTDetection)
admin_site.register(GTDetectionRegion)
admin_site.register(GTDetectionRegionDefect)
admin_site.register(TrainingSession)
admin_site.register(TrainingSessionFileSet)