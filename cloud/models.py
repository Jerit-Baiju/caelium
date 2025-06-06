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
        choices=[("pending", "Pending"), ("completed", "Completed"), ("failed", "Failed")],
        default="completed",
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
        shared_item = self.content.name if self.content else self.directory
        return f"{shared_item} shared with {self.user.email}"


class Tag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tags")
    related_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="related_tags")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Enforce unique constraint for tag name per owner
        # Also enforce unique constraint for related_user per owner
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="unique_tag_name_per_owner"),
            models.UniqueConstraint(
                fields=["owner", "related_user"],
                name="unique_related_user_per_owner",
                condition=models.Q(related_user__isnull=False),
            ),
        ]

    def __str__(self):
        if self.related_user:
            return f"{self.name} ({self.related_user.email})"
        return self.name


class FileTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name="tags")
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE, related_name="files")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensure a file can't be tagged with the same tag multiple times
        constraints = [models.UniqueConstraint(fields=["file", "tag"], name="unique_file_tag")]

    def __str__(self):
        return f"{self.file.name} - {self.tag.name}"
