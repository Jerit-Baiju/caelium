from rest_framework import serializers

from cloud.models import CloudFile, Directory, MediaFile


class MediaSerializer(serializers.ModelSerializer):
    """
    Serializer for media objects.
    """

    class Meta:
        model = MediaFile
        fields = ["location"]


class DirectorySerializer(serializers.ModelSerializer):
    """
    Serializer for directory objects in explorer view.
    """
    class Meta:
        model = Directory
        fields = ["id", "name", "created_at", "modified_at"]


class CloudFileSerializer(serializers.ModelSerializer):
    """
    Serializer for cloud file objects in explorer view.
    """
    size = serializers.SerializerMethodField()
    mime_type = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = CloudFile
        fields = ["id", "name", "size", "mime_type", "download_url", "created_at", "modified_at"]

    def get_size(self, obj):
        if obj.media:
            return obj.media.size
        return 0

    def get_mime_type(self, obj):
        if obj.media and obj.media.filename:
            # Simple mime type detection based on file extension
            ext = obj.media.filename.lower().split('.')[-1]
            mime_types = {
                'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'gif': 'image/gif',
                'bmp': 'image/bmp', 'webp': 'image/webp', 'svg': 'image/svg+xml',
                'mp4': 'video/mp4', 'avi': 'video/x-msvideo', 'mov': 'video/quicktime',
                'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'ogg': 'audio/ogg',
                'pdf': 'application/pdf',
                'zip': 'application/zip', 'rar': 'application/x-rar-compressed',
                'js': 'text/javascript', 'ts': 'text/typescript', 'py': 'text/x-python',
                'html': 'text/html', 'css': 'text/css', 'json': 'application/json',
                'txt': 'text/plain',
            }
            return mime_types.get(ext, 'application/octet-stream')
        return 'application/octet-stream'

    def get_download_url(self, obj):
        # Return a placeholder URL that the frontend can use
        # You'll need to implement the actual download endpoint
        return f"/api/cloud/files/{obj.id}/download/"


class BreadcrumbSerializer(serializers.ModelSerializer):
    """
    Serializer for breadcrumb navigation.
    """
    class Meta:
        model = Directory
        fields = ["id", "name"]
