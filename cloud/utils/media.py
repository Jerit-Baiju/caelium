import hashlib
import mimetypes
import shutil
from pathlib import Path
from typing import Union

import requests
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from rest_framework import status
from rest_framework.response import Response

from accounts.models import User
from api.utils import get_current_server
from cloud.models import MediaFile
from cloud.utils.encryption import encrypt_file_stream, generate_encryption_key, generate_nonce

MAX_FILE_SIZE = 5 * 1024 * 1024 * 1024


def create_media_file(
    file: Union[UploadedFile, str],
    folder: str,
    owner: User,
    shared_with=None,
    privacy="private",
    should_encrypt=False,
    filename: str = None,
):
    """
    Create a MediaFile from an uploaded file, a filename, or a URL.

    Args:
        file: Either an UploadedFile object, a filename (str) from MEDIA_ROOT/defaults/, or a URL starting with http/https
        folder: The folder to store the file in (e.g., "avatars", "cloud")
        should_encrypt: Whether to encrypt the file (only applies to UploadedFile, not str)
        filename: Optional custom filename to use (mainly for URLs)

    Returns:
        MediaFile instance or Response/None on error
    """

    # Determine the type of file input
    is_string = isinstance(file, str)
    is_url = is_string and file.startswith(("http://", "https://"))
    is_filename = is_string and not is_url

    downloaded_content = None  # For URL downloads

    # Get file info based on type
    if is_url:
        # Handle URL case - download from HTTP/HTTPS
        try:
            response = requests.get(file, timeout=10)
            if response.status_code != 200:
                print(f"Failed to download file from {file}: Status {response.status_code}")
                return None

            downloaded_content = response.content
            file_size = len(downloaded_content)

            # Use provided filename or extract from URL
            if not filename:
                filename = file.split("/")[-1].split("?")[0] or "downloaded_file"

            # Get mime type from response headers or guess from filename
            mime_type = response.headers.get("content-type")
            if not mime_type:
                mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

            should_encrypt = False  # Never encrypt downloaded files

        except requests.exceptions.RequestException as e:
            print(f"Error downloading file from {file}: {e}")
            return None

    elif is_filename:
        # Handle filename string case - load from MEDIA_ROOT/defaults/{filename}
        source_path = Path(settings.MEDIA_ROOT) / "defaults" / file

        if not source_path.exists():
           print(f"File not found in defaults: {source_path}") 

        file_size = source_path.stat().st_size
        filename = source_path.name
        mime_type = mimetypes.guess_type(source_path)[0] or "application/octet-stream"
        should_encrypt = False  # Never encrypt files from defaults

    else:
        # Handle UploadedFile case
        file_size = file.size
        filename = file.name
        mime_type = file.content_type or "application/octet-stream"

    # Check file size (5GB limit)
    if file_size > MAX_FILE_SIZE:
        error_msg = f"File size exceeds maximum limit of 5GB. File size: {file_size / (1024**3):.2f}GB"
        print(error_msg)
        if is_url or is_filename:
            return None
        raise ValueError(error_msg)
    try:
        # Calculate hash
        sha256 = hashlib.sha256()

        if is_url:
            # Hash from downloaded content
            sha256.update(downloaded_content)
        elif is_filename:
            # Hash from file path
            with open(source_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
        else:
            # Hash from uploaded file
            for chunk in file.chunks():
                sha256.update(chunk)
            file.seek(0)  # Reset file pointer

        # Create MediaFile instance
        media_file = MediaFile(
            filename=filename,
            media_hash=sha256.hexdigest(),
            size=file_size,
            mime_type=mime_type,
            is_encrypted=should_encrypt,
            residing_server=get_current_server(),
            owner=owner,
            privacy=privacy,
            folder=folder,
        )
        media_file.save()

        # Set shared_with after saving (many-to-many relationship)
        if shared_with:
            media_file.shared_with.set(shared_with)
        else:
            media_file.shared_with.set([])

        # Create directory for this file: media/{folder}/{uuid}/
        file_dir = Path(settings.MEDIA_ROOT) / folder / str(media_file.id)
        file_dir.mkdir(parents=True, exist_ok=True)

        # Determine output filename and path
        output_filename = "encrypted" if should_encrypt else filename
        output_path = file_dir / output_filename

        # Save the file
        if is_url:
            # Write downloaded content to file
            with open(output_path, "wb") as f:
                f.write(downloaded_content)
        elif is_filename:
            # Copy file from defaults folder
            shutil.copy2(source_path, output_path)
        elif should_encrypt:
            # Encrypt and save uploaded file
            encryption_key = generate_encryption_key()
            nonce = generate_nonce()

            with open(output_path, "wb") as output_file:
                encrypted_size = encrypt_file_stream(file, output_file, encryption_key, nonce)

            # Store encryption parameters
            media_file.encryption_key = encryption_key
            media_file.encryption_nonce = nonce
            media_file.encrypted_size = encrypted_size
            media_file.save()
        else:
            # Save uploaded file without encryption
            with open(output_path, "wb") as output_file:
                for chunk in file.chunks():
                    output_file.write(chunk)

        return media_file

    except Exception as e:
        # Clean up media file if created
        if "media_file" in locals():
            file_dir = Path(settings.MEDIA_ROOT) / folder / str(media_file.id)
            if file_dir.exists():
                shutil.rmtree(file_dir)
            media_file.delete()

        # Return None for URLs/filenames, raise exception for uploaded files
        error_msg = f"Failed to process file: {str(e)}"
        print(error_msg)
        if is_url or is_filename:
            return None
        
        raise Exception(error_msg)
