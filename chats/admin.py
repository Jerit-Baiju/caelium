from django.contrib import admin

from .models import Chat,Message, PinnedChat

# Register your models here.
admin.site.register(Chat)
admin.site.register(Message)
admin.site.register(PinnedChat)
