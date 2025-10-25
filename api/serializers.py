from api.models import Server
from rest_framework.serializers import ModelSerializer


class ServerSerializer(ModelSerializer):
    """
    Serializer for server objects.
    """

    class Meta:
        model = Server
        fields = "__all__"
