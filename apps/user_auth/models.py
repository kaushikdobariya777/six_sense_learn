from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _


# Create your models here.
from phonenumber_field.modelfields import PhoneNumberField

from apps.user_auth.managers import UserManager
from common.models import Base


class User(AbstractBaseUser, PermissionsMixin, Base):
    email = models.EmailField(
        unique=True,
    )
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
    )
    phone = PhoneNumberField(_("phone number"), blank=True, default=None, null=True, unique=True)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    # REQUIRED_FIELDS = ['first_name', ]
    AUTH_FIELDS = (
        "email",
        "phone",
    )

    def __str__(self):
        return self.display_name or self.email

    @property
    def display_name(self):
        name = self.first_name + " " + self.last_name if self.first_name or self.last_name else ""
        username = self.email.split("@")[0]
        return name.title() or username


class BlackListedToken(Base):
    token = models.CharField(max_length=500)
    user = models.ForeignKey(User, related_name="black_token", on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("token", "user")
        # db_table = 'ss_users_blacklisted_tokens'
