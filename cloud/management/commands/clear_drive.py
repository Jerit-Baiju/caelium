import os

from django.core.management.base import BaseCommand
from googleapiclient.http import BatchHttpRequest

from cloud.google_drive import GoogleDriveStorage


class Command(BaseCommand):
    help = "Clear all files from the Google Drive folder"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of files to delete in a single batch request (default: 100)'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        drive = GoogleDriveStorage()
        folder_id = drive.DRIVE_FOLDER_ID
        files_deleted = 0

        try:
            # List all files in the folder
            self.stdout.write("Fetching files from Google Drive...")
            
            # Get all files in the folder
            response = drive.service.files().list(
                q=f"'{folder_id}' in parents",
                fields="files(id, name), nextPageToken",
                pageSize=1000
            ).execute()
            
            files = response.get("files", [])
            next_page_token = response.get("nextPageToken")
            
            # Continue fetching if there are more files
            while next_page_token:
                next_page = drive.service.files().list(
                    q=f"'{folder_id}' in parents",
                    fields="files(id, name), nextPageToken",
                    pageToken=next_page_token,
                    pageSize=1000
                ).execute()
                files.extend(next_page.get("files", []))
                next_page_token = next_page.get("nextPageToken")

            total_files = len(files)
            if not total_files:
                self.stdout.write("No files found in the folder.")
                return

            self.stdout.write(f"Found {total_files} files. Starting deletion...")
            
            # Process files in batches
            for i in range(0, total_files, batch_size):
                batch = files[i:i + batch_size]
                batch_request = drive.service.new_batch_http_request()
                
                for file in batch:
                    batch_request.add(
                        drive.service.files().delete(fileId=file["id"]),
                        callback=self._create_callback(file["name"], file["id"])
                    )
                
                # Execute the batch request
                self.stdout.write(f"Deleting batch {i//batch_size + 1} ({len(batch)} files)...")
                batch_request.execute()
                files_deleted += len(batch)
                self.stdout.write(f"Progress: {files_deleted}/{total_files} files deleted")

            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {files_deleted} files from Google Drive."))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"An error occurred: {str(e)}"))
    
    def _create_callback(self, name, file_id):
        """Create a callback function for batch request that handles both success and error"""
        def callback(request_id, response, exception):
            if exception:
                # Handle the error
                self.stdout.write(self.style.WARNING(
                    f"Error deleting file: {name} (ID: {file_id}): {str(exception)}"
                ))
            # No need to handle success case for delete operations as there's no response
            
        return callback
