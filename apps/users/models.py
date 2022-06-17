from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import ugettext_lazy as _

from sixsense.settings import AUTH_USER_MODEL as User
from common.models import Base


class SubOrganization(Base):
    name = models.CharField(max_length=30)
    code = models.CharField(max_length=15)
    address = models.TextField()
    users = models.ManyToManyField(User, through="OrganizationUser", through_fields=("sub_organization", "user"))

    def link_users(self, user_ids, user):
        self.users.clear()
        for user_id in user_ids:
            user = get_user_model().objects.filter(id=user_id).first()
            if user:
                self.users.add(user)
        self.updated_by = user

    class Meta:
        db_table = "ss_users_sub_organization"

    def __str__(self):
        return self.name


class OrganizationUser(models.Model):
    user = models.ForeignKey(User, related_name="sub_organizations", on_delete=models.CASCADE)
    sub_organization = models.ForeignKey(SubOrganization, on_delete=models.CASCADE, null=True)
    created_ts = models.DateTimeField(_("Created Date"), auto_now_add=True, null=True)

    class Meta:
        db_table = "ss_users_user_sub_organization"
        unique_together = ("sub_organization", "user")
