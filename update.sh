#!/bin/bash
# This script is placed on your servers (e.g., in PROJECT_PATH)
# and is executed by the /api/update endpoint in your Django app.
# It pulls the latest release tag and restarts the service.

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting server update..."

# Ensure we are in the correct project directory.
# This assumes the script is run from the PROJECT_PATH
# or you can cd to it explicitly.
# cd /path/to/your/project || exit

# Fetch all tags and branches
git fetch --all --tags

# Get the latest tag name
latest_tag=$(git describe --tags `git rev-list --tags --max-count=1`)

if [ -z "$latest_tag" ]; then
    echo "Error: No tags found. Cannot update."
    exit 1
fi

echo "Checking out latest tag: $latest_tag"
git checkout $latest_tag

# Activate virtual environment
echo "Activating venv..."
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "Running migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Restart the application server
echo "Restarting supervisor process..."
sudo supervisorctl restart caelium

echo "Update to $latest_tag complete."
