from django.contrib.auth import get_user_model


class EmailMobileAuthentication(object):
    User = get_user_model()

    def authenticate(self, request, **credentials):
        try:
            filter = {}
            for key in self.User.AUTH_FIELDS:
                if key in credentials and credentials[key] is not None:
                    filter[key] = credentials[key]
            if credentials.get("username", None):
                filter[self.User.USERNAME_FIELD] = credentials["username"]
            if not bool(filter):
                return None
            user = self.User.objects.get(**filter)
            if user.check_password(credentials.get("password", None)):
                return user
            return None
        except self.User.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return self.User.objects.get(id=user_id)
        except Exception:
            return None
