from rest_framework.serializers import ModelSerializer, SerializerMethodField

from accounts.models import FCMToken, Follow, User


class UserSerializer(ModelSerializer):
    followers_count = SerializerMethodField()
    following_count = SerializerMethodField()
    is_following = SerializerMethodField()
    is_followed_by = SerializerMethodField()

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
            "followers_count",
            "following_count",
            "is_following",
            "is_followed_by",
        ]

    def get_followers_count(self, obj):
        return obj.get_followers_count()

    def get_following_count(self, obj):
        return obj.get_following_count()

    def get_is_following(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return request.user.is_following(obj)
        return False

    def get_is_followed_by(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.is_following(request.user)
        return False


class FollowSerializer(ModelSerializer):
    follower = UserSerializer(read_only=True)
    followed = UserSerializer(read_only=True)

    class Meta:
        model = Follow
        fields = ["id", "follower", "followed", "created_at"]
        read_only_fields = ["id", "created_at"]


class FollowListSerializer(ModelSerializer):
    """Lightweight serializer for listing follows without nested user data"""

    follower_username = SerializerMethodField()
    followed_username = SerializerMethodField()

    class Meta:
        model = Follow
        fields = ["id", "follower", "followed", "follower_username", "followed_username", "created_at"]

    def get_follower_username(self, obj):
        return obj.follower.username

    def get_followed_username(self, obj):
        return obj.followed.username


class FCMTokenSerializer(ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ["token"]
