import os
from django.core.management.base import BaseCommand
from cloud.google_drive import GoogleDriveStorage


class Command(BaseCommand):
    help = "Clear all files from the Google Drive folder"

    def handle(self, *args, **kwargs):
        drive = GoogleDriveStorage()
        folder_id = drive.DRIVE_FOLDER_ID

        try:
            # List all files in the folder
            files = drive.service.files().list(
                q=f"'{folder_id}' in parents",
                fields="files(id, name)"
            ).execute().get("files", [])

            if not files:
                self.stdout.write("No files found in the folder.")
                return

            # Delete each file
            for file in files:
                drive.delete_file(file["id"])
                self.stdout.write(f"Deleted file: {file['name']} (ID: {file['id']})")

            self.stdout.write("All files have been cleared from the folder.")

        except Exception as e:
            self.stderr.write(f"An error occurred: {str(e)}")
