from django.urls import path

from dash.views import CloudFileDetailView, CloudFileListView, LoginView, Stats, UserDetailView, UserListView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("stats/", Stats.as_view(), name="stats"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("cloud/files/", CloudFileListView.as_view(), name="cloud-files-list"),
    path(
        "cloud/files/<uuid:pk>/",
        CloudFileDetailView.as_view(),
        name="cloud-file-detail",
    ),
]
