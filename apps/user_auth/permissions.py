from rest_framework.permissions import IsAuthenticated

from apps.user_auth.models import BlackListedToken


class IsTokenValid(IsAuthenticated):
    message = "Signature has expired."

    def has_permission(self, request, view):
        if not super(IsTokenValid, self).has_permission(request, view):
            return False
        user_id = request.user.id
        token = request.auth
        is_allowed_user = True
        try:
            is_black_listed = BlackListedToken.objects.get(user=user_id, token=token)
            if is_black_listed:
                is_allowed_user = False
        except BlackListedToken.DoesNotExist:
            is_allowed_user = True
        return is_allowed_user
