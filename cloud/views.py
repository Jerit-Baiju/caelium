import hashlib

from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cloud.models import CloudFile, Directory, MediaFile
from cloud.serializers import (
    BreadcrumbSerializer,
    CloudFileSerializer,
    DirectorySerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def explorer_view(request):
    """
    API endpoint to browse directories and files.
    Returns directories, files, breadcrumbs, and current directory info.
    Query params:
        - parent: UUID of parent directory (optional, if not provided returns root level)
    """
    parent_id = request.GET.get("parent", None)
    user = request.user

    # Get current directory
    current_directory = None
    if parent_id:
        try:
            current_directory = Directory.objects.get(id=parent_id, owner=user)
        except Directory.DoesNotExist:
            return Response(
                {"error": "Directory not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Get subdirectories
    if current_directory:
        directories = Directory.objects.filter(parent=current_directory, owner=user).order_by("name")
    else:
        # Root level - directories with no parent
        directories = Directory.objects.filter(parent=None, owner=user).order_by("name")

    # Get files in current directory
    if current_directory:
        files = CloudFile.objects.filter(
            directory=current_directory, owner=user, is_deleted=False
        ).order_by("name")
    else:
        # Root level - files with no directory
        files = CloudFile.objects.filter(directory=None, owner=user, is_deleted=False).order_by("name")

    # Build breadcrumbs
    breadcrumbs = []
    if current_directory:
        temp_dir = current_directory
        breadcrumb_list = []
        while temp_dir:
            breadcrumb_list.insert(0, temp_dir)
            temp_dir = temp_dir.parent
        breadcrumbs = BreadcrumbSerializer(breadcrumb_list, many=True).data

    # Serialize data
    directories_data = DirectorySerializer(directories, many=True).data
    files_data = CloudFileSerializer(files, many=True).data

    response_data = {
        "directories": directories_data,
        "files": files_data,
        "breadcrumbs": breadcrumbs,
        "current_directory": DirectorySerializer(current_directory).data if current_directory else None,
    }

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(["POST"])
def create_cloud_file(request):
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file:
            return HttpResponse("No file uploaded", status=400)

        # Calculate SHA-256 hash of the file
        sha256 = hashlib.sha256()
        for chunk in file.chunks():
            sha256.update(chunk)
        media_hash = sha256.hexdigest()

        # Create MediaFile instance
        media_file = MediaFile.objects.create(
            filename=file.name,
            media_hash=media_hash,
            size=file.size,
        )
        cloud_file = CloudFile.objects.create()
        return HttpResponse(f"Cloud file created with ID: {media_file.id}")
    return HttpResponse("")
