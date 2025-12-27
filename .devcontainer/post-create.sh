#!/bin/bash

# Upgrade pip
pip install --upgrade pip

# Install requirements
pip3 install --user -r requirements.txt

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput
