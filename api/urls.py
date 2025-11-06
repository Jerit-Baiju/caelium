from django.urls import path

from api import views

urlpatterns = [
    path("verify_jwt/", views.verify_jwt_user, name="verify_jwt_user"),
    path("redeploy/", views.redeploy_view, name="redeploy"),
    path("release_update_failure/", views.update_release_failure_view, name="update_release_failure_view"),
    path("update_server_status/", views.update_server_status, name="update_server_status"),
    path("public_server_error_handler/", views.public_server_error_handler, name="public_server_error_handler"),
    path("ping/", views.ping_view, name="ping_view"),
    path("servers/", views.list_servers, name="list_servers"),
]
