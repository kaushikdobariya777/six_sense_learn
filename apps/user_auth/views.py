import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.user_auth.permissions import IsTokenValid
from apps.user_auth.models import BlackListedToken
from apps.user_auth.serializers import TokenObtainPairSerializer, ChangePasswordSerializer

logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = TokenObtainPairSerializer


@api_view(["POST"])
@permission_classes((IsTokenValid,))
def logout(request):
    try:
        user_id = request.user.id
        logger.info("'%s' user id logout request.", user_id)
        logger.info("Adding user '%s' token in black listed token." % user_id)
        BlackListedToken.objects.create(token=str(request.auth), user=request.user)
        logger.info("User '%s' logged out successfully.")
        return Response({"msg": "'%s' logged out successfully." % user_id}, status=status.HTTP_200_OK)
    except Exception as ex:
        logger.critical("Caught exception in {}".format(__file__), exc_info=True)
        return Response(
            {"msg": ex.args},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes((IsTokenValid,))
def change_password(request):
    logger.info("Password change request from user '%s'" % request.user)
    serializer = ChangePasswordSerializer(data=request.data)
    user = request.user
    if serializer.is_valid():
        if not user.check_password(serializer.data.get("old_password")):
            return Response({"msg": "'old_password' is Wrong password."}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.data.get("new_password"))
        user.save()
        logger.info("Password changed successfully for user '%s'" % user.username)
        return Response(
            {"msg": "Password changed successfully for user '%s'." % user.username}, status=status.HTTP_200_OK
        )
    logger.error("Failed on password change request for user '%s'" % user.username)
    logger.error(serializer.errors)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
