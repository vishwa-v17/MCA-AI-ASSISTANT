from flask import Blueprint, request, jsonify, session
from app.config import Config
from database import save_user_api_config, get_user_api_config
import requests

config_bp = Blueprint('config', __name__)


@config_bp.route('/api/config', methods=['GET'])
def get_config():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']

    cfg = get_user_api_config(user_id)

    return jsonify({
        "api_key": cfg.get("api_key", ""),
        "model": cfg.get("model", "")
    })


@config_bp.route('/api/config', methods=['POST'])
def set_config():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']

    data = request.json or {}

    api_key = data.get("api_key", "").strip()
    model = data.get("model", "").strip()

    if not api_key:
        return jsonify({
            "status": "error",
            "message": "API Key is required."
        }), 400

    if not model:
        return jsonify({
            "status": "error",
            "message": "Model is required."
        }), 400

    # Validate API key by hitting OpenRouter API
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    try:
        res = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=10
        )

        if res.status_code == 200:

            # Save configuration ONLY for this logged-in user
            save_user_api_config(
                user_id=user_id,
                api_key=api_key,
                model=model
            )

            return jsonify({
                "status": "success",
                "message": "Settings updated successfully."
            })

        else:
            return jsonify({
                "status": "error",
                "message": "Invalid API Key or connectivity issue."
            }), 400

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Validation failed: {str(e)}"
        }), 500

{
  "api_key": "",
  "model": "nvidia/nemotron-3-ultra-550b-a55b:free"
}
