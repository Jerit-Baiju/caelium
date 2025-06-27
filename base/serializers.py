from django.contrib.auth import get_user_model
from rest_framework import serializers

from base.models import Comment, Like, Post, Task

User = get_user_model()


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["name", "completed", "id"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class PostUserSerializer(serializers.ModelSerializer):
    """Lightweight user serializer for posts"""

    class Meta:
        model = User
        fields = ["id", "name", "username", "avatar"]


class PostSerializer(serializers.ModelSerializer):
    user = PostUserSerializer(source="owner", read_only=True)
    likes = serializers.SerializerMethodField()
    comments = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "user", "content", "image", "likes", "comments", "time", "is_liked", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_likes(self, obj):
        return obj.likes_count()

    def get_comments(self, obj):
        return obj.comments.count()

    def get_time(self, obj):
        """Return time in a format similar to your frontend expectation"""
        from django.utils import timezone

        now = timezone.now()
        diff = now - obj.created_at

        if diff.days > 0:
            return f"{diff.days}d"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}h"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}m"
        else:
            return "now"

    def get_is_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)


class LikeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Like
        fields = ["id", "post", "user", "created_at"]
        read_only_fields = ["id", "created_at"]


class CommentSerializer(serializers.ModelSerializer):
    owner = PostUserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "post", "owner", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        return super().create(validated_data)
