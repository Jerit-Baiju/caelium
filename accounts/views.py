from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.cache import cache

from .models import User

# Create your views here.


def register_page(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        first_name = request.POST['first_name'].lstrip().rstrip()
        last_name = request.POST['last_name'].lstrip().rstrip()
        email = request.POST['mail']
        gender = request.POST['gender']
        password = request.POST['password']
        confirm = request.POST['confirm']
        if password == confirm:
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists.')
                return render(request, 'accounts/register.html')
            user = User.objects.create_user( # type: ignore
                first_name=first_name, last_name=last_name, email=email, gender=gender, password=password)
            user.save()
            login(request, user)
            try:
                url = request.POST.get('next')
                cache.clear()
                return redirect(url)
            except:
                cache.clear()
                return redirect('index')
        else:
            messages.error(request, 'Passwords does not match.')
            return render(request, 'accounts/register.html')
    return render(request, 'accounts/register.html')


def login_page(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        email = request.POST.get('mail').lower()
        password = request.POST.get('password')
        try:
            user = User.objects.get(email=email)
        except:
            messages.error(
                request, 'It seems you want to Sign UP. User does not exist')
            return render(request, 'accounts/login.html')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            try: 
                url = request.POST.get('next')
                cache.clear()
                return redirect(url)
            except:
                cache.clear()
                return redirect('index')
        else:
            messages.error(request, 'Invalid Password')
            return render(request, 'accounts/login.html')
    return render(request, 'accounts/login.html')


def logout_page(request):
    logout(request)
    cache.clear()
    return redirect('index')
