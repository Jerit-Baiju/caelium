import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from api.models import Server


@api_view(["POST"])
@permission_classes([IsAdminUser])
def verify_jwt_user(request):
    """
    Accepts a JWT token in the Authorization header, verifies it, and checks if it is a real user.
    """
    token = request.data.get("accessToken")
    if not token:
        return Response({"detail": "accessToken not provided in POST data."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        UntypedToken(token)  # This will raise if the token is invalid
        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        user = jwt_auth.get_user(validated_token)
        if user and user.is_active:
            return Response({"valid": True, "user_id": user.id, "username": user.username})
        else:
            return Response({"detail": "User not found or inactive."}, status=status.HTTP_404_NOT_FOUND)
    except (InvalidToken, TokenError) as e:
        return Response({"detail": "Invalid token.", "error": str(e)}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({"detail": "Error verifying token.", "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_hps(request):
    for server in Server.objects.order_by("priority"):
        response = requests.get(f"{server.base_url}/api/internals/ping/", timeout=2)
        if response.status_code == 200:
            return Response({"base_url": server.base_url}, status=status.HTTP_200_OK)
    return Response({"detail": "No active servers found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def ping_view(request):
    return Response({"detail": "pong"}, status=status.HTTP_200_OK)
