from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('welcome/', views.welcome, name='welcome'),
    path('invite/',views.invite, name='invite'),
    path('invitation/<str:invite_code>/', views.invitation, name='invitation')
]
