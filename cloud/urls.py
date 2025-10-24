from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cloud.views import explorer_view

router = DefaultRouter()


urlpatterns = [
    path("", include(router.urls)),
    path("explorer/", explorer_view, name="cloud-explorer"),
]
