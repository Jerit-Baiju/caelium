import random
import secrets
import string

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.generic import TemplateView
from PIL import Image, UnidentifiedImageError

from accounts.models import User
from api.views import weather_api
from base.models import Relationship

# Create your views here.

def gen_code(length):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


def index(request):
    if not request.user.is_authenticated:
        return redirect('welcome')
    if request.user.partner():
        weather = weather_api(request.user.partner().location)
        context = {
            'weather': weather,
            'partner': request.user.partner(),
            'quote': random.choice(['Connect with your partner and plan your future together.','"Every day with you is a new chapter in our story."'])
        }
        return render(request, 'base/index.html', context)
    return redirect('invite')


def welcome(request):
    if not request.user.is_authenticated:
        return render(request, 'base/welcome.html')
    return redirect('index')


def invite(request):
    if not request.user.is_authenticated:
        return redirect('welcome')
    if not request.user.partner():
        if request.user.invite_code:
            invitation_code = request.user.invite_code
        else:
            user = User.objects.get(id=request.user.id)
            invitation_code = gen_code(16)
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
                room = gen_code(16)
                if request.user.gender == 'Male':
                    Relationship.objects.create(male=request.user, female=requested, room=room)
                else:
                    Relationship.objects.create(male=requested, female=request.user, room=room)
                return redirect('index')
        context = {'requested': requested}
        return render(request, 'base/invitation.html', context)
    messages.error(request, f'You are already committed to {request.user.partner()}')
    return redirect('index')


@login_required(login_url='login')
def profile(request):
    if request.method == 'POST':
        first_name = request.POST['first_name'].strip()
        last_name = request.POST['last_name'].strip()
        email = request.POST['email']
        gender = request.POST['gender']
        location = request.POST['location']
        user = User.objects.get(email=request.user.email)
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.gender = gender
        user.location = location
        try:
            avatar = request.FILES['avatar']
            img = Image.open(avatar)
            if str(img.format).lower() not in ['jpeg', 'png', 'jpg', 'webp']:
                messages.error(request, 'Invalid image format. Please upload a JPEG, PNG, or GIF.')
                return redirect('profile')
            max_file_size = getattr(settings, "MAX_FILE_SIZE_BYTES")
            if avatar.size > max_file_size:
                messages.error(request, 'File size exceeds the allowed limit.')
                return redirect('profile')
            user.avatar = avatar
        except KeyError:
            pass
        except UnidentifiedImageError:
            messages.error(request, 'Cannot identify image file')
            return render(request, 'base/profile.html')
        user.save()
        return redirect('profile')
    return render(request, 'base/profile.html')

class ServiceWorkerView(TemplateView):
    content_type = 'application/javascript'
    template_name = 'external/service-worker.js'

class ManifestView(TemplateView):
    content_type = 'text/plain'
    template_name = 'external/manifest.json'
