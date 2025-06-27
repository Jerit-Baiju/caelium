from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.models import Follow
from base.models import Comment, Like, Post, Task
from base.serializers import CommentSerializer, LikeSerializer, PostSerializer, TaskSerializer


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Task.objects.filter(owner=self.request.user, completed=False)


class PostViewSet(ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return posts based on action"""
        user = self.request.user

        if self.action == "feed":
            # Get posts from users that the current user follows + own posts
            following_users = Follow.objects.filter(follower=user).values_list("followed", flat=True)
            return (
                Post.objects.filter(Q(owner__in=following_users) | Q(owner=user))
                .select_related("owner")
                .prefetch_related("likes", "comments")
                .order_by("-created_at")
            )

        elif self.action == "user_posts":
            # Get posts for a specific user
            user_id = self.request.query_params.get("user_id")
            if user_id:
                return Post.objects.filter(owner_id=user_id).select_related("owner").order_by("-created_at")
            return Post.objects.filter(owner=user).select_related("owner").order_by("-created_at")

        else:
            # Default: all posts
            return Post.objects.select_related("owner").prefetch_related("likes", "comments").order_by("-created_at")

    @action(detail=False, methods=["get"])
    def feed(self, request):
        """Get posts for the user's feed (following + own posts)"""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def user_posts(self, request):
        """Get posts for a specific user"""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        """Like or unlike a post"""
        post = self.get_object()
        user = request.user

        like, created = Like.objects.get_or_create(post=post, user=user)

        if not created:
            # Unlike the post
            like.delete()
            return Response({"message": "Post unliked", "liked": False, "likes_count": post.likes_count()})
        else:
            # Like the post
            return Response(
                {"message": "Post liked", "liked": True, "likes_count": post.likes_count()}, status=status.HTTP_201_CREATED
            )

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        """Get comments for a post or add a new comment"""
        post = self.get_object()

        if request.method == "GET":
            comments = Comment.objects.filter(post=post).select_related("owner").order_by("-created_at")
            serializer = CommentSerializer(comments, many=True, context={"request": request})
            return Response(serializer.data)

        elif request.method == "POST":
            serializer = CommentSerializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                serializer.save(post=post)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LikeViewSet(ModelViewSet):
    serializer_class = LikeSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Like.objects.filter(user=self.request.user)


class CommentViewSet(ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Comment.objects.filter(owner=self.request.user)
