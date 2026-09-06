from flask import Blueprint, request, jsonify, session
from app.config import Config
import requests

config_bp = Blueprint('config', __name__)

@config_bp.route('/api/config', methods=['GET'])
def get_config():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    cfg = Config.load_api_config()
    return jsonify({
        "api_key": cfg.get("api_key", ""),
        "model": cfg.get("model", "")
    })

@config_bp.route('/api/config', methods=['POST'])
def set_config():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json
    api_key = data.get("api_key")
    model = data.get("model")
    
    # Validate by hitting OpenRouter API
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        res = requests.get("https://openrouter.ai/api/v1/models", headers=headers, timeout=10)
        if res.status_code == 200:
            Config.save_api_config({"api_key": api_key, "model": model})
            return jsonify({"status": "success", "message": "Settings updated successfully."})
        else:
            return jsonify({"status": "error", "message": "Invalid API Key or connectivity issue."}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Validation failed: {str(e)}"}), 500
