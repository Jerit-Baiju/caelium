import os

from django.core.exceptions import ObjectDoesNotExist

from api.models import Server


def get_current_server():
    base_url = os.getenv("BASE_URL")
    if not base_url:
        raise RuntimeError("BASE_URL is not defined in the environment.")

    try:
        server = Server.objects.get(base_url=base_url)
        return server
    except ObjectDoesNotExist:
        # Get the highest existing server ID and increment
        last_server = Server.objects.order_by("-id").first()
        new_id = last_server.id + 1 if last_server else 1

        # Create a new server with name server_{id}
        server = Server.objects.create(name=f"server_{new_id}", base_url=base_url)
        return server
