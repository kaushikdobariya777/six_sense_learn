from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.models import update_last_login
from django.utils.translation import ugettext_lazy as _
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers, exceptions
from rest_framework_simplejwt.serializers import PasswordField
from rest_framework_simplejwt.tokens import RefreshToken


class TokenObtainSerializer(serializers.Serializer):
    User = get_user_model()
    username_field = User.USERNAME_FIELD

    default_error_messages = {"no_active_account": _("No active account found with the given credentials")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # self.fields[self.username_field] = serializers.CharField()
        self.fields["email"] = serializers.EmailField(allow_null=True, default=None, allow_blank=True)
        self.fields["phone"] = PhoneNumberField(allow_blank=True, default=None, allow_null=True)
        self.fields["password"] = PasswordField()

    def validate(self, attrs):
        authenticate_kwargs = {
            "password": attrs["password"],
        }
        for field in self.User.AUTH_FIELDS:
            authenticate_kwargs[field] = attrs[field]
        try:
            authenticate_kwargs["request"] = self.context["request"]
        except KeyError:
            pass

        self.user = authenticate(**authenticate_kwargs)

        # Prior to Django 1.10, inactive users could be authenticated with the
        # default `ModelBackend`.  As of Django 1.10, the `ModelBackend`
        # prevents inactive users from authenticating.  App designers can still
        # allow inactive users to authenticate by opting for the new
        # `AllowAllUsersModelBackend`.  However, we explicitly prevent inactive
        # users from authenticating to enforce a reasonable policy and provide
        # sensible backwards compatibility with older Django versions.
        if self.user is None or not self.user.is_active:
            raise exceptions.AuthenticationFailed(
                self.error_messages["no_active_account"],
                "no_active_account",
            )

        return {}

    @classmethod
    def get_token(cls, user):
        raise NotImplementedError("Must implement `get_token` method for `TokenObtainSerializer` subclasses")

    # class Meta:
    #     model = get_user_model()
    #     fields = get_user_model().AUTH_FIELDS + ('password',)


class TokenObtainPairSerializer(TokenObtainSerializer):
    @classmethod
    def get_token(cls, user):
        return RefreshToken.for_user(user)

    def validate(self, attrs):
        data = super().validate(attrs)

        refresh = self.get_token(self.user)

        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)
        update_last_login(None, self.user)
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
