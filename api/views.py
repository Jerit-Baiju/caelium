# from django.shortcuts import render
# import os
import requests
from django.core.cache import cache

api_key = '30cabdb500a38872a30c50a0f07c5ad8'
def weather_api(city):
    cached_weather = cache.get(city)
    if cached_weather is not None:
        return cached_weather
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}'
    try:
        response = requests.get(url, timeout=2)
        response.raise_for_status()
        data = response.json()
        weather = {'city': data['name'], 'temp': int(data['main']['temp']) - 273, 'desc': data['weather'][0]['description']}
        cache.set(city, weather, 3600)
        return weather
    except requests.exceptions.RequestException:
        return {'city': city, 'temp': 0, 'desc':'unknown place'}
