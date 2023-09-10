from base.models import Relationship


def get_profile(request):
    return Relationship.objects.get(partners=request.user)
