import requests
from django.shortcuts import redirect, render

# Create your views here.


def index(request):
    if request.user.is_superuser:
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
            'weather': weather
        }
        return render(request, 'base/index.html', context)
    if not request.user.is_authenticated:
        return redirect('welcome')


def welcome(request):
    return render(request, 'base/welcome.html')
