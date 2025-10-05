from flask import Flask, request, render_template, send_file
import os
import random
import re
from proglog import ProgressBarLogger
from werkzeug.utils import secure_filename
from moviepy import VideoFileClip, VideoClip, concatenate_videoclips
from moviepy.video.fx.FadeIn import FadeIn
from moviepy.video.fx.FadeOut import FadeOut
from moviepy.video.fx.MultiplySpeed import MultiplySpeed

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
from PIL import Image
from moviepy.video import fx as vfx
from moviepy.video.io.ffmpeg_writer import ffmpeg_write_video
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip
from moviepy.tools import subprocess_call


def split_srt_by_blocks(srt_text, num_parts=4):
    """Split .srt into full subtitle blocks evenly (not cutting lines)."""
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


class FlaskProgressLogger(ProgressBarLogger):
    def callback(self, **changes):
        if changes.get("progress"):
            # Save progress percentage (0–100)
            progress["percent"] = int(changes["progress"] * 100)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        action = request.form.get("action")

        # 1️⃣ Generate Raw Transcript (SRT → 4 Files)
        if action == "generate_srt":
            movie_file = request.files.get("movie_file")
            if movie_file:
                video_filename = secure_filename(movie_file.filename)
                video_path = os.path.join(UPLOAD_FOLDER, video_filename)
                movie_file.save(video_path)

                srt_filename = os.path.splitext(video_filename)[0] + ".srt"
                srt_path = os.path.join(UPLOAD_FOLDER, srt_filename)

                # Extract subtitles using ffmpeg
                cmd = f'ffmpeg -y -i "{video_path}" -map 0:s:0 "{srt_path}"'
                os.system(cmd)

                if not os.path.exists(srt_path):
                    return "No subtitles found in video."

                with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read()

                # Split into full subtitle parts (not breaking lines)
                parts = split_srt_by_blocks(raw_text)

                # Save each part into a separate file
                part_filenames = []
                for i, part in enumerate(parts, start=1):
                    part_filename = f"{os.path.splitext(video_filename)[0]}_part{i}.srt"
                    part_path = os.path.join(UPLOAD_FOLDER, part_filename)
                    with open(part_path, "w", encoding="utf-8") as f:
                        f.write(part)
                    part_filenames.append(part_filename)

                # Show filenames on page (no automatic download)
                return render_template(
                    "index.html",
                    show_tabs=True,
                    part_files=part_filenames,
                    video_filename=video_filename,
                )

        # 2️⃣ Trim Video using pasted transcript
        elif action == "trim":
            transcript_text = request.form.get("transcript_text")
            video_filename_input = request.form.get("video_filename")

            video_path = os.path.join(UPLOAD_FOLDER, secure_filename(video_filename_input))
            if not os.path.exists(video_path):
                return f"Error: Video file not found: {video_filename_input}"

            # Parse transcript timestamps
            lines = transcript_text.strip().split("\n")
            entries = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                match = re.match(r"(\d{2}):(\d{2}):(\d{2}),?(\d{0,3})?", line)
                if match:
                    h, m, s, ms = match.groups()
                    ms = int(ms) / 1000 if ms else 0
                    seconds = int(h) * 3600 + int(m) * 60 + int(s) + ms
                    entries.append(seconds)

            if not entries:
                return "Error: No valid timestamps found in transcript."

            CLIP_DURATION = 2.5
            with VideoFileClip(video_path) as video:
                video = vfx.MirrorX().apply(video)
                # # Width and height of the crop
                # crop_width = 600
                # crop_height = 300

                # # Slightly left of center (e.g., 100 pixels to the left)
                # x_center = (clip.w / 2) + 100  
                # y_center = clip.h / 2  # keep vertical center

                # clip = Crop(
                #     x_center=x_center,
                #     y_center=y_center,
                #     width=crop_width,
                #     height=crop_height
                # ).apply(clip)     
                subclips = []
                transitions = [
                    lambda c: FadeIn(duration=0.5).apply(FadeOut(duration=0.5).apply(c)),
                ]

                for start_time in entries:
                    start = start_time + 2  # optional offset
                    end = min(start + CLIP_DURATION, video.duration)
                    clip = video.subclipped(start, end)
                    # 1️⃣ Slow the clip to 0.5x speed
                    clip = MultiplySpeed(factor=0.5).apply(clip)
                    clip.preview()

                    # 3️⃣ Apply random transition effect
                    effect = random.choice(transitions)
                    subclips.append(effect(clip))

                final_clip = concatenate_videoclips(subclips, method="compose")

                trimmed_filename = os.path.splitext(video_filename_input)[0] + "_trimmed.mp4"
                trimmed_path = os.path.join(UPLOAD_FOLDER, trimmed_filename)
                
                #  Delete uploaded video 
                try: 
                    os.remove(video_path) 
                except Exception: 
                    pass

                logger = FlaskProgressLogger()

                final_clip.write_videofile(
                    trimmed_path,
                    codec="libx264",
                    audio_codec="aac",
                    threads=4,
                    fps=video.fps or 30,
                    logger=logger
                )

            return send_file(trimmed_path, as_attachment=True)

    return render_template("index.html", show_tabs=False)



@app.route("/download/<filename>")
def download_file(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return "File not found.", 404
    
@app.route("/progress")
def get_progress():
    return {"percent": 100}

if __name__ == "__main__":
    app.run(debug=True)
