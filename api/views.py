import os
import subprocess
from http import server

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import UntypedToken

from api.models import Server
from api.serializers import ServerSerializer


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
def ping_view(request):
    return Response({"detail": "pong"}, status=status.HTTP_200_OK)


@api_view(["POST"])
def update_release_view(request):
    if "secret" not in request.data:
        return Response({"error": "Secret not provided."}, status=status.HTTP_400_BAD_REQUEST)

    if request.data["secret"] == settings.SECRET_KEY:
        UPDATE_SCRIPT_PATH = os.path.join(settings.BASE_DIR, "update.sh")
        if not os.path.exists(UPDATE_SCRIPT_PATH):
            return Response({"error": "Update script not found on server."}, status=status.HTTP_424_FAILED_DEPENDENCY)
        try:
            # Run the script in the background so the HTTP request returns immediately.
            # We don't wait for it to finish.
            # Ensure the script is executable: chmod +x update.sh
            subprocess.Popen([UPDATE_SCRIPT_PATH], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            current_server = Server.objects.filter(base_url=settings.BASE_URL).first()
            if current_server:
                current_server.release_update_status = True
                current_server.save()
            else:
                return Response({"error": "Current server not found."}, status=status.HTTP_404_NOT_FOUND)
            return Response({"success": True, "message": "Update process started in background."})
        except Exception as e:
            # Log the error e
            return Response({"error": f"Failed to start update script: {e}"})
    else:
        return Response({"error": "Invalid secret."}, status=status.HTTP_403_FORBIDDEN)


@api_view(["POST"])
def update_release_failure_view(request):
    if "secret" not in request.data or "server_id" not in request.data:
        return Response({"error": "Secret or server_id not provided."}, status=status.HTTP_400_BAD_REQUEST)

    if request.data["secret"] == settings.SECRET_KEY:
        try:
            server = Server.objects.get(id=request.data["server_id"])
            server.release_update_status = False
            server.save()
            return Response({"success": True, "message": f"Server {server.name} marked as failed to update."})
        except Server.DoesNotExist:
            return Response({"error": "Server not found."}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({"error": "Invalid secret."}, status=status.HTTP_403_FORBIDDEN)


@api_view(["POST"])
def update_server_status(request):
    if "secret" not in request.data or "server_id" not in request.data or "status" not in request.data:
        return Response({"error": "Secret, server_id, or status not provided."}, status=status.HTTP_400_BAD_REQUEST)

    if request.data["secret"] == settings.SECRET_KEY:
        try:
            server = Server.objects.get(id=request.data["server_id"])
            server.active_status = request.data["status"]
            server.save()
            return Response({"success": True, "message": f"Server {server.name} status updated."})
        except Server.DoesNotExist:
            return Response({"error": "Server not found."}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({"error": "Invalid secret."}, status=status.HTTP_403_FORBIDDEN)


@api_view(["POST"])
def public_server_error_handler(request):
    if "server_id" not in request.data:
        return Response({"error": "server_id not provided."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        server = Server.objects.get(id=request.data["server_id"])
        if server.active_status:
            resp = requests.get(f"{server.base_url}/api/core/ping/", timeout=5)
            if resp.status_code != 200:
                server.active_status = False
                server.save()
                return Response({"success": True, "message": f"Server {server.name} marked as inactive due to error."})
            return Response({"success": True, "message": f"Server {server.name} error handled."})
        else:
            return Response({"message": f"Server {server.name} is already inactive."})
    except Server.DoesNotExist:
        return Response({"error": "Server not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["GET"])
def list_servers(request):
    server_data = ServerSerializer(Server.objects.all(), many=True).data
    return Response(server_data, status=status.HTTP_200_OK)
