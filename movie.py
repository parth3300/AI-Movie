from moviepy.video.io.VideoFileClip import VideoFileClip

# Load your video
video = VideoFileClip("Forrest.Gump.1994.1080p.Hindi.English.MoviesFlixPro.in.mkv")

# Trim from 00:02:30 to 00:05:00 (2min30s–5min)
trimmed = video.subclipped("00:02:30", "00:05:00")

# Save it as a new file
trimmed.write_videofile("trimmed_scene.mp4", codec="libx264", audio_codec="aac")


    