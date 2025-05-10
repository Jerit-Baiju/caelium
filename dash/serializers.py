from rest_framework import serializers
from accounts.models import User


class DashboardUserSerializer(serializers.ModelSerializer):
    """Serializer for users in the dashboard."""
    
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "name",
            "avatar",
            "is_online",
            "last_seen",
            "date_joined",
            "is_superuser",
            "is_staff",
        ]
        read_only_fields = ["date_joined"]