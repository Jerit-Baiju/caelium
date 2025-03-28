import base64
import secrets
import os
from io import BytesIO

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import Http404, HttpResponse, StreamingHttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cloud.models import Directory, File
from cloud.serializers import DirectorySerializer, FileSerializer
from cloud.utils import check_type, extract_date_from_filename, get_directory_path
from cloud.google_drive import GoogleDriveStorage


class FileDownloadView(APIView):
    """View for handling file downloads"""

    permission_classes = [IsAuthenticated]
    # Buffer size: 10MB chunks for streaming
    CHUNK_SIZE = 10 * 1024 * 1024

    def decrypt_chunk(self, chunk, key_bytes, iv_bytes, counter):
        """Decrypt a single chunk with AES-256 in CTR mode"""
        # CTR mode uses a counter that increases for each chunk
        # This allows us to decrypt chunks independently at any position
        cipher = Cipher(
            algorithms.AES(key_bytes),
            modes.CTR(iv_bytes + counter.to_bytes(4, byteorder='big')),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        return decryptor.update(chunk) + decryptor.finalize()

    def decrypt_file_stream(self, file_obj):
        """Generator to stream decrypt file data in chunks"""
        # Decode key and IV from base64
        key_bytes = base64.b64decode(file_obj.encryption_key)
        iv_bytes = base64.b64decode(file_obj.encryption_iv)
        
        # For CTR mode, we use a 12-byte nonce + 4-byte counter
        # Starting counter at 0
        counter = 0
        
        # Get file from Google Drive
        drive = GoogleDriveStorage()
        file_content = drive.download_file(file_obj.drive_file_id)
        
        # Process file in chunks
        while True:
            chunk = file_content.read(self.CHUNK_SIZE)
            if not chunk:
                break
            
            # Decrypt the chunk
            decrypted_chunk = self.decrypt_chunk(chunk, key_bytes, iv_bytes, counter)
            yield decrypted_chunk
            
            # Increment counter for next chunk
            counter += 1

    def get(self, request, pk, format=None):
        """Handle GET request for file download with streaming"""
        try:
            # Get the file by UUID
            file_obj = File.objects.get(id=pk, owner=request.user)
        except File.DoesNotExist:
            raise Http404("File not found")

        # Check if file exists in Google Drive
        if not file_obj.drive_file_id:
            raise Http404("File content not found")

        # Create streaming response with decrypted data
        response = StreamingHttpResponse(
            self.decrypt_file_stream(file_obj),
            content_type=file_obj.mime_type or "application/octet-stream"
        )

        # Set content disposition to attachment with the original filename
        response["Content-Disposition"] = f'attachment; filename="{file_obj.name}"'
        
        # Set Content-Length if known
        if file_obj.size:
            response['Content-Length'] = file_obj.size

        return response


class FileUploadView(APIView):
    """View for handling multiple file uploads with encryption"""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]
    # Buffer size: 10MB chunks for processing
    CHUNK_SIZE = 10 * 1024 * 1024

    def encrypt_large_file(self, uploaded_file):
        """Process large file encryption in chunks using AES-256 CTR mode"""
        # Generate a secure random 256-bit (32-byte) key for AES-256
        key = secrets.token_bytes(32)
        # Generate a secure random 96-bit (12-byte) nonce for CTR mode
        # (Counter will be the remaining 4 bytes, starting at 0)
        iv = secrets.token_bytes(12)
        
        # Create a temporary file to store encrypted content
        import tempfile
        temp_encrypted = tempfile.NamedTemporaryFile(delete=False)
        
        # Track file size
        file_size = 0
        counter = 0
        
        try:
            # Process the file in chunks
            for chunk in uploaded_file.chunks(self.CHUNK_SIZE):
                # Update file size
                file_size += len(chunk)
                
                # Create CTR cipher for this chunk
                cipher = Cipher(
                    algorithms.AES(key),
                    modes.CTR(iv + counter.to_bytes(4, byteorder='big')),
                    backend=default_backend()
                )
                encryptor = cipher.encryptor()
                
                # Encrypt the chunk and write to temp file
                encrypted_chunk = encryptor.update(chunk) + encryptor.finalize()
                temp_encrypted.write(encrypted_chunk)
                
                # Increment counter for next chunk
                counter += 1
                
            temp_encrypted.close()
            
            # Return the temp file path and encryption params
            return {
                "temp_file": temp_encrypted.name,
                "size": file_size,
                "key": base64.b64encode(key).decode("utf-8"),
                "iv": base64.b64encode(iv).decode("utf-8"),
            }
        except Exception as e:
            # Clean up temp file in case of errors
            temp_encrypted.close()
            if os.path.exists(temp_encrypted.name):
                os.unlink(temp_encrypted.name)
            raise e

    def create_or_get_directory(self, user, directory_name, parent=None):
        """Create a directory if it doesn't exist or get it if it does"""
        directory, created = Directory.objects.get_or_create(
            name=directory_name,
            owner=user,
            parent=parent,
        )
        return directory

    def create_directory_hierarchy(self, user, path_hierarchy):
        """Create or get a directory hierarchy from a list of directory names"""
        parent = None
        for directory_name in path_hierarchy:
            parent = self.create_or_get_directory(user, directory_name, parent)
        return parent

    def post(self, request, format=None):
        """Handle POST request for multiple file uploads"""
        parent_dir_id = request.data.get("parent_directory") or request.data.get("parent")
        parent_directory = None
        # Parse auto_organize from request, default to True if not specified or from upload page
        use_auto_organization = str(request.data.get("auto_organize", "true")).lower() == "true"

        # Check if a parent directory was specified and it exists
        if parent_dir_id:
            try:
                parent_directory = Directory.objects.get(id=parent_dir_id, owner=request.user)
            except Directory.DoesNotExist:
                return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)

        files = request.FILES.getlist("files")
        if not files:
            return Response({"error": "No files provided"}, status=status.HTTP_400_BAD_REQUEST)

        uploaded_files = []
        drive = GoogleDriveStorage()
        
        for uploaded_file in files:
            try:
                # Use smaller, targeted transactions for critical DB operations
                # This allows other operations to proceed in between file uploads
                
                # Determine file category based on filename
                main_category, sub_category = check_type(uploaded_file.name)
                category = main_category

                # Extract creation date from filename
                file_date = extract_date_from_filename(uploaded_file.name)

                # Determine parent directory based on auto-organization
                file_parent = parent_directory
                if use_auto_organization:
                    # Get directory path hierarchy from filename
                    path_hierarchy = get_directory_path(uploaded_file.name)
                    if path_hierarchy:
                        # Create directory hierarchy and use the leaf directory as parent
                        with transaction.atomic():
                            file_parent = self.create_directory_hierarchy(request.user, path_hierarchy)

                # Handle large file encryption (non-database operation)
                encryption_result = self.encrypt_large_file(uploaded_file)

                # Create initial file record with a short, targeted transaction
                with transaction.atomic():
                    # Create file record in database
                    file_obj = File(
                        name=uploaded_file.name,
                        owner=request.user,
                        parent=file_parent,
                        size=encryption_result["size"],
                        mime_type=uploaded_file.content_type or "application/octet-stream",
                        encryption_key=encryption_result["key"],
                        encryption_iv=encryption_result["iv"],
                        category=category,
                        created_at=file_date,
                    )
                    
                    # Save the file object to get an ID
                    file_obj.save()
                
                # Upload to Google Drive (non-database operation)
                drive_file = drive.upload_file(
                    file_path=encryption_result["temp_file"],
                    file_name=uploaded_file.name,
                    mime_type="application/octet-stream",
                    file_id=str(file_obj.id)
                )
                
                # Update file with Drive ID in a separate transaction
                with transaction.atomic():
                    # Get the most recent version of the file object
                    file_obj = File.objects.get(id=file_obj.id)
                    file_obj.drive_file_id = drive_file['id']
                    file_obj.save()
                
                # Delete the temporary file
                if os.path.exists(encryption_result["temp_file"]):
                    os.unlink(encryption_result["temp_file"])
                
                # Add the request context when creating the serializer
                uploaded_files.append(FileSerializer(file_obj, context={"request": request}).data)
                
            except Exception as e:
                # Log the error
                print(f"Error uploading file {uploaded_file.name}: {str(e)}")
                # Continue with the next file instead of failing the entire request
                continue

        return Response({"files": uploaded_files}, status=status.HTTP_201_CREATED)


