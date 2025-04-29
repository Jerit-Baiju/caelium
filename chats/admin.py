from django.contrib import admin

from chats.models import Chat,Message, PinnedChat

# Register your models here.
admin.site.register(Chat)
admin.site.register(PinnedChat)

class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "chat", "sender", "type", "short_content", "timestamp")
    list_filter = ("type", "chat", "sender", "timestamp")
    search_fields = ("content", "sender__name", "chat__name")
    ordering = ("-timestamp",)
    readonly_fields = ("timestamp",)

    def short_content(self, obj):
        return (obj.content[:50] + "...") if obj.content and len(obj.content) > 50 else obj.content
    short_content.short_description = "Content"

admin.site.register(Message, MessageAdmin)
