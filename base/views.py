import secrets
import string

from django.contrib.auth.decorators import login_required
import requests
from django.shortcuts import redirect, render

from accounts.models import User

# Create your views here.


def index(request):
    # if request.user.is_superuser:
    #     api_key = '30cabdb500a38872a30c50a0f07c5ad8'
    #     cities = ['Kumily', 'Thookkupalam']
    #     weather = []
    #     for city in cities:
    #         url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'
    #         response = requests.get(url, timeout=10)
    #         if response.status_code == 200:
    #             data = response.json()
    #             weather.append({'city': data['name'], 'temp': int(
    #                 data['main']['temp'])-273, 'desc': data['weather'][0]['description']})
    #         else:
    #             pass
    #     context = {
    #         'weather': weather
    #     }
    #     return render(request, 'base/index.html', context)
    if not request.user.is_authenticated:
        return redirect('welcome')
    else:
        return redirect('invite')


def welcome(request):
    return render(request, 'base/welcome.html')


def invite(request):
    if not request.user.is_authenticated:
        return redirect('welcome')
    if request.user.invite_code:
        invitation_code = request.user.invite_code
    else:
        characters = string.ascii_letters + string.digits
        invitation_code = ''.join(secrets.choice(characters)
                                  for _ in range(16))
        user = User.objects.get(id=request.user.id)
        user.invite_code = invitation_code
        user.save()
    context = {
        'code': invitation_code
    }
    return render(request, 'base/invite.html', context)

@login_required(login_url='login')
def invitation(request, invite_code):
    try:
        requested = User.objects.get(invite_code=invite_code)
    except:
        requested = None
    context = {
        'requested': requested
    }
    return render(request, 'base/invitation.html', context)
