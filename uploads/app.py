from flask import Flask, request, render_template, send_file
import os
import re
from proglog import ProgressBarLogger
from werkzeug.utils import secure_filename
from PIL import Image

# ✅ Correct MoviePy imports for version 2+
from moviepy.editor import VideoFileClip, concatenate_videoclips
from moviepy.video.fx import all as vfx
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

# ✅ Ngrok for Colab tunnel
from pyngrok import ngrok
import subprocess
import json

# Flask setup
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

progress = {"percent": 0}


# -------------------------------------------------------
# 🧩 Split SRT text evenly by subtitle blocks
# -------------------------------------------------------
def split_srt_by_blocks(srt_text, num_parts=4):
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    total_blocks = len(blocks)
    per_part = total_blocks // num_parts
    parts = []

    for i in range(num_parts):
        start = i * per_part
        end = (i + 1) * per_part if i < num_parts - 1 else total_blocks
        joined = "\n\n".join(blocks[start:end]).strip()
        parts.append(joined)
    return parts


# -------------------------------------------------------
# 📊 Custom MoviePy logger that updates progress for Flask
# -------------------------------------------------------
class FlaskProgressLogger(ProgressBarLogger):
    def callback(self, **changes):
        if changes.get("progress"):
            progress["percent"] = int(changes["progress"] * 100)


