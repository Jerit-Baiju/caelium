from django.urls import path

from api import views


urlpatterns = [
    path("verify_jwt/", views.verify_jwt_user, name="verify_jwt_user"),
    path("ping/", views.ping_view, name="ping_view"),
    path("hps/", views.get_hps, name="hps_view"),
]
