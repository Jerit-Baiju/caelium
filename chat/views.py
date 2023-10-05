from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from base.models import Relationship
from chat.models import Message

# Create your views here.
@login_required(login_url='login')
def chat(request):
    room = Relationship.objects.get(Q(male=request.user) | Q(female=request.user))
    context = {
        'conversation': Message.objects.filter(room=room),
    }
    return render(request, 'chat/main.html',  context)
