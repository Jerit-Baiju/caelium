from django.contrib import admin

from cloud.models import Directory, File, SharedItem


@admin.register(Directory)
class DirectoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "get_path", "created_at", "modified_at")
    list_filter = ("owner", "created_at", "modified_at")
    search_fields = ("name", "owner__username")
    date_hierarchy = "created_at"

    def get_path(self, obj):
        return obj.path

    get_path.short_description = "Path"


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "get_path", "size", "mime_type", "created_at", "modified_at")
    list_filter = ("owner", "mime_type", "created_at", "modified_at")
    search_fields = ("name", "owner__username", "mime_type")
    date_hierarchy = "created_at"
    readonly_fields = ("size",)

    def get_path(self, obj):
        return obj.path

    get_path.short_description = "Path"


@admin.register(SharedItem)
class SharedItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "get_shared_item", "permission", "created_at")
    list_filter = ("permission", "created_at", "user")
    search_fields = ("user__username", "file__name", "directory__name")
    date_hierarchy = "created_at"

    def get_shared_item(self, obj):
        if obj.file:
            return f"File: {obj.file.name}"
        return f"Directory: {obj.directory.name}"

    get_shared_item.short_description = "Shared Item"
