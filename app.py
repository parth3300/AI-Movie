from flask import Flask, request, send_file, jsonify, render_template, send_from_directory
from flask_cors import CORS
from io import BytesIO
import requests
import os       # ✅ Needed for file paths, directories, etc.

app = Flask(__name__)
CORS(app)  # allow frontend requests

app = Flask(__name__)
UPLOAD_FOLDER = "downloads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Remote ngrok URL
# NGROK_URL = "https://filosus-impartibly-contessa.ngrok-free.dev/"

NGROK_URL = "https://innocently-nonsustained-bari.ngrok-free.dev/"

# Video name already on server
VIDEO_NAME = "Joker.mp4"


@app.route("/")
def index():
    return render_template("index.html")




UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/generate_srt", methods=["POST"])
def generate_srt():
    data = {"action": "srt", "video_filename": VIDEO_NAME}

    try:
        response = requests.post(NGROK_URL, data=data)
        content_type = response.headers.get("content-type", "")

        # 🧠 Case 1: JSON response from Colab
        if "application/json" in content_type:
            response_json = response.json()

        # 🧠 Case 2: Plain text response (e.g., error or log)
        elif "text" in content_type or response.text.strip().startswith("{"):
            try:
                response_json = json.loads(response.text)
            except Exception:
                return jsonify({"error": "Unexpected text response from Colab", "content": response.text}), 500

        # 🧠 Case 3: Empty or non-JSON (likely ffmpeg issue)
        else:
            return jsonify({"error": "Colab did not return valid JSON", "status": response.status_code, "body": response.text[:200]}), 500

        if "error" in response_json:
            return jsonify({"error": response_json["error"]}), 500

        # ✅ Now safely download all part files
        local_files = []
        for part_file in response_json.get("parts_created", []):
            file_url = f"{NGROK_URL}download/{part_file}"
            file_resp = requests.get(file_url, stream=True)
            if file_resp.status_code != 200:
                return jsonify({"error": f"Could not download {part_file} from Colab"}), 500

            local_path = os.path.join(UPLOAD_FOLDER, part_file)
            with open(local_path, "wb") as f:
                for chunk in file_resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            local_files.append(part_file)

        # ✅ Return downloadable local links to frontend
        download_links = [f"/download/{f}" for f in local_files]
        return jsonify({"files": download_links})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download_file(filename):
    """Serve downloaded SRT parts"""
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

@app.route("/trim", methods=["POST"])
def trim_video():
    """
    Call remote server to trim video.
    Expects `transcript_text` in JSON body from frontend.
    """
    json_data = request.get_json()
    transcript_text = json_data.get("transcript_text", "")

    data = {
        "action": "trim",
        "video_filename": VIDEO_NAME,
        "transcript_text": transcript_text
    }

    try:
        response = requests.post(NGROK_URL, data=data, stream=True)

        if "video/mp4" in response.headers.get("Content-Type", ""):
            # Send video as downloadable file
            video_stream = BytesIO(response.content)
            return send_file(
                video_stream,
                mimetype="video/mp4",
                as_attachment=True,
                download_name="trimmed_video.mp4"
            )
        else:
            # Otherwise, return server message
            return (response.content, response.status_code, response.headers.items())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
