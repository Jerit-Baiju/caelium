from django.urls import path

from . import views

urlpatterns = [
    path('create/', views.MessageCreateView.as_view()),
    path('', views.ChatViewSet.as_view({'get': 'list'}))
]
