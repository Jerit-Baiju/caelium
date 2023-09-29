# from django.shortcuts import render
# import os
from django.core.cache import cache
import requests

api_key = '30cabdb500a38872a30c50a0f07c5ad8'


# Create your views here.
def weather_api(city):
    try:
        url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'
        response = requests.get(url, timeout=0)
        data = response.json()
        cache_data = {'city': data['name'], 'temp': int(
            data['main']['temp'])-273, 'desc': data['weather'][0]['description']}
        cache.set('city', cache_data, timeout=24*60*60)
        return data
    except:
        data = cache.get(city)
        if data is None:
            data = {'city': city, 'temp': 0, 'desc': 'Unknown'}
        return data
