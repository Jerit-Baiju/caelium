from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cloud.views import DirectoryDetailView, DirectoryListView, FileDownloadView, FileListView, FileUploadView

router = DefaultRouter()

urlpatterns = [
    path("", include(router.urls)),
    path("upload/", FileUploadView.as_view(), name="file-upload"),
    path("files/<uuid:pk>/download/", FileDownloadView.as_view(), name="file-download"),
    path("files/", FileListView.as_view(), name="file-list"),
    path("directories/", DirectoryListView.as_view(), name="directory-list"),
    path("directories/<uuid:pk>/", DirectoryDetailView.as_view(), name="directory-detail"),
]
