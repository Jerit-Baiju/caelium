from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cloud.views import (ExplorerView, FileDownloadView, FileUploadView, GalleryListView)

router = DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path("files/<uuid:pk>/download/", FileDownloadView.as_view(), name="file-download"),
    path("gallery/", GalleryListView.as_view(), name="gallery-list"),
    path("explorer/", ExplorerView.as_view(), name="explorer"),
]
