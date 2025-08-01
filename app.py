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

    payload = {
        "text": text,
    }
    if duration is not None:
        payload["duration_seconds"] = duration

    try:
        response = requests.post(
            "https://api.elevenlabs.io/v1/sound-generation",
            headers={
                "xi-api-key": os.getenv("ELEVENLABS_API_KEY"),
                "Content-Type": "application/json"
            },
            json=payload
        )
        response.raise_for_status()
        result = response.json()

        # Вернём task_id клиенту для дальнейшего ожидания
        return jsonify({
            "task_id": result.get("task_id")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/background/status/<task_id>")
def background_status(task_id):
    try:
        response = requests.get(
            f"https://api.elevenlabs.io/v1/sound-effects/task/{task_id}",
            headers={"xi-api-key": os.getenv("ELEVENLABS_API_KEY")}
        )
        response.raise_for_status()
        data = response.json()
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
