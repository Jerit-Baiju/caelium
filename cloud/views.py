import hashlib
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from cloud.encryption import (
    decrypt_file_memory,
    encrypt_file_stream,
    generate_encryption_key,
    generate_nonce,
)
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

    # Check file size (5GB limit)
    MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024  # 5GB in bytes
    if uploaded_file.size > MAX_FILE_SIZE:
        return Response(
            {"error": f"File size exceeds maximum limit of 5GB. File size: {uploaded_file.size / (1024**3):.2f}GB"},
            status=status.HTTP_400_BAD_REQUEST,
        )

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
        # Calculate hash of original file
        sha256 = hashlib.sha256()
        original_size = 0

        # Read file in chunks to calculate hash
        for chunk in uploaded_file.chunks():
            sha256.update(chunk)
            original_size += len(chunk)

        file_hash = sha256.hexdigest()

        # Reset file pointer
        uploaded_file.seek(0)

        # Create MediaFile instance
        media_file = MediaFile(
            filename=uploaded_file.name,
            media_hash=file_hash,
            size=original_size,
            mime_type=uploaded_file.content_type or "application/octet-stream",
            is_encrypted=should_encrypt,
        )
        media_file.save()

        # Create directory for this file: media/cloud/{uuid}/
        file_dir = Path(settings.MEDIA_ROOT) / "cloud" / str(media_file.id)
        file_dir.mkdir(parents=True, exist_ok=True)

        # Determine output filename
        output_filename = "encrypted" if should_encrypt else uploaded_file.name
        output_path = file_dir / output_filename

        if should_encrypt:
            # Generate encryption key and nonce
            encryption_key = generate_encryption_key()
            nonce = generate_nonce()

            # Encrypt and save file
            with open(output_path, "wb") as output_file:
                encrypted_size = encrypt_file_stream(uploaded_file, output_file, encryption_key, nonce)

            # Store encryption parameters
            media_file.encryption_key = encryption_key
            media_file.encryption_nonce = nonce
            media_file.encrypted_size = encrypted_size
            media_file.save()
        else:
            # Save file without encryption
            with open(output_path, "wb") as output_file:
                for chunk in uploaded_file.chunks():
                    output_file.write(chunk)

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
    Preview a file (with decryption if needed).
    Returns the file content for preview purposes.
    """
    user = request.user

    try:
        cloud_file = CloudFile.objects.get(id=file_id, owner=user, is_deleted=False)
    except CloudFile.DoesNotExist:
        return Response({"error": "File not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

    if not cloud_file.media:
        return Response({"error": "File media not found"}, status=status.HTTP_404_NOT_FOUND)

    media = cloud_file.media
    file_path = Path(settings.MEDIA_ROOT) / "cloud" / str(media.id)

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
        cloud_file.last_accessed_at = None
        cloud_file.save()

        return response

    except Exception as e:
        return Response({"error": f"Failed to preview file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def download_file(request, file_id):
    """
    Download a file (with decryption if needed).
    Returns the file for download.
    """
    user = request.user

    try:
        cloud_file = CloudFile.objects.get(id=file_id, owner=user, is_deleted=False)
    except CloudFile.DoesNotExist:
        return Response({"error": "File not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

    if not cloud_file.media:
        return Response({"error": "File media not found"}, status=status.HTTP_404_NOT_FOUND)

    media = cloud_file.media
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

        response["Content-Disposition"] = f'attachment; filename="{cloud_file.name}"'

        # Update accessed_at timestamp
        media.accessed_at = None  # Django will set auto_now field
        media.save()
        cloud_file.last_accessed_at = None
        cloud_file.save()

        return response

    except Exception as e:
        return Response({"error": f"Failed to download file: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
