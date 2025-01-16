"""Upload Videos Through Youtube API"""
import os
import google_auth_httplib2
import google_auth_oauthlib
import googleapiclient.discovery
import googleapiclient.errors
import googleapiclient.http

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def authenticate_youtube(client_secrets_file):
    """Authenticate Youtube UploadRequest"""
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        client_secrets_file, SCOPES)
    credentials = flow.run_local_server()

    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=credentials)

    return youtube

def upload_video(youtube,media_file,request_body):
    """Upload Video To YouTube via API"""

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=googleapiclient.http.MediaFileUpload(media_file, chunksize=-1, resumable=True)
    )

    response = None

    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload {int(status.progress()*100)}%")

        print(f"Video uploaded with ID: {response['id']}")
        with open("status_report.txt","w",encoding="utf-8") as f:
            f.write(f"Video uploaded with ID: {response['id']}")
