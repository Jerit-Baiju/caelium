from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("base.urls")),
    path("api/auth/", include("accounts.urls")),
    path("api/chats/", include("chats.urls")),
    path("api/crafts/", include("crafts.urls")),
    path("api/gallery/", include("gallery.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
