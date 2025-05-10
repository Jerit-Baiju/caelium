from django.contrib.auth import authenticate
from django.utils import timezone
from datetime import timedelta
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from chats.models import Chat, Message
from cloud.models import File


class LoginView(APIView):
    permission_classes = (permissions.AllowAny,)

    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        password = request.data.get("password")
        user = authenticate(username=email, password=password)
        if user is not None and user.is_superuser is True:
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            )
        return Response({"error": "Invalid Credentials"}, status=status.HTTP_401_UNAUTHORIZED)


class Stats(APIView):
    permission_classes = (permissions.IsAdminUser,)

    def get(self, request, *args, **kwargs):
        now = timezone.now()

        def get_week_range():
            start_of_this_week = now - timedelta(days=now.weekday())
            start_of_this_week = start_of_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_last_week = start_of_this_week - timedelta(days=7)
            return start_of_this_week, start_of_last_week

        def get_month_range():
            first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month = (first_of_this_month - timedelta(days=1)).replace(day=1)
            return first_of_this_month, last_month

        def calc_trend(current, prev):
            if prev == 0:
                return 100.0 if current > 0 else 0.0
            return round(((current - prev) / prev) * 100, 1)

        # Weekly stats
        week_start_current, week_start_prev = get_week_range()
        users_current_week = User.objects.filter(date_joined__gte=week_start_current).count()
        users_prev_week = User.objects.filter(date_joined__gte=week_start_prev, date_joined__lt=week_start_current).count()
        messages_current_week = Message.objects.filter(timestamp__gte=week_start_current).count()
        messages_prev_week = Message.objects.filter(timestamp__gte=week_start_prev, timestamp__lt=week_start_current).count()
        chats_current_week = Chat.objects.filter(updated_time__gte=week_start_current).count()
        chats_prev_week = Chat.objects.filter(updated_time__gte=week_start_prev, updated_time__lt=week_start_current).count()
        cloud_files_current_week = File.objects.filter(created_at__gte=week_start_current).count()
        cloud_files_prev_week = File.objects.filter(created_at__gte=week_start_prev, created_at__lt=week_start_current).count()

        weekly = {
            "users": users_current_week,
            "users_trend": calc_trend(users_current_week, users_prev_week),
            "messages": messages_current_week,
            "messages_trend": calc_trend(messages_current_week, messages_prev_week),
            "chats": chats_current_week,
            "chats_trend": calc_trend(chats_current_week, chats_prev_week),
            "cloudFiles": cloud_files_current_week,
            "cloudFiles_trend": calc_trend(cloud_files_current_week, cloud_files_prev_week),
        }

        # Monthly stats
        month_start_current, month_start_prev = get_month_range()
        users_current_month = User.objects.filter(date_joined__gte=month_start_current).count()
        users_prev_month = User.objects.filter(date_joined__gte=month_start_prev, date_joined__lt=month_start_current).count()
        messages_current_month = Message.objects.filter(timestamp__gte=month_start_current).count()
        messages_prev_month = Message.objects.filter(timestamp__gte=month_start_prev, timestamp__lt=month_start_current).count()
        chats_current_month = Chat.objects.filter(updated_time__gte=month_start_current).count()
        chats_prev_month = Chat.objects.filter(updated_time__gte=month_start_prev, updated_time__lt=month_start_current).count()
        cloud_files_current_month = File.objects.filter(created_at__gte=month_start_current).count()
        cloud_files_prev_month = File.objects.filter(created_at__gte=month_start_prev, created_at__lt=month_start_current).count()

        monthly = {
            "users": users_current_month,
            "users_trend": calc_trend(users_current_month, users_prev_month),
            "messages": messages_current_month,
            "messages_trend": calc_trend(messages_current_month, messages_prev_month),
            "chats": chats_current_month,
            "chats_trend": calc_trend(chats_current_month, chats_prev_month),
            "cloudFiles": cloud_files_current_month,
            "cloudFiles_trend": calc_trend(cloud_files_current_month, cloud_files_prev_month),
        }

        stats = {
            "total": {
                "users": User.objects.count(),
                "messages": Message.objects.count(),
                "chats": Chat.objects.count(),
                "cloudFiles": File.objects.count(),
            },
            "weekly": weekly,
            "monthly": monthly
        }
        return Response(stats)