class DirectoryListView(APIView):
    """View for listing and creating directories"""

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """Get directories owned by the authenticated user"""
        # Get optional query parameters
        parent_id = request.query_params.get("parent", None)

        # Filter by parent directory if specified
        if parent_id:
            try:
                parent = Directory.objects.get(id=parent_id, owner=request.user)
                directories = Directory.objects.filter(owner=request.user, parent=parent)
            except Directory.DoesNotExist:
                return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Get directories in root directory (parent=None)
            directories = Directory.objects.filter(owner=request.user, parent=None)

        serializer = DirectorySerializer(directories, many=True)
        return Response(serializer.data)

    def post(self, request, format=None):
        """Create a new directory"""
        serializer = DirectorySerializer(data=request.data)
        if serializer.is_valid():
            # Ensure that the owner is the authenticated user
            serializer.validated_data["owner"] = request.user

            # If parent is specified, ensure it exists and belongs to the user
            parent_id = serializer.validated_data.get("parent", None)
            if parent_id:
                try:
                    parent = Directory.objects.get(id=parent_id, owner=request.user)
                    serializer.validated_data["parent"] = parent
                except Directory.DoesNotExist:
                    return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)

            # Save the directory
            directory = serializer.save()
            return Response(DirectorySerializer(directory).data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DirectoryDetailView(APIView):
    """View for retrieving, updating, and deleting directories"""

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return Directory.objects.get(pk=pk, owner=self.request.user)
        except Directory.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        """Get details of a specific directory"""
        directory = self.get_object(pk)
        serializer = DirectorySerializer(directory)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        """Update a directory"""
        directory = self.get_object(pk)
        serializer = DirectorySerializer(directory, data=request.data, partial=True)

        if serializer.is_valid():
            # If parent is being updated, ensure it exists and belongs to the user
            parent_id = serializer.validated_data.get("parent", None)
            if parent_id and parent_id != directory.parent:
                try:
                    parent = Directory.objects.get(id=parent_id, owner=request.user)

                    # Check for circular reference
                    if pk == parent_id:
                        return Response(
                            {"error": "A directory cannot be its own parent"}, status=status.HTTP_400_BAD_REQUEST
                        )

                    # TODO: Add more checks to prevent circular references in the directory tree
                    serializer.validated_data["parent"] = parent
                except Directory.DoesNotExist:
                    return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)

            directory = serializer.save()
            return Response(DirectorySerializer(directory).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """Delete a directory and all its contents"""
        directory = self.get_object(pk)

        # Recursively delete all contents
        directory.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GalleryListView(APIView):
    """View for listing media files (images and videos) for the authenticated user"""

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """Get all media files (with category Pictures or Videos) owned by the authenticated user"""
        # Get optional query parameters
        parent_id = request.query_params.get("parent", None)

        # Define media categories to include in gallery
        media_categories = ["Pictures", "Videos"]

        from django.db.models import Q

        # Build query to match any media category - case insensitive
        category_query = Q(category__iexact=media_categories[0])
        for category in media_categories[1:]:
            category_query |= Q(category__iexact=category)

        # Start building the queryset - filter by owner and categories
        queryset = File.objects.filter(category_query, owner=request.user)

        # If no results found, try a more flexible query that checks if category contains these words
        if queryset.count() == 0:
            category_query = (
                Q(category__icontains="picture") | Q(category__icontains="video") | Q(category__icontains="image")
            )
            queryset = File.objects.filter(category_query, owner=request.user)

        # Filter by parent directory if specified
        if parent_id:
            try:
                parent = Directory.objects.get(id=parent_id, owner=request.user)
                queryset = queryset.filter(parent=parent)
            except Directory.DoesNotExist:
                return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)
        # Remove the else clause that was filtering to only root files
        # This way we return ALL media files when no parent is specified

        # If still no results found, return a more descriptive response
        if queryset.count() == 0:
            # Check if there are any files for this user at all
            total_files = File.objects.filter(owner=request.user).count()
            if total_files > 0:
                # Get a list of unique categories for debugging
                categories = File.objects.filter(owner=request.user).values_list("category", flat=True).distinct()
                return Response(
                    {
                        "message": "No media files found with the categories Pictures or Videos.",
                        "debug_info": {"total_files": total_files, "available_categories": list(categories)},
                    }
                )

        serializer = FileSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)


