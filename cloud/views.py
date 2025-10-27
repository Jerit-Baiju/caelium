from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cloud.models import CloudFile, Directory, MediaFile
from cloud.serializers import BreadcrumbSerializer, CloudFileSerializer, DirectorySerializer
from cloud.utils.encryption import decrypt_file_memory
from cloud.utils.media import create_media_file


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
        files = CloudFile.objects.filter(directory=current_directory, owner=user, is_deleted=False).order_by("name")
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
@permission_classes([IsAuthenticated])
def upload_file(request):
    """
    Upload a single file with optional encryption.
    Accepts:
        - file: The file to upload
        - encrypt: Boolean (true/false) - whether to encrypt the file (default: false)
        - directory: UUID of parent directory (optional)
        - name: Custom name for the file (optional, defaults to filename)

    Returns:
        - CloudFile data with upload status
    """
    user = request.user

    # Get file from request
    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

    # Get parameters
    should_encrypt = request.POST.get("encrypt", "false").lower() == "true"
    directory_id = request.POST.get("directory", None)
    custom_name = request.POST.get("name", uploaded_file.name)

    # Validate directory if provided
    parent_directory = None
    if directory_id:
        try:
            parent_directory = Directory.objects.get(id=directory_id, owner=user)
        except Directory.DoesNotExist:
            return Response({"error": "Directory not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

    try:

        media_file = create_media_file(file=uploaded_file, folder="cloud", owner=user, should_encrypt=should_encrypt)

        # Create CloudFile entry
        cloud_file = CloudFile.objects.create(name=custom_name, owner=user, directory=parent_directory, media=media_file)

        # Return success response
        serializer = CloudFileSerializer(cloud_file)
        return Response(
            {"success": True, "message": "File uploaded successfully", "file": serializer.data},
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        # Clean up media file if created
        if "media_file" in locals():
            # Remove directory if created
            file_dir = Path(settings.MEDIA_ROOT) / "cloud" / str(media_file.id)
            if file_dir.exists():
                import shutil

                shutil.rmtree(file_dir)
            media_file.delete()

        return Response({"error": f"Failed to upload file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def preview_file(request, file_id):
    """
    Preview a media file (with decryption if needed).
    Returns the file content for preview purposes.
    Works directly with MediaFile ID.
    """
    user = request.user

    try:
        media = MediaFile.objects.get(id=file_id, is_deleted=False)

        # Debug information
        debug_info = {
            "file_exists": True,
            "media_id": str(media.id),
            "media_filename": media.filename,
            "media_owner_id": str(media.owner.id),
            "media_owner_email": media.owner.email,
            "current_user_id": str(user.id),
            "current_user_email": user.email,
            "is_owner": media.owner == user,
            "media_privacy": media.privacy,
            "media_is_encrypted": media.is_encrypted,
            "is_deleted": media.is_deleted,
        }

        # Check access: owner or public media file
        if media.owner != user and media.privacy != "public":
            debug_info["access_denied_reason"] = "Not owner and file is not public"
            return Response(
                {"error": "File not found or access denied", "debug": debug_info}, status=status.HTTP_404_NOT_FOUND
            )

        debug_info["access_granted"] = True

    except MediaFile.DoesNotExist:
        return Response(
            {
                "error": "File not found or access denied",
                "debug": {
                    "file_exists": False,
                    "file_id": file_id,
                    "current_user_id": str(user.id),
                    "current_user_email": user.email,
                },
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    file_path = Path(settings.MEDIA_ROOT) / media.folder / str(media.id)

    if media.is_encrypted:
        encrypted_file = file_path / "encrypted"
    else:
        encrypted_file = file_path / media.filename

    if not encrypted_file.exists():
        return Response({"error": "Physical file not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        if media.is_encrypted:
            # Decrypt file in memory for preview
            with open(encrypted_file, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = decrypt_file_memory(encrypted_data, bytes(media.encryption_key), bytes(media.encryption_nonce))

            # Return decrypted content
            response = HttpResponse(decrypted_data, content_type=media.mime_type or "application/octet-stream")
        else:
            # Return file directly
            response = FileResponse(open(encrypted_file, "rb"), content_type=media.mime_type or "application/octet-stream")

        response["Content-Disposition"] = f'inline; filename="{media.filename}"'

        # Update accessed_at timestamp
        media.accessed_at = None  # Django will set auto_now field
        media.save()

        return response

    except Exception as e:
        return Response({"error": f"Failed to preview file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_file(request, file_id):
    """
    Download a media file (with decryption if needed).
    Returns the file for download.
    Works directly with MediaFile ID.
    """
    user = request.user

    try:
        media = MediaFile.objects.get(id=file_id, is_deleted=False)

        # Check access: owner or public media file
        if media.owner != user and media.privacy != "public":
            return Response({"error": "File not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

    except MediaFile.DoesNotExist:
        return Response({"error": "File not found or access denied"}, status=status.HTTP_404_NOT_FOUND)
    file_path = Path(settings.MEDIA_ROOT) / "cloud" / str(media.id)

    if media.is_encrypted:
        encrypted_file = file_path / "encrypted"
    else:
        encrypted_file = file_path / media.filename

    if not encrypted_file.exists():
        return Response({"error": "Physical file not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        if media.is_encrypted:
            # Decrypt file
            with open(encrypted_file, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = decrypt_file_memory(encrypted_data, bytes(media.encryption_key), bytes(media.encryption_nonce))

            # Return decrypted content
            response = HttpResponse(decrypted_data, content_type=media.mime_type or "application/octet-stream")
        else:
            # Return file directly
            response = FileResponse(open(encrypted_file, "rb"), content_type=media.mime_type or "application/octet-stream")

        response["Content-Disposition"] = f'attachment; filename="{media.filename}"'

        # Update accessed_at timestamp
        media.accessed_at = None  # Django will set auto_now field
        media.save()

        return response

    except Exception as e:
        return Response({"error": f"Failed to download file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
