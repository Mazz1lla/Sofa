import os
import io
import requests
from flask import Flask, request, send_file, jsonify
from elevenlabs import generate, set_api_key
from dotenv import load_dotenv

load_dotenv()
set_api_key(os.getenv("ELEVENLABS_API_KEY"))

app = Flask(__name__)

@app.route("/")
def root():
    return "✅ ElevenLabs proxy server is running."

@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text", "")
    voice_id = data.get("voice_id", "Rachel")

    try:
        audio = generate(
            text=text,
            voice=voice_id,
            model="eleven_multilingual_v2"
        )

        return send_file(
            io.BytesIO(b"".join(audio)),
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name="voice.mp3"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/background", methods=["POST"])
def background():
    data = request.get_json()
    text = data.get("text", "")
    duration = data.get("duration_seconds", None)

    try:
        response = requests.post(
            "https://api.elevenlabs.io/v1/sound-generation",
            headers={
                "xi-api-key": os.getenv("ELEVENLABS_API_KEY"),
                "Content-Type": "application/json"
            },
            json={
                "text": text,
                "duration_seconds": duration
            }
        )
        response.raise_for_status()

        return send_file(
            io.BytesIO(response.content),
            mimetype="audio/mpeg",
            as_attachment=True,
            download_name="background.mp3"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
