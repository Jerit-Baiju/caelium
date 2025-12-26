from pathlib import Path

from django.conf import settings
from django.core.cache import cache
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
def create_directory(request):
    """
    Create a new directory.
    Accepts:
        - name: Name of the directory (required)
        - parent: UUID of parent directory (optional, if not provided creates at root level)

    Returns:
        - Directory data with creation status
    """
    user = request.user

    # Get parameters
    directory_name = request.data.get("name", "").strip()
    parent_id = request.data.get("parent", None)

    # Validate directory name
    if not directory_name:
        return Response({"error": "Directory name is required"}, status=status.HTTP_400_BAD_REQUEST)

    if len(directory_name) > 255:
        return Response({"error": "Directory name is too long (max 255 characters)"}, status=status.HTTP_400_BAD_REQUEST)

    # Validate parent directory if provided
    parent_directory = None
    if parent_id:
        try:
            parent_directory = Directory.objects.get(id=parent_id, owner=user)
        except Directory.DoesNotExist:
            return Response(
                {"error": "Parent directory not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Check if directory with same name already exists in this location
    existing_dir = Directory.objects.filter(
        name=directory_name,
        parent=parent_directory,
        owner=user
    ).first()

    if existing_dir:
        return Response(
            {"error": f"A directory with name '{directory_name}' already exists in this location"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Create directory
        new_directory = Directory.objects.create(
            name=directory_name,
            owner=user,
            parent=parent_directory
        )

        # Return success response
        serializer = DirectorySerializer(new_directory)
        return Response(
            {
                "success": True,
                "message": "Directory created successfully",
                "directory": serializer.data
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to create directory: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initiate_chunked_upload(request):
    """
    Initiate a chunked file upload session.
    Accepts:
        - filename: The name of the file
        - file_size: Total size of the file in bytes
        - total_chunks: Total number of chunks that will be uploaded
        - encrypt: Boolean - whether to encrypt the file
        - directory: UUID of parent directory (optional)

    Returns:
        - upload_id: Unique identifier for this upload session
    """
    user = request.user

    filename = request.data.get("filename")
    file_size = request.data.get("file_size")
    total_chunks = request.data.get("total_chunks")
    should_encrypt = request.data.get("encrypt", False)
    directory_id = request.data.get("directory", None)

    if not all([filename, file_size, total_chunks]):
        return Response(
            {"error": "filename, file_size, and total_chunks are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate directory if provided
    parent_directory = None
    if directory_id:
        try:
            parent_directory = Directory.objects.get(id=directory_id, owner=user)
        except Directory.DoesNotExist:
            return Response(
                {"error": "Directory not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Generate unique upload ID
    import uuid
    upload_id = str(uuid.uuid4())

    # Store upload metadata in cache (expires in 24 hours)
    upload_metadata = {
        "user_id": str(user.id),
        "filename": filename,
        "file_size": int(file_size),
        "total_chunks": int(total_chunks),
        "should_encrypt": should_encrypt,
        "directory_id": directory_id,
        "chunks_received": [],
        "created_at": str(settings.USE_TZ),
    }

    cache.set(f"chunked_upload_{upload_id}", upload_metadata, timeout=86400)  # 24 hours

    # Create temporary directory for chunks
    temp_dir = Path(settings.MEDIA_ROOT) / "temp_chunks" / upload_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    return Response(
        {
            "success": True,
            "upload_id": upload_id,
            "message": "Chunked upload initiated",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_chunk(request, upload_id):
    """
    Upload a single chunk of a file.
    Accepts:
        - chunk: The chunk file data
        - chunk_number: The index of this chunk (0-based)

    Returns:
        - success status and chunk number confirmation
    """
    user = request.user

    # Retrieve upload metadata from cache
    upload_metadata = cache.get(f"chunked_upload_{upload_id}")

    if not upload_metadata:
        return Response(
            {"error": "Upload session not found or expired"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Verify user ownership
    if str(user.id) != upload_metadata["user_id"]:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_403_FORBIDDEN,
        )

    chunk = request.FILES.get("chunk")
    chunk_number = request.data.get("chunk_number")

    if not chunk or chunk_number is None:
        return Response(
            {"error": "chunk and chunk_number are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        chunk_number = int(chunk_number)
    except ValueError:
        return Response(
            {"error": "chunk_number must be an integer"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate chunk number
    if chunk_number < 0 or chunk_number >= upload_metadata["total_chunks"]:
        return Response(
            {"error": "Invalid chunk_number"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Save chunk to temporary directory
    temp_dir = Path(settings.MEDIA_ROOT) / "temp_chunks" / upload_id
    chunk_path = temp_dir / f"chunk_{chunk_number}"

    try:
        with open(chunk_path, "wb") as f:
            for data in chunk.chunks():
                f.write(data)

        # Update metadata with received chunk
        if chunk_number not in upload_metadata["chunks_received"]:
            upload_metadata["chunks_received"].append(chunk_number)
            upload_metadata["chunks_received"].sort()
            cache.set(f"chunked_upload_{upload_id}", upload_metadata, timeout=86400)

        return Response(
            {
                "success": True,
                "chunk_number": chunk_number,
                "chunks_received": len(upload_metadata["chunks_received"]),
                "total_chunks": upload_metadata["total_chunks"],
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to save chunk: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def finalize_chunked_upload(request, upload_id):
    """
    Finalize a chunked upload by assembling all chunks into final file.
    Creates the MediaFile and CloudFile entries.

    Returns:
        - CloudFile data
    """
    user = request.user

    # Retrieve upload metadata from cache
    upload_metadata = cache.get(f"chunked_upload_{upload_id}")

    if not upload_metadata:
        return Response(
            {"error": "Upload session not found or expired"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Verify user ownership
    if str(user.id) != upload_metadata["user_id"]:
        return Response(
            {"error": "Unauthorized"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Check all chunks received
    if len(upload_metadata["chunks_received"]) != upload_metadata["total_chunks"]:
        return Response(
            {
                "error": "Not all chunks received",
                "chunks_received": len(upload_metadata["chunks_received"]),
                "total_chunks": upload_metadata["total_chunks"],
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    temp_dir = Path(settings.MEDIA_ROOT) / "temp_chunks" / upload_id

    try:
        # Create a temporary file to assemble chunks
        import mimetypes
        mime_type = mimetypes.guess_type(upload_metadata["filename"])[0] or "application/octet-stream"

        # Assemble chunks into a single temporary file
        assembled_file_path = temp_dir / "assembled"
        with open(assembled_file_path, "wb") as assembled_file:
            for i in range(upload_metadata["total_chunks"]):
                chunk_path = temp_dir / f"chunk_{i}"
                if not chunk_path.exists():
                    raise FileNotFoundError(f"Chunk {i} not found")
                with open(chunk_path, "rb") as chunk_file:
                    assembled_file.write(chunk_file.read())

        # Create a file-like object for create_media_file
        class AssembledFile:
            def __init__(self, path, name, content_type):
                self.path = path
                self.name = name
                self.content_type = content_type
                self._file = None
                self._size = path.stat().st_size

            def __enter__(self):
                self._file = open(self.path, "rb")
                return self

            def __exit__(self, *args):
                if self._file:
                    self._file.close()

            def read(self, size=-1):
                if not self._file:
                    self._file = open(self.path, "rb")
                return self._file.read(size)

            def seek(self, position, whence=0):
                if not self._file:
                    self._file = open(self.path, "rb")
                return self._file.seek(position, whence)

            def chunks(self, chunk_size=8192):
                if not self._file:
                    self._file = open(self.path, "rb")
                self._file.seek(0)
                while True:
                    data = self._file.read(chunk_size)
                    if not data:
                        break
                    yield data

            @property
            def size(self):
                return self._size

            def close(self):
                if self._file:
                    self._file.close()
                    self._file = None

        assembled_file_obj = AssembledFile(
            assembled_file_path,
            upload_metadata["filename"],
            mime_type
        )

        # Get directory if specified
        parent_directory = None
        if upload_metadata["directory_id"]:
            try:
                parent_directory = Directory.objects.get(
                    id=upload_metadata["directory_id"],
                    owner=user
                )
            except Directory.DoesNotExist:
                pass

        # Create media file
        try:
            media_file = create_media_file(
                file=assembled_file_obj,
                folder="cloud",
                owner=user,
                should_encrypt=upload_metadata["should_encrypt"]
            )
        finally:
            # Ensure file is closed
            assembled_file_obj.close()

        # Check if media_file creation failed
        if not isinstance(media_file, MediaFile):
            # Clean up temporary files
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            cache.delete(f"chunked_upload_{upload_id}")
            
            if isinstance(media_file, Response):
                return media_file
            else:
                return Response(
                    {"error": "Failed to create media file"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        # Create CloudFile entry
        cloud_file = CloudFile.objects.create(
            name=upload_metadata["filename"],
            owner=user,
            directory=parent_directory,
            media=media_file
        )

        # Clean up temporary files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

        # Clear cache
        cache.delete(f"chunked_upload_{upload_id}")

        # Return success response
        serializer = CloudFileSerializer(cloud_file)
        return Response(
            {
                "success": True,
                "message": "File uploaded successfully",
                "file": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        # Clean up on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        cache.delete(f"chunked_upload_{upload_id}")

        return Response(
            {"error": f"Failed to finalize upload: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rename_directory(request, directory_id):
    """
    Rename a directory.
    Accepts:
        - name: New name for the directory
    """
    user = request.user
    new_name = request.data.get("name", "").strip()

    if not new_name:
        return Response({"error": "New name is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    if len(new_name) > 255:
        return Response({"error": "Directory name is too long"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        directory = Directory.objects.get(id=directory_id, owner=user)
        
        # Check for duplicate name in same parent
        existing = Directory.objects.filter(
            name=new_name,
            parent=directory.parent,
            owner=user
        ).exclude(id=directory.id).exists()
        
        if existing:
            return Response({"error": "A directory with this name already exists in this location"}, status=status.HTTP_400_BAD_REQUEST)

        directory.name = new_name
        directory.save()
        
        return Response(DirectorySerializer(directory).data)
    except Directory.DoesNotExist:
        return Response({"error": "Directory not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rename_file(request, file_id):
    """
    Rename a file.
    Accepts:
        - name: New name for the file
    """
    user = request.user
    new_name = request.data.get("name", "").strip()

    if not new_name:
        return Response({"error": "New name is required"}, status=status.HTTP_400_BAD_REQUEST)
        
    if len(new_name) > 255:
        return Response({"error": "File name is too long"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # We rename the CloudFile wrapper, not the underlying MediaFile
        # Although one might argue we should rename both, for the user view CloudFile is what matters.
        file_obj = CloudFile.objects.get(id=file_id, owner=user, is_deleted=False)
        
        # Check for duplicate name in same directory
        existing = CloudFile.objects.filter(
            name=new_name,
            directory=file_obj.directory,
            owner=user,
            is_deleted=False
        ).exclude(id=file_obj.id).exists()
        
        if existing:
            return Response({"error": "A file with this name already exists in this location"}, status=status.HTTP_400_BAD_REQUEST)

        file_obj.name = new_name
        file_obj.save()
        
        return Response(CloudFileSerializer(file_obj).data)
    except CloudFile.DoesNotExist:
        return Response({"error": "File not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def move_directory(request, directory_id):
    """
    Move a directory to a new parent.
    Accepts:
        - parent: UUID of the new parent directory (or null for root)
    """
    user = request.user
    parent_id = request.data.get("parent")
    
    try:
        directory = Directory.objects.get(id=directory_id, owner=user)
        
        # New parent
        new_parent = None
        if parent_id:
            try:
                new_parent = Directory.objects.get(id=parent_id, owner=user)
                
                # Circular dependency check
                # Check if new_parent is a child of the directory being moved
                temp = new_parent
                while temp:
                    if temp.id == directory.id:
                        return Response({"error": "Cannot move a directory into itself or its children"}, status=status.HTTP_400_BAD_REQUEST)
                    temp = temp.parent
                    
            except Directory.DoesNotExist:
                return Response({"error": "Target parent directory not found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check for name collision in destination
        if Directory.objects.filter(name=directory.name, parent=new_parent, owner=user).exclude(id=directory.id).exists():
             return Response({"error": "A directory with this name already exists in the destination"}, status=status.HTTP_400_BAD_REQUEST)

        directory.parent = new_parent
        directory.save()
        
        return Response(DirectorySerializer(directory).data)
    except Directory.DoesNotExist:
        return Response({"error": "Directory not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def move_file(request, file_id):
    """
    Move a file to a new directory.
    Accepts:
        - parent: UUID of the new parent directory (or null for root)
    """
    user = request.user
    parent_id = request.data.get("parent")
    
    try:
        file_obj = CloudFile.objects.get(id=file_id, owner=user, is_deleted=False)
        
        # New parent
        new_parent = None
        if parent_id:
            try:
                new_parent = Directory.objects.get(id=parent_id, owner=user)
            except Directory.DoesNotExist:
                return Response({"error": "Target directory not found"}, status=status.HTTP_404_NOT_FOUND)
                
        # Check for name collision in destination
        if CloudFile.objects.filter(name=file_obj.name, directory=new_parent, owner=user, is_deleted=False).exclude(id=file_obj.id).exists():
             return Response({"error": "A file with this name already exists in the destination"}, status=status.HTTP_400_BAD_REQUEST)
        
        file_obj.directory = new_parent
        file_obj.save()
        
        return Response(CloudFileSerializer(file_obj).data)
    except CloudFile.DoesNotExist:
        return Response({"error": "File not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
