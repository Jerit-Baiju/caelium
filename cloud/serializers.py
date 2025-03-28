from rest_framework import serializers

from accounts.serializers import UserSerializer
from cloud.models import Directory, File, SharedItem


class DirectorySerializer(serializers.ModelSerializer):
    owner_details = UserSerializer(source="owner", read_only=True)
    path = serializers.ReadOnlyField()

    class Meta:
        model = Directory
        fields = ["id", "name", "owner", "owner_details", "parent", "created_at", "modified_at", "path"]
        read_only_fields = ["id", "created_at", "modified_at", "path"]


class FileSerializer(serializers.ModelSerializer):
    owner_details = UserSerializer(source="owner", read_only=True)
    path = serializers.ReadOnlyField()
    download_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = [
            "id",
            "name",
            "owner",
            "owner_details",
            "parent",
            "created_at",
            "path",
            "size",
            "mime_type",
            "download_url",
            "preview_url",
            "category",
            "drive_file_id"
        ]
        read_only_fields = [
            "id",
            "created_at",
            "path",
            "size",
            "encryption_key",
            "encryption_iv",
            "download_url",
            "preview_url",
            "category",
            "drive_file_id"
        ]
        extra_kwargs = {
            "encryption_key": {"write_only": True},
            "encryption_iv": {"write_only": True},
        }

    def get_download_url(self, obj):
        request = self.context.get("request")
        if request is None:
            return None

        # Ensure we're using the correct format for UUID
        return f"{request.build_absolute_uri('/api/cloud/files/')}{obj.id}/download/"

    def get_preview_url(self, obj):
        # Only provide preview URL for image files
        if not obj.mime_type or not obj.mime_type.startswith("image/"):
            return None

        request = self.context.get("request")
        if request is None:
            return None

        # Use the same download URL for preview
        return f"{request.build_absolute_uri('/api/cloud/files/')}{obj.id}/download/"


class SharedItemSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source="user", read_only=True)
    file_details = FileSerializer(source="file", read_only=True)
    directory_details = DirectorySerializer(source="directory", read_only=True)

    class Meta:
        model = SharedItem
        fields = [
            "id",
            "user",
            "user_details",
            "file",
            "file_details",
            "directory",
            "directory_details",
            "permission",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
