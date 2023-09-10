import secrets
import string
from django.contrib import messages
import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from accounts.models import User
from base.basic import get_profile

from base.models import Relationship

# Create your views here.


def index(request):
    if not request.user.is_authenticated:
        return redirect('welcome')
    if request.user.partner():
        api_key = '30cabdb500a38872a30c50a0f07c5ad8'
        cities = ['Kumily', 'Thookkupalam']
        weather = []
        for city in cities:
            url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                weather.append({'city': data['name'], 'temp': int(
                    data['main']['temp'])-273, 'desc': data['weather'][0]['description']})
            else:
                pass
        context = {
            'weather': weather,
            'partner': request.user.partner()
        }
        return render(request, 'base/index.html', context)
    return redirect('invite')


def welcome(request):
    return render(request, 'base/welcome.html')


def invite(request):
    if not request.user.is_authenticated:
        return redirect('welcome')
    if not request.user.partner():
        if request.user.invite_code:
            invitation_code = request.user.invite_code
        else:
            characters = string.ascii_letters + string.digits
            invitation_code = ''.join(secrets.choice(characters) for _ in range(16))
            user = User.objects.get(id=request.user.id)
            user.invite_code = invitation_code
            user.save()
        context = {
            'code': invitation_code
        }
        return render(request, 'base/invite.html', context)
    return redirect('index')


@login_required(login_url='login')
def invitation(request, invite_code):
    user = request.user
    if not user.partner():
        requested = User.objects.filter(invite_code=invite_code).first()
        if request.method == 'POST' and requested:
            action = request.POST.get('action')
            if action == 'accept' and user != requested and user.gender != requested.gender and not user.partner() and not requested.partner():
                if request.user.gender == 'Male':
                    Relationship.objects.create(male=request.user, female=requested)
                else:
                    Relationship.objects.create(male=requested, female=request.user)
                return redirect('index')
        context = {'requested': requested}
        return render(request, 'base/invitation.html', context)
    messages.error(request, f'You are already committed to {request.user.partner()}')
    return redirect('index')


def test(request):
    return HttpResponse(str(get_profile(request)))


class ServiceWorkerView(TemplateView):
    content_type = 'application/javascript'
    template_name = 'js/service-worker.js'
