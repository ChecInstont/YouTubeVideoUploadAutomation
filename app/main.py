import os
import io
import aiofiles
import pickle
import httpx
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import asyncio

# Initialize FastAPI app
app = FastAPI()

# Load environment variables for storage configuration
STORAGE_MODE = os.getenv("STORAGE_MODE", "memory")  # Can be "disk" or "memory"
UPLOAD_DIR = os.getenv("VIDEOS_DIRECTORY", "uploaded_videos")  # Directory for disk storage
CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")  # OAuth credentials path

# OAuth 2.0 scope and token storage
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PICKLE = "token.pickle"

# Create directory for disk storage if needed
if STORAGE_MODE == "disk" and not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# Authenticate and return the YouTube API client
async def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=8000)

        with open(TOKEN_PICKLE, 'wb') as token:
            pickle.dump(creds, token)

    return build("youtube", "v3", credentials=creds)

# Function to upload video to YouTube
async def upload_to_youtube(video_path: str, title: str, description: str, tags: List[str], privacy: str, category_id: str):
    youtube = await get_authenticated_service()

    # Set video metadata
    request_body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
        },
    }

    # Initialize file upload
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    upload_request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    try:
        # Run the upload in a separate thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: upload_request.execute())

        # Return video ID and URL
        return {
            "video_id": response["id"],
            "url": f"https://youtu.be/{response['id']}"
        }

    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"HTTP request error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

# Endpoint to upload video and send to YouTube

@app.post("/api/upload/video")
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    tags: List[str] = Form([]),
    privacy: str = Form("public"),
    category_id: str = Form("22"),
):
    """
    Upload a video and send it to YouTube Shorts.
    - `file`: Video file to upload
    - `title`: Title of the video
    - `description`: Description of the video
    - `tags`: List of tags for the video
    - `privacy`: Privacy setting ('public', 'private', 'unlisted')
    - `category_id`: YouTube category ID
    """
    try:
        # Validate file type
        if not file.content_type.startswith("video/"):
            raise HTTPException(status_code=400, detail="Only video files are allowed.")

        if STORAGE_MODE == "disk":
            # Handle file storage on disk
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            async with aiofiles.open(file_path, "wb") as buffer:
                while chunk := await file.read(1024 * 1024):  # Read in 1MB chunks
                    await buffer.write(chunk)
        else:
            # Handle file storage in memory using BytesIO
            file_bytes = io.BytesIO(await file.read())  # File stored entirely in memory
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            file_path = temp_file.name
            with open(file_path, "wb") as f:
                f.write(file_bytes.getvalue())

        # Upload the video to YouTube
        youtube_response = await upload_to_youtube(
            video_path=file_path,
            title=title,
            description=description,
            tags=tags,
            privacy=privacy,
            category_id=category_id,
        )

        # Cleanup: if stored on disk, remove the file
        if STORAGE_MODE == "disk" and os.path.exists(file_path):
            os.remove(file_path)

        return {
            "message": "Video uploaded successfully to YouTube.",
            "youtube_response": youtube_response,
        }

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"An unexpected error occurred: {str(e)}"}
        )
