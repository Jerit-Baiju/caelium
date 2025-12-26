from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cloud.views import (
    create_directory,
    download_file,
    explorer_view,
    finalize_chunked_upload,
    initiate_chunked_upload,
    preview_file,
    upload_chunk,
    upload_file,
    rename_directory,
    rename_file,
    move_directory,
    move_file,
)

router = DefaultRouter()


urlpatterns = [
    path("", include(router.urls)),
    path("explorer/", explorer_view, name="cloud-explorer"),
    path("directory/create/", create_directory, name="cloud-create-directory"),
    path("upload/", upload_file, name="cloud-upload"),
    path("upload/initiate/", initiate_chunked_upload, name="cloud-upload-initiate"),
    path("upload/<str:upload_id>/chunk/", upload_chunk, name="cloud-upload-chunk"),
    path("upload/<str:upload_id>/finalize/", finalize_chunked_upload, name="cloud-upload-finalize"),
    path("files/<uuid:file_id>/preview/", preview_file, name="cloud-preview"),
    path("files/<uuid:file_id>/download/", download_file, name="cloud-download"),
    path("directory/<uuid:directory_id>/rename/", rename_directory, name="cloud-directory-rename"),
    path("files/<uuid:file_id>/rename/", rename_file, name="cloud-file-rename"),
    path("directory/<uuid:directory_id>/move/", move_directory, name="cloud-directory-move"),
    path("files/<uuid:file_id>/move/", move_file, name="cloud-file-move"),
]
