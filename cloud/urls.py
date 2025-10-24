from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cloud.views import download_file, explorer_view, preview_file, upload_file

router = DefaultRouter()


urlpatterns = [
    path("", include(router.urls)),
    path("explorer/", explorer_view, name="cloud-explorer"),
    path("upload/", upload_file, name="cloud-upload"),
    path("files/<uuid:file_id>/preview/", preview_file, name="cloud-preview"),
    path("files/<uuid:file_id>/download/", download_file, name="cloud-download"),
]
