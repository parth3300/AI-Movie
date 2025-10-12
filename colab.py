import requests

# 🔗 Replace with your actual ngrok link
url = "https://filosus-impartibly-contessa.ngrok-free.dev"

# Choose your uploaded video name inside /content/uploads
video_filename = "your_video.mp4"

# Example of transcript timestamps
transcript_text = """
00:00:02,000
00:00:10,000
00:00:20,000
"""

data = {
    "action": "trim",
    "video_filename": video_filename,
    "transcript_text": transcript_text
}

response = requests.post(url, data=data)

# If it returns a video file, save it
if response.headers.get("content-type") == "video/mp4":
    with open("trimmed_video.mp4", "wb") as f:
        f.write(response.content)
    print("✅ Trimmed video saved as trimmed_video.mp4")
else:
    print("Server response:", response.text)
