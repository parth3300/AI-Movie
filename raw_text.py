import google.generativeai as genai
import re

# -----------------------------
# CONFIG
# -----------------------------
SRT_FILE = "subs.srt"
OUTPUT_FILE = "gujarati_narration.txt"
GEMINI_API_KEY = "your_gemini_api_key_here"  # Get from: https://aistudio.google.com/
CHUNK_SIZE = 500

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Same SRT parsing function as before
def srt_to_raw_transcript(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    blocks = re.split(r'\n\s*\n', content.strip())
    transcript_lines = []

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            timestamp_line = lines[1]
            text = " ".join(lines[2:])
            start_time = timestamp_line.split(" --> ")[0].replace(",", ".")
            transcript_lines.append(f"{start_time} - {text}")

    return "\n".join(transcript_lines)

raw_transcript = srt_to_raw_transcript(SRT_FILE)
print(f"✅ Raw transcript extracted from {SRT_FILE}")

# Process with Gemini
lines = raw_transcript.split("\n")
chunks = [lines[i:i + CHUNK_SIZE] for i in range(0, len(lines), CHUNK_SIZE)]
final_transcript_parts = []

for idx, chunk in enumerate(chunks):
    chunk_text = "\n".join(chunk)
    prompt = f"""
You are a professional movie narrator.
Here is a raw timestamped transcript of a part of a movie:

{chunk_text}

Task:
- Summarize only the main scenes and important dialogues.
- Keep the timestamps exactly as in the raw transcript.
- Paraphrase dialogues into a storytelling style.
- Output the final transcript in Gujarati.
- Format output like:
00:00:05 - [Gujarati narration about this scene]
"""

    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        final_transcript_parts.append(response.text)
        print(f"✅ Chunk {idx + 1}/{len(chunks)} processed")
    except Exception as e:
        print(f"❌ Error processing chunk {idx + 1}: {e}")

# Save results
if final_transcript_parts:
    final_transcript = "\n\n".join(final_transcript_parts)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(final_transcript)
    print(f"✅ Gujarati narration saved to {OUTPUT_FILE}")
else:
    print("❌ No content processed")