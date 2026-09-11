from flask import Blueprint, request, jsonify, session

from database import get_user_ai_config, save_user_ai_config, delete_user_api_config
from app.services.openrouter_service import (
    get_server_api_key,
    get_default_model,
    get_model_catalog,
    validate_model,
)

config_bp = Blueprint('config', __name__)


def _authenticated_user_id():
    return session.get("user_id")


def _effective_key(user_id):
    cfg = get_user_ai_config(user_id)
    personal = cfg.get("api_key", "")
    return personal or get_server_api_key(), personal


@config_bp.route('/api/config', methods=['GET'])
def get_config():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        cfg = get_user_ai_config(user_id)
    except RuntimeError:
        return jsonify({"error": "Stored personal API key could not be decrypted."}), 500

    return jsonify({
        "provider": "OpenRouter",
        "has_personal_key": bool(cfg.get("api_key")),
        "personal_key_last4": cfg.get("api_key_last4", "") if cfg.get("api_key") else "",
        "api_key_status": "Using your personal OpenRouter key" if cfg.get("api_key") else "Using default server key",
        "server_default_available": bool(get_server_api_key()),
        "model": cfg.get("model") or get_default_model(),
        "default_model": get_default_model(),
    })


@config_bp.route('/api/config/models', methods=['GET'])
def get_models():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        api_key, _ = _effective_key(user_id)
    except RuntimeError:
        return jsonify({"error": "Stored personal API key could not be decrypted."}), 500

    if not api_key:
        return jsonify({
            "error": "AI service is not configured.",
            "free_models": [{
                "id": "openrouter/free",
                "name": "OpenRouter Free Router",
                "provider": "OpenRouter",
                "free": True,
                "description": "Automatically selects an available free model.",
                "context_length": 200000,
            }],
            "all_models": [],
        }), 503

    catalog, error = get_model_catalog(api_key)
    if error:
        return jsonify({"error": error}), 502

    return jsonify(catalog)


@config_bp.route('/api/config/validate-key', methods=['POST'])
def validate_key():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    api_key = str(data.get("api_key") or "").strip()
    if not api_key:
        return jsonify({"status": "error", "message": "Enter an OpenRouter API key to validate."}), 400

    # Validation is performed against OpenRouter without persisting the key.
    catalog, error = get_model_catalog(api_key, force=True)
    if error:
        return jsonify({"status": "error", "message": "Invalid OpenRouter API key or OpenRouter could not be reached."}), 400

    return jsonify({
        "status": "success",
        "message": "OpenRouter API key connected successfully.",
        "available_models": len(catalog["all_models"]),
    })


@config_bp.route('/api/config', methods=['POST'])
def set_config():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or {}
    new_api_key = data.get("api_key")
    model = str(data.get("model") or "").strip()

    try:
        current = get_user_ai_config(user_id)
    except RuntimeError:
        return jsonify({"status": "error", "message": "Stored personal API key could not be decrypted. Remove it and add it again."}), 500

    # An omitted api_key means "do not change the current personal key".
    if new_api_key is None:
        api_key_for_validation = current.get("api_key") or get_server_api_key()
        api_key_to_save = None
    else:
        api_key_to_save = str(new_api_key).strip()
        if not api_key_to_save:
            return jsonify({
                "status": "error",
                "message": "Use Remove Personal Key to return to server default access."
            }), 400
        api_key_for_validation = api_key_to_save

        catalog, error = get_model_catalog(api_key_for_validation, force=True)
        if error:
            return jsonify({
                "status": "error",
                "message": "Invalid OpenRouter API key or OpenRouter could not be reached."
            }), 400

    if not model:
        model = current.get("model") or get_default_model()

    if not api_key_for_validation:
        return jsonify({
            "status": "error",
            "message": "AI service is not configured on the server."
        }), 503

    if not validate_model(model, api_key_for_validation):
        return jsonify({
            "status": "error",
            "message": "This model is currently unavailable. Please select another model."
        }), 400

    try:
        save_user_ai_config(
            user_id=user_id,
            api_key=api_key_to_save,
            model=model,
        )
    except RuntimeError:
        return jsonify({
            "status": "error",
            "message": "Could not securely store the personal API key. Check USER_KEY_ENCRYPTION_SECRET."
        }), 500

    return jsonify({
        "status": "success",
        "message": "Settings updated successfully.",
        "using_personal_key": bool(api_key_to_save or current.get("api_key")),
        "model": model,
    })


@config_bp.route('/api/config/key', methods=['DELETE'])
def remove_personal_key():
    user_id = _authenticated_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    current = get_user_ai_config(user_id)
    # Keep the user's model preference while removing only the personal key.
    save_user_ai_config(user_id, api_key="", model=current.get("model") or get_default_model())

    return jsonify({
        "status": "success",
        "message": "Personal API key removed. The application will now use the server default key.",
        "using_personal_key": False,
    })

