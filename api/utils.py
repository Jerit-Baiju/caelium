import os
from api.models import Server


def get_self_server():
    host = os.environ["BASE_URL"]
    try:
        server = Server.objects.get(hostname=host)
        return server
    except Server.DoesNotExist:
        return None
