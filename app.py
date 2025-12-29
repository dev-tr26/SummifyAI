import os
import re
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable
)

load_dotenv()


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

app = Flask(__name__)
CORS(app)

PROMPT = """
You are a YouTube video summarizer.
Summarize the transcript below into a clean, concise bullet-point summary
within 250 words. Use clear, structured formatting.

Transcript:
"""


@app.route('/')
def index():
    return render_template('index.html')



def extract_transcript_details(youtube_video_url: str) -> str:
    try:
        match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", youtube_video_url)
        if not match:
            raise ValueError("Invalid YouTube URL format")

        video_id = match.group(1)

        transcript_items = YouTubeTranscriptApi().fetch(video_id)

        transcript = " ".join(item.text for item in transcript_items)

        if not transcript.strip():
            raise Exception("Transcript is empty")

        return transcript[:5000]

    except TranscriptsDisabled:
        raise Exception("Transcripts are disabled for this video")

    except NoTranscriptFound:
        raise Exception("No transcript available for this video")

    except VideoUnavailable:
        raise Exception("Video is unavailable or private")

    except Exception as e:
        raise Exception(f"Transcript fetch failed: {str(e)}")



def generate_llama_summary(transcript: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "You are a YouTube video summarizer."},
            {"role": "user", "content": PROMPT + transcript}
        ],
        "temperature": 0.7
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code != 200:
        raise Exception(f"Groq API Error: {response.status_code} {response.text}")

    return response.json()["choices"][0]["message"]["content"]



@app.route('/api/summarize', methods=['POST'])
def summarize_video():
    data = request.get_json(silent=True)
    video_url = data.get("url") if data else None

    if not video_url:
        return jsonify({"error": "No YouTube URL provided"}), 400

    try:
        transcript = extract_transcript_details(video_url)
        summary = generate_llama_summary(transcript)
        return jsonify({"summary": summary}), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
