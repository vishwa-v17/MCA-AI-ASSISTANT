import requests
import json
from app.config import Config

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Connection pooling for fast requests
session = requests.Session()

def generate_streaming_response(messages, model, api_key):
    """Generates a fast streaming response using OpenRouter API."""
    if not api_key or not model:
        yield "data: {\"error\": \"Missing API Key or Model in Configuration. Please update Settings.\"}\n\n"
        return

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000", 
        "X-Title": "MCA AI Assistant"
    }

    payload = {
        "model": model,
        "messages": messages,
        "stream": True
    }

    try:
        try:
            response = session.post(url, headers=headers, json=payload, stream=True, timeout=25)
        except requests.exceptions.SSLError:
            response = session.post(url, headers=headers, json=payload, stream=True, timeout=25, verify=False)

        if response.status_code != 200:
            try:
                err_data = response.json()
                error_message = err_data.get('error', {}).get('message', f'Status {response.status_code}')
            except Exception:
                error_message = response.text
            yield f"data: {{\"error\": \"API Error: {error_message}\"}}\n\n"
            return

        for line in response.iter_lines(chunk_size=1):
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        if content:
                            yield f"data: {json.dumps({'content': content})}\n\n"
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        yield f"data: {{\"error\": \"Connection Error: {str(e)}\"}}\n\n"


def generate_text_sync(prompt, model, api_key):
    """Generates text synchronously for tasks like generating notes/papers."""
    if not api_key or not model:
        return None, "Missing API Key or Model."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000", 
        "X-Title": "MCA AI Assistant"
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }

    try:
        # Increase timeout as generation can take longer
        try:
            response = session.post(url, headers=headers, json=payload, timeout=120)
        except requests.exceptions.SSLError:
            response = session.post(url, headers=headers, json=payload, timeout=120, verify=False)
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content, None
        else:
            try:
                err = response.json().get('error', {}).get('message', f'HTTP {response.status_code}')
            except:
                err = response.text
            return None, f"API Error: {err}"
    except Exception as e:
        return None, f"Connection Error: {str(e)}"
