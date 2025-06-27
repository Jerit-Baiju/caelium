import os

import jwt
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveAPIView, RetrieveUpdateAPIView, UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import FCMToken, Follow, GoogleToken, User
from accounts.serializers import FCMTokenSerializer, FollowListSerializer, FollowSerializer, UserSerializer
from base.utils import log_admin
from chats.models import Chat, Message


class GoogleLoginUrl(APIView):
    def get(self, request):
        request_url = requests.Request(
            "GET",
            "https://accounts.google.com/o/oauth2/v2/auth",
            params={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "redirect_uri": f"{os.environ['CLIENT_HOST']}/api/auth/callback/google",
                "scope": "https://www.googleapis.com/auth/userinfo.email "
                "https://www.googleapis.com/auth/userinfo.profile",
                "access_type": "offline",
                "response_type": "code",
                "prompt": "consent",
                "include_granted_scopes": "true",
            },
        )
        url = request_url.prepare().url
        return Response({"url": url})


def get_auth_tokens(code, redirect_uri):
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        params={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    return response.json()


def refresh_access(refresh_token):
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        params={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    return response.json()


class GoogleLogin(APIView):
    def post(self, request):
        code = request.data.get("code")
        token_data = get_auth_tokens(code, f"{os.environ['CLIENT_HOST']}/api/auth/callback/google")

        # Check if id_token exists in the response
        if "id_token" not in token_data:
            log_admin(f"Google login failed: Missing id_token in response. Received: {token_data}")
            return Response(
                {"error": "Authentication failed. Invalid response from Google."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            data = jwt.decode(token_data["id_token"], options={"verify_signature": False})
            email = data["email"]
            name = data["name"]
            google_access_token = token_data["access_token"]
            google_refresh_token = token_data.get("refresh_token", "")  # Handle case when refresh token is not provided

            # Generate username based on email if not provided
            username = email.split("@")[0]

            try:
                user, created = User.objects.get_or_create(email=email)
                if created:
                    user.name = name
                    user.username = username
                    user.save()
                    admin_user = User.objects.get(email="app@caelium.co")
                    chat = Chat.objects.create()
                    chat.participants.add(admin_user, user)
                    chat.save()

                    # Send the personalized welcome message
                    Message.objects.create(
                        chat=chat,
                        sender=admin_user,
                        type="txt",
                        content=(
                            f"Hi {name},\n\n"
                            f"Welcome to Caelium! 🌟 We're thrilled to have you on board. "
                            f"Caelium is all about building a connected and innovative community, "
                            f"and we're excited to see what we can achieve together.\n\n"
                            f"If you have any questions, feedback, or if you ever need help, feel free to reach out. "
                            f"You can send messages or report any issues directly here, and we'll be happy to assist you.\n\n"
                            f"Your journey with Caelium starts now, and we can't wait to see you grow within our platform! 🚀\n\n"
                            f"Best regards,\n"
                            f"The Caelium Team"
                        ),
                    )

                    # Attempt to download the user's avatar if available
                    try:
                        response = requests.get(data["picture"], timeout=10)
                        if response.status_code == 200:
                            user.avatar.save(f"{email}.png", ContentFile(response.content), save=True)
                    except requests.exceptions.RequestException as e:
                        print(f"Error downloading avatar: {e}")

            except IntegrityError:
                user = User.objects.get(email=email)

            # Update GoogleToken with access and refresh tokens
            google_token, _ = GoogleToken.objects.get_or_create(user=user)
            google_token.access_token = google_access_token
            google_token.refresh_token = google_refresh_token
            google_token.save()

            # Create JWT tokens for the user
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            log_admin(f"Logged in user: {user.name}")
            return Response(
                {
                    "access": access_token,
                    "refresh": refresh_token,
                },
                status=status.HTTP_200_OK,
            )
        except jwt.DecodeError:
            log_admin(f"Google login failed: Unable to decode id_token. Received: {token_data}")
            return Response(
                {"error": "Authentication failed. Invalid id_token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserUpdateView(UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def perform_update(self, serializer):
        user_instance = serializer.instance
        if user_instance == self.request.user:
            serializer.save()
        return Response(
            {"error": "You are not authorized to update this user's data."},
            status=status.HTTP_403_FORBIDDEN,
        )


class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer

    def get_queryset(self):
        return User.objects.all()


class UserDetailsView(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_serializer_context(self):
        """Add request context for follow-related fields"""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context


class FCMTokenUpdateView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FCMTokenSerializer

    def get_object(self):
        # Try to get the FCM token for the current user, or create a new one
        obj, _ = FCMToken.objects.get_or_create(user=self.request.user)
        return obj


class FollowViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing follow/unfollow operations
    """

    serializer_class = FollowSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return follows based on the requested action"""
        user = self.request.user
        action = self.action

        if action == "following":
            # Users that the current user is following
            return Follow.objects.filter(follower=user).select_related("followed")
        elif action == "followers":
            # Users that are following the current user
            return Follow.objects.filter(followed=user).select_related("follower")
        else:
            # Default queryset for admin or other uses
            return Follow.objects.all()

    def get_serializer_class(self):
        """Use lightweight serializer for list views"""
        if self.action in ["list", "following", "followers"]:
            return FollowListSerializer
        return FollowSerializer

    @action(detail=False, methods=["get"])
    def following(self, request):
        """Get list of users that the current user is following"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": queryset.count(), "results": serializer.data})

    @action(detail=False, methods=["get"])
    def followers(self, request):
        """Get list of users that are following the current user"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": queryset.count(), "results": serializer.data})

    @action(detail=False, methods=["post"])
    def follow_user(self, request):
        """Follow a user"""
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_to_follow = get_object_or_404(User, id=user_id)

            # Check if user is trying to follow themselves
            if user_to_follow == request.user:
                return Response({"error": "You cannot follow yourself"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if already following
            if request.user.is_following(user_to_follow):
                return Response({"error": "You are already following this user"}, status=status.HTTP_400_BAD_REQUEST)

            # Create follow relationship
            follow = Follow.objects.create(follower=request.user, followed=user_to_follow)

            serializer = FollowSerializer(follow, context={"request": request})
            return Response(
                {"message": f"You are now following {user_to_follow.username}", "follow": serializer.data},
                status=status.HTTP_201_CREATED,
            )

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"])
    def unfollow_user(self, request):
        """Unfollow a user"""
        user_id = request.data.get("user_id")
        if not user_id:
            return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user_to_unfollow = get_object_or_404(User, id=user_id)

            # Check if following
            follow = Follow.objects.filter(follower=request.user, followed=user_to_unfollow).first()

            if not follow:
                return Response({"error": "You are not following this user"}, status=status.HTTP_400_BAD_REQUEST)

            follow.delete()

            return Response({"message": f"You have unfollowed {user_to_unfollow.username}"}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"])
    def mutual_followers(self, request):
        """Get mutual followers between current user and another user"""
        user_id = request.query_params.get("user_id")
        if not user_id:
            return Response({"error": "user_id parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            other_user = get_object_or_404(User, id=user_id)

            # Use the optimized method from the model
            mutual_users = request.user.get_mutual_followers_with(other_user)

            serializer = UserSerializer(mutual_users, many=True, context={"request": request})

            return Response({"count": mutual_users.count(), "mutual_followers": serializer.data})

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"])
    def suggestions(self, request):
        """Get follow suggestions for the current user"""
        limit = int(request.query_params.get("limit", 10))

        suggested_users = request.user.get_follow_suggestions(limit=limit)
        serializer = UserSerializer(suggested_users, many=True, context={"request": request})

        return Response({"count": len(suggested_users), "suggestions": serializer.data})

    @action(detail=False, methods=["post"])
    def bulk_follow_check(self, request):
        """Check if current user is following multiple users at once"""
        user_ids = request.data.get("user_ids", [])
        if not user_ids or not isinstance(user_ids, list):
            return Response({"error": "user_ids list is required"}, status=status.HTTP_400_BAD_REQUEST)

        follow_status = request.user.bulk_follow_check(user_ids)

        return Response({"follow_status": follow_status})