# -------------------------------------------------------
# 🧠 Routes
# -------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    print(request.method)
    print(request.form.get("action"))
    print("hi3")

    if request.method == "POST":
        action = request.form.get("action")

        if action == "srt":
            video_filename_input = request.form.get("video_filename")
            video_path = os.path.join(UPLOAD_FOLDER, video_filename_input)
            srt_filename = os.path.splitext(video_filename_input)[0] + ".srt"
            srt_path = os.path.join(UPLOAD_FOLDER, srt_filename)

            # 1️⃣ Find the subrip (text) subtitle stream
            cmd_probe = [
                "ffprobe", "-v", "error", "-select_streams", "s",
                "-show_entries", "stream=index,codec_name", "-of", "json",
                video_path
            ]
            probe_result = subprocess.run(cmd_probe, capture_output=True, text=True)
            streams = json.loads(probe_result.stdout).get("streams", [])

            text_stream_index = None
            for stream in streams:
                if stream.get("codec_name") == "subrip":  # text-based SRT
                    text_stream_index = stream["index"]
                    break

            if text_stream_index is None:
                return {"error": "No text-based subtitle stream found."}

            # 2️⃣ Extract SRT
            cmd_extract = f'ffmpeg -y -i "{video_path}" -map 0:{text_stream_index} "{srt_path}"'
            os.system(cmd_extract)

            # 3️⃣ Read SRT and clean
            if not os.path.exists(srt_path):
                return {"error": "Failed to create SRT file."}

            with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read().strip()

            blocks = re.split(r'\n\s*\n', raw_text)
            cleaned_blocks = []
            for block in blocks:
                lines = block.strip().split("\n")
                lines = [l for l in lines if not re.match(r"^\d+$", l.strip())]  # remove numbering
                if lines:
                    cleaned_blocks.append("\n".join(lines).strip())

            cleaned_srt_text = "\n\n".join(cleaned_blocks)
            parts = split_srt_by_blocks(cleaned_srt_text)

            # 4️⃣ Save each part
            part_filenames = []
            for i, part in enumerate(parts, start=1):
                part_filename = f"{os.path.splitext(video_filename_input)[0]}_part{i}.txt"
                part_path = os.path.join(UPLOAD_FOLDER, part_filename)
                with open(part_path, "w", encoding="utf-8") as f:
                    f.write(part)
                part_filenames.append(part_filename)

            # Sample for verification
            sample_lines = "\n".join(parts[0].split("\n")[:5])
            print("Sample of first SRT part:\n", sample_lines)

            return {"parts_created": part_filenames, "sample_first_part": sample_lines}
        # 2️⃣ Trim Video based on transcript
        elif action == "trim":
            transcript_text = request.form.get("transcript_text")
            video_filename_input = request.form.get("video_filename")

            video_path = os.path.join(UPLOAD_FOLDER, secure_filename(video_filename_input))
            if not os.path.exists(video_path):
                return f"Error: Video file not found: {video_filename_input}"

            # Parse timestamps
            lines = transcript_text.strip().split("\n")
            entries = []
            for line in lines:
                match = re.match(r"(\d{2}):(\d{2}):(\d{2}),?(\d{0,3})?", line.strip())
                if match:
                    h, m, s, ms = match.groups()
                    ms = int(ms) / 1000 if ms else 0
                    seconds = int(h) * 3600 + int(m) * 60 + int(s) + ms
                    entries.append(seconds)

            if not entries:
                return "Error: No valid timestamps found in transcript."

            CLIP_DURATION = 2.5
            output_files = []

            with VideoFileClip(video_path) as video:
                subclips = []
                for start_time in entries:
                    start = start_time + 2
                    end = min(start + CLIP_DURATION, video.duration)
                    clip = video.subclip(start, end)

                    # 🎥 Apply effects
                    clip = vfx.speedx(clip, 0.5)
                    clip = vfx.mirror_x(clip)
                    clip = vfx.fadein(clip, 0.5)
                    clip = vfx.fadeout(clip, 0.5)

                    subclips.append(clip)

                # 🎬 Merge clips in groups of 2
                for i in range(0, len(subclips), 2):
                    group = subclips[i:i+2]  # Take 2 clips at a time
                    merged_clip = concatenate_videoclips(group, method="compose")

                    trimmed_filename = f"{os.path.splitext(video_filename_input)[0]}_part_{(i//2)+1}.mp4"
                    trimmed_path = os.path.join(UPLOAD_FOLDER, trimmed_filename)

                    # Maintain aspect ratio and even width
                    new_height = 1080
                    new_width = int(merged_clip.w * (new_height / merged_clip.h))
                    if new_width % 2 != 0:
                        new_width += 1
                    merged_clip = merged_clip.resize(newsize=(new_width, new_height))

                    logger = FlaskProgressLogger()
                    merged_clip.write_videofile(
                        trimmed_path,
                        codec="libx264",
                        temp_audiofile="temp-audio.m4a",
                        audio=False,  # No audio
                        remove_temp=True,
                        ffmpeg_params=["-profile:v", "baseline", "-level", "3.0", "-pix_fmt", "yuv420p"],
                        threads=4,
                        fps=30,
                        logger=logger
                    )

                    output_files.append(trimmed_path)
                    merged_clip.close()

            # ✅ Option 1: Return first file for now (you can zip them later)
            if len(output_files) == 1:
                return send_file(output_files[0], as_attachment=True)
            else:
                # Or return as a zip file
                import zipfile
                zip_filename = os.path.splitext(video_filename_input)[0] + "_clips.zip"
                zip_path = os.path.join(UPLOAD_FOLDER, zip_filename)
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for f in output_files:
                        zipf.write(f, os.path.basename(f))
                return send_file(zip_path, as_attachment=True)

    # Default response
    return {"message": "Use POST / with 'action=generate_srt' or 'action=trim'"}


@app.route("/download/<filename>")
def download_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return {"error": "File not found"}, 404


@app.route("/progress")
def get_progress():
    return {"percent": progress.get("percent", 0)}

from IPython.display import Javascript, display
import time

# JS trick: simulate user interaction every 60 seconds
keep_alive = Javascript('''
function ClickConnect(){
    console.log("🔄 Keeping Colab alive...");
    document.querySelector("colab-toolbar-button#connect").click();
}
setInterval(ClickConnect, 60000);
''')

display(keep_alive)
print("✅ Keepalive script running. Now start your Flask cell.")

# -------------------------------------------------------
# 🚀 Start Flask with Ngrok Tunnel (for Colab)
# -------------------------------------------------------
if __name__ == "__main__":
    port = 2000
    public_url = ngrok.connect(port)
    print("🔥 Public URL:", public_url)
    app.run(host="0.0.0.0", port=port)
