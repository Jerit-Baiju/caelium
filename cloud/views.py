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
from cloud.serializers import FileSerializer
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
        use_auto_organization = str(request.data.get("auto_organize", "false")).lower() == "true"

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
            category = check_type(uploaded_file.name)

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


class FileListView(APIView):
    """View for listing files for the authenticated user"""

    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """Get all files owned by the authenticated user"""
        # Get optional query parameters
        parent_id = request.query_params.get("parent", None)

        # Filter by parent directory if specified
        if parent_id:
            try:
                parent = Directory.objects.get(id=parent_id, owner=request.user)
                files = File.objects.filter(owner=request.user, parent=parent)
            except Directory.DoesNotExist:
                return Response({"error": "Parent directory not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Get files in root directory (parent=None)
            files = File.objects.filter(owner=request.user, parent=None)

        serializer = FileSerializer(files, many=True, context={"request": request})
        return Response(serializer.data)
