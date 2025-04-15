import os
import uuid

from django.db import models

from accounts.models import User


class Directory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="directories")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="subdirectories")
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    @property
    def path(self):
        if self.parent:
            return f"{self.parent.path}/{self.name}"
        return self.name

    def __str__(self):
        return f"{self.name}"


class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="files")
    parent = models.ForeignKey(Directory, on_delete=models.CASCADE, null=True, blank=True, related_name="files")
    size = models.BigIntegerField(default=0)
    mime_type = models.CharField(max_length=255, blank=True, null=True)
    encryption_key = models.TextField(blank=True, null=True)
    encryption_iv = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    category = models.CharField(max_length=50, blank=True, null=True)
    # Google Drive specific fields
    drive_file_id = models.CharField(max_length=255, blank=True, null=True)
    upload_status = models.CharField(
        max_length=20, 
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='completed'
    )
    # Store local file path for files still being uploaded
    local_path = models.CharField(max_length=500, blank=True, null=True)

    @property
    def path(self):
        if self.parent:
            return f"{self.parent.path}/{self.name}"
        return self.name

    def __str__(self):
        return f"{self.name}"

    def delete(self, *args, **kwargs):
        # If file is stored in Google Drive, delete it from there
        if self.drive_file_id:
            from cloud.google_drive import GoogleDriveStorage
            try:
                drive = GoogleDriveStorage()
                drive.delete_file(self.drive_file_id)
            except Exception as e:
                print(f"Error deleting file from Google Drive: {e}")
        super().delete(*args, **kwargs)


class SharedItem(models.Model):
    PERMISSION_CHOICES = (
        ("view", "View"),
        ("edit", "Edit"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shared_items")
    content = models.ForeignKey(File, on_delete=models.CASCADE, null=True, blank=True, related_name="shared_with")
    directory = models.ForeignKey(Directory, on_delete=models.CASCADE, null=True, blank=True, related_name="shared_with")
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES, default="view")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        shared_item = self.content.name if self.content else self.directory.name
        return f"{shared_item} shared with {self.user.email}"


class Tag(models.Model):
    """Model to represent tags for files"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}"


class FileTag(models.Model):
    """Model to connect files with tags and users who applied them"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="file_tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="file_tags")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="applied_tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("file", "tag", "user")

    def __str__(self):
        return f"{self.file.name} - {self.tag.name} (by {self.user.username})"
