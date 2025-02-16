from django.contrib import admin

from .models import FCMToken, GoogleToken, TestUserEmail, User

admin.site.register(User)
admin.site.register(GoogleToken)
admin.site.register(FCMToken)
admin.site.register(TestUserEmail)
