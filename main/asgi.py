import os

import django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")
django.setup()

from base import routing as base_routing
from dash import routing as dash_routing

# Combine websocket_urlpatterns from both apps
websocket_urlpatterns = (
    base_routing.websocket_urlpatterns  + dash_routing.websocket_urlpatterns
)

# Get the ASGI application
django_asgi_app = get_asgi_application()

# Define the application protocol type router
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