class DirectoryPathView(APIView):
    """View for getting directory information by path"""

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """Get directory information by path"""
        path = request.query_params.get("path", None)
        if not path:
            return Response({"error": "Path parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Split the path into components
        path_parts = path.strip("/").split("/")

        # Start from root level
        parent = None
        result = []
        current_path = ""

        # For each path part, try to find the corresponding directory
        for part in path_parts:
            current_path += (current_path and "/") + part
            try:
                # Find directory matching name and parent
                directory = Directory.objects.get(owner=request.user, name=part, parent=parent)

                # Add to result list
                result.append({"id": directory.id, "name": directory.name, "path": current_path})

                # Update parent for next iteration
                parent = directory

            except Directory.DoesNotExist:
                # If directory doesn't exist, return what we have so far
                break

        return Response(result)


class FileListView(APIView):
    """View for listing files"""

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """Get files owned by the authenticated user"""
        # Get optional query parameters
        parent_id = request.query_params.get("parent", None)

        # Build the base queryset - filter by owner
        queryset = File.objects.filter(owner=request.user)

        # Filter by parent directory if specified
        if parent_id:
            try:
                parent = Directory.objects.get(id=parent_id, owner=request.user)
                queryset = queryset.filter(parent=parent)
            except Directory.DoesNotExist:
                return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Get files in root directory (parent=None)
            queryset = queryset.filter(parent=None)

        # Optional: Sort files by name or created_at
        queryset = queryset.order_by("name")

        serializer = FileSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)
