from rest_framework.serializers import ModelSerializer, SerializerMethodField

from accounts.models import FCMToken, SpecialUser, User


class UserSerializer(ModelSerializer):
    is_special_user = SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "avatar",
            "location",
            "gender",
            "birthdate",
            "last_seen",
            "username",
            "is_special_user",
        ]

    def get_is_special_user(self, obj):
        """Check if user's email is in the SpecialUser table"""
        return SpecialUser.is_special_user(obj.email)


class FCMTokenSerializer(ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ["token"]
