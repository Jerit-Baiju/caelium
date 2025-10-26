#!/bin/bash
set -e  # Exit on any error

# Add safe directory exception for git (using --system to avoid $HOME dependency)
git config --system --add safe.directory /home/ubuntu/prod/caelium

# Fetch latest changes
git fetch --all

# Stash any local changes
git stash

# Pull latest from main
git pull origin main

# Activate virtual environment
source venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Restart the service
sudo supervisorctl restart caelium