import base64
import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import Http404, HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from cloud.models import Directory, File
from cloud.serializers import DirectorySerializer, FileSerializer
from cloud.utils import check_type, extract_date_from_filename, get_directory_path


class FileDownloadView(APIView):
    """View for handling file downloads"""

    permission_classes = [IsAuthenticated]

    def decrypt_file(self, encrypted_data, key, iv):
        """Decrypt file data with AES-256 in CBC mode"""
        # Decode key and IV from base64
        key_bytes = base64.b64decode(key)
        iv_bytes = base64.b64decode(iv)

        # Create AES cipher
        cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes), backend=default_backend())
        decryptor = cipher.decryptor()

        # Decrypt data
        decrypted_padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # Remove padding
        padding_length = decrypted_padded_data[-1]
        decrypted_data = decrypted_padded_data[:-padding_length]

        return decrypted_data

    def get(self, request, pk, format=None):
        """Handle GET request for file download"""
        try:
            # Get the file by UUID
            file_obj = File.objects.get(id=pk, owner=request.user)
        except File.DoesNotExist:
            raise Http404("File not found")

        # Return the file with decryption
        if file_obj.content:
            # Read the encrypted data
            encrypted_data = file_obj.content.read()

            # Decrypt the file data
            decrypted_data = self.decrypt_file(encrypted_data, file_obj.encryption_key, file_obj.encryption_iv)

            # Create response with decrypted data
            response = HttpResponse(decrypted_data, content_type=file_obj.mime_type or "application/octet-stream")

            # Set content disposition to attachment with the original filename
            response["Content-Disposition"] = f'attachment; filename="{file_obj.name}"'

            return response

        raise Http404("File content not found")


class FileUploadView(APIView):
    """View for handling multiple file uploads with encryption"""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def encrypt_file(self, file_data):
        """Encrypt file data with AES-256 in CBC mode"""
        # Generate a secure random 256-bit (32-byte) key for AES-256
        key = secrets.token_bytes(32)
        # Generate a secure random 128-bit (16-byte) initialization vector for CBC mode
        iv = secrets.token_bytes(16)

        # Create AES cipher
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()

        # Pad data to block size (16 bytes for AES)
        block_size = 16
        padding_length = block_size - (len(file_data) % block_size)
        if padding_length == 0:
            padding_length = block_size
        padding = bytes([padding_length]) * padding_length
        padded_data = file_data + padding

        # Encrypt data
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        # Return the encrypted data and encryption parameters
        return {
            "data": encrypted_data,
            "key": base64.b64encode(key).decode("utf-8"),
            "iv": base64.b64encode(iv).decode("utf-8"),
        }

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

    @transaction.atomic
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
        for uploaded_file in files:
            # Read file data
            file_data = uploaded_file.read()

            # Get file size and mime type
            file_size = len(file_data)
            mime_type = uploaded_file.content_type or "application/octet-stream"

            # Determine file category based on filename
            main_category, sub_category = check_type(uploaded_file.name)
            # Use the main category as the file category for database storage
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
                    file_parent = self.create_directory_hierarchy(request.user, path_hierarchy)

            # Encrypt the file
            encryption_result = self.encrypt_file(file_data)

            # Create file record in database
            file_obj = File(
                name=uploaded_file.name,
                owner=request.user,
                parent=file_parent,
                size=file_size,
                mime_type=mime_type,
                encryption_key=encryption_result["key"],
                encryption_iv=encryption_result["iv"],
                category=category,
                created_at=file_date,  # Set the creation date based on filename
            )

            # Save the file with encrypted content
            file_obj.content.save(uploaded_file.name, ContentFile(encryption_result["data"]), save=False)

            file_obj.save()
            # Add the request context when creating the serializer
            uploaded_files.append(FileSerializer(file_obj, context={"request": request}).data)

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

        # Debug: Print the SQL query and count
        print(f"SQL Query: {queryset.query}")
        print(f"Count: {queryset.count()}")

        # If no results found, try a more flexible query that checks if category contains these words
        if queryset.count() == 0:
            category_query = (
                Q(category__icontains="picture") | Q(category__icontains="video") | Q(category__icontains="image")
            )
            queryset = File.objects.filter(category_query, owner=request.user)
            print(f"Fallback SQL Query: {queryset.query}")
            print(f"Fallback Count: {queryset.count()}")

        # Filter by parent directory if specified
        if parent_id:
            try:
                parent = Directory.objects.get(id=parent_id, owner=request.user)
                queryset = queryset.filter(parent=parent)
            except Directory.DoesNotExist:
                return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)
        # Remove the else clause that was filtering to only root files
        # This way we return ALL media files when no parent is specified

        # Add debug print to check final queryset
        print(f"Final Count: {queryset.count()}")

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
        path = request.query_params.get('path', None)
        if not path:
            return Response({"error": "Path parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Split the path into components
        path_parts = path.strip('/').split('/')
        
        # Start from root level
        parent = None
        result = []
        current_path = ''
        
        # For each path part, try to find the corresponding directory
        for part in path_parts:
            current_path += (current_path and '/') + part
            try:
                # Find directory matching name and parent
                directory = Directory.objects.get(
                    owner=request.user, 
                    name=part,
                    parent=parent
                )
                
                # Add to result list
                result.append({
                    'id': directory.id,
                    'name': directory.name,
                    'path': current_path
                })
                
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
        queryset = queryset.order_by('name')
        
        serializer = FileSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)
