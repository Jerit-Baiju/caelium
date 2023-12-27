from django.contrib import admin

from .models import Chat, ImageMessage, Message, TextMessage, VideoMessage, VoiceMessage

# Register your models here.
admin.site.register(Chat)
admin.site.register(Message)
admin.site.register(TextMessage)
admin.site.register(ImageMessage)
admin.site.register(VoiceMessage)
admin.site.register(VideoMessage)
