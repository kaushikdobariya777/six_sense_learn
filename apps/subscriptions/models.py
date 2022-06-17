import json
import os
from django.db.models import JSONField
from django.contrib.postgres.fields.array import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from common.models import Base
from apps.packs.models import Pack
from apps.users.models import SubOrganization
import jsonschema

# Create your models here.


class Subscription(Base):
    pack = models.ForeignKey(Pack, on_delete=models.PROTECT)
    sub_organization = models.ForeignKey(SubOrganization, on_delete=models.PROTECT)
    expires_at = models.DateTimeField()
    starts_at = models.DateTimeField()
    status = models.CharField(default="ACTIVE", max_length=100)
    file_set_meta_info = JSONField(default=dict, blank=True)
    overkill_defect_config = ArrayField(base_field=models.IntegerField(), default=list, blank=True)
    expected_automation = models.FloatField(default=0.93)

    def clean(self):
        if self.starts_at and self.expires_at:
            if self.starts_at > self.expires_at:
                raise ValidationError(
                    {
                        "starts_at": "Subscription can't start after it's expiration.",
                        "expires_at": "Subscription can't expire  before it's beginning.",
                    }
                )
        if self.file_set_meta_info:
            with open(os.path.join(os.path.dirname(__file__), "file_set_meta_info_schema.json"), "r") as file:
                schema = json.load(file)
                try:
                    jsonschema.validate(instance=self.file_set_meta_info, schema=schema)
                except jsonschema.ValidationError as e:
                    raise ValidationError({"file_set_meta_info": f"Invalid json schema: {e}"})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
