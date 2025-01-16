"""Upload Youtube videos directly from code"""

import json
from youtube_upload import authenticate_youtube,upload_video

# Load Oauth credentials file, put the path of your file
CREDENTIALS_FILE = "credentials.json"
media_files_list = []

with open("video_details.json","r",encoding="utf-8") as f:
    media_files_list = json.load(f)

youtube = authenticate_youtube(client_secrets_file=CREDENTIALS_FILE)
for each_file in media_files_list:
    upload_video(
        youtube=youtube,
        media_file=each_file["file"],
        request_body=each_file["details"]
        )
