from flask import Blueprint, request, jsonify, session, Response
import uuid
import json
from werkzeug.utils import secure_filename

from app.services.db_service import (
    create_session,
    get_sessions,
    delete_session,
    get_session_messages,
    save_message,
    rename_session,
    toggle_pin_session
)

from app.services.llm_service import generate_streaming_response
from app.config import Config
from app.routes.upload import _validate_and_save_file
from database import get_user_ai_config
from app.services.openrouter_service import get_server_api_key, get_default_model, validate_model
from app.services.rate_limiter import user_rate_limiter


chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/api/sessions', methods=['GET', 'POST'])
def sessions_api():

    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user_id = session['user_id']

    if request.method == 'GET':
        sessions = get_sessions(user_id)
        return jsonify({"sessions": sessions})

    if request.method == 'POST':
        data = request.json or {}
        title = data.get('title', 'New Chat Session')

        session_id = str(uuid.uuid4())

        create_session(
            session_id,
            user_id,
            title
        )

        return jsonify({
            "session_id": session_id,
            "title": title
        })


@chat_bp.route('/api/sessions/<session_id>', methods=['DELETE'])
def delete_session_api(session_id):

    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    delete_session(
        session_id,
        session['user_id']
    )

    return jsonify({
        "status": "success"
    })


@chat_bp.route('/api/sessions/<session_id>/rename', methods=['PUT'])
def rename_session_api(session_id):

    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    new_title = data.get('title')

    if new_title:
        rename_session(
            session_id,
            session['user_id'],
            new_title
        )

        return jsonify({
            "status": "success"
        })

    return jsonify({
        "error": "Invalid title"
    }), 400


@chat_bp.route('/api/sessions/<session_id>/pin', methods=['PUT'])
def pin_session_api(session_id):

    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json or {}
    is_pinned = data.get('is_pinned', False)

    toggle_pin_session(
        session_id,
        session['user_id'],
        is_pinned
    )

    return jsonify({
        "status": "success"
    })


@chat_bp.route('/api/sessions/<session_id>/messages', methods=['GET'])
def session_messages_api(session_id):

    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    messages = get_session_messages(session_id)

    return jsonify({
        "messages": messages
    })


@chat_bp.route('/chat', methods=['POST'])
def chat():

    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    # Get the currently logged-in user's ID
    user_id = session['user_id']

    if request.content_type and 'multipart/form-data' in request.content_type:

        user_message = request.form.get(
            "message",
            ""
        ).strip()

        session_id = request.form.get(
            "session_id"
        )

        file = request.files.get(
            "file"
        )

    else:

        data = request.json or {}

        user_message = data.get(
            "message",
            ""
        ).strip()

        session_id = data.get(
            "session_id"
        )

        file = None

    if not session_id or (not user_message and not file):
        return jsonify({
            "error": "Missing message, session_id, or file"
        }), 400

    # If an attached file was sent with the message
    if file and file.filename:

        valid, msg, unique_name, extracted_text = _validate_and_save_file(file)

        if not valid:
            return jsonify({
                "error": msg
            }), 400

        safe_name = secure_filename(
            file.filename
        ) or unique_name

        # Prepare AI prompt with extracted text/attachment info
        if extracted_text and len(extracted_text.strip()) > 0:

            truncated = extracted_text.strip()[:6000]

            if len(extracted_text.strip()) > 6000:
                truncated += (
                    "\n[... Document content truncated for length ...]"
                )

            if user_message:

                prompt_for_ai = (
                    f"📎 [Attached Document: {safe_name}]\n\n"
                    f"--- Document Content ---\n"
                    f"{truncated}\n\n"
                    f"--- Student Question/Task ---\n"
                    f"{user_message}"
                )

            else:

                prompt_for_ai = (
                    f"📎 [Attached Document: {safe_name}]\n\n"
                    f"--- Document Content ---\n"
                    f"{truncated}\n\n"
                    f"Please analyze this document and summarize "
                    f"the key MCA topics and concepts it covers."
                )

        else:

            if user_message:

                prompt_for_ai = (
                    f"📎 [Attached File: {safe_name}]\n\n"
                    f"{user_message}"
                )

            else:

                prompt_for_ai = (
                    f"📎 [Attached File: {safe_name}]\n\n"
                    f"Please review and explain the academic concepts "
                    f"related to this attached MCA study material."
                )

        display_user_msg = f"📎 {safe_name}"

        if user_message:
            display_user_msg += (
                f"\n\n{user_message}"
            )

        save_message(
            session_id,
            "user",
            display_user_msg
        )

    else:

        save_message(
            session_id,
            "user",
            user_message
        )

        prompt_for_ai = user_message

    # ---------------------------------------------------------
    # Resolve AI credentials server-side.
    # Personal key wins; otherwise use the server environment key.
    # Neither key is ever sent back to the browser.
    # ---------------------------------------------------------
    try:
        api_config = get_user_ai_config(user_id)
    except RuntimeError:
        return jsonify({"error": "Your saved personal API key could not be loaded. Please remove it from Settings and add it again."}), 500

    personal_key = api_config.get("api_key", "")
    api_key = personal_key or get_server_api_key()
    model = api_config.get("model") or get_default_model()

    if not api_key:
        return jsonify({
            "error": "AI service is not configured. Please contact the server administrator."
        }), 503

    if len(user_message) > Config.MAX_AI_MESSAGE_LENGTH:
        return jsonify({
            "error": f"Message is too long. Maximum allowed length is {Config.MAX_AI_MESSAGE_LENGTH} characters."
        }), 400

    # The shared server key is rate-limited per authenticated user.
    if not personal_key and not user_rate_limiter.allow(
        user_id,
        Config.AI_RATE_LIMIT_PER_MINUTE,
        Config.AI_RATE_LIMIT_PER_HOUR,
    ):
        return jsonify({
            "error": "Request limit reached. Please try again later or use your personal OpenRouter API key."
        }), 429

    if not validate_model(model, api_key):
        return jsonify({
            "error": "This model is currently unavailable. Please select another model in Settings."
        }), 400

    # Fetch context
    history = get_session_messages(
        session_id
    )

    system_prompt = Config.get_system_prompt()

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    for msg in history[-6:]:

        role = (
            "assistant"
            if msg['sender'] == "bot"
            else "user"
        )

        content = msg['content']

        # Trim historical attached document bodies
        # to keep latency low
        if len(content) > 1500 and msg != history[-1]:

            content = (
                content[:1500]
                + "... [prior attachment trimmed for speed]"
            )

        messages.append({
            "role": role,
            "content": content
        })

    # Ensure current turn uses prompt_for_ai
    if messages and messages[-1]["role"] == "user":

        messages[-1]["content"] = prompt_for_ai

    def stream_and_save():

        full_content = ""

        for chunk in generate_streaming_response(
            messages,
            model,
            api_key
        ):

            if chunk.startswith("data: "):

                data_str = chunk[6:].strip()

                if data_str != "[DONE]":

                    try:

                        parsed = json.loads(
                            data_str
                        )

                        if "content" in parsed:

                            full_content += (
                                parsed["content"]
                            )

                    except Exception:
                        pass

            yield chunk

        if full_content:

            save_message(
                session_id,
                "bot",
                full_content
            )

    resp = Response(
        stream_and_save(),
        mimetype='text/event-stream'
    )

    resp.headers['Cache-Control'] = (
        'no-cache, no-transform'
    )

    resp.headers['X-Accel-Buffering'] = 'no'

    resp.headers['Connection'] = 'keep-alive'

    return resp

