"""Display useful OpenAI errors without exposing credentials or request text."""
import json
import re


def openai_error(status, payload, request_id=None, private=()):
    if isinstance(payload, bytes):
        try:
            payload = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    error = payload.get('error')
    parts = []
    if isinstance(error, dict):
        for key in ('code', 'type', 'param', 'message'):
            value = error.get(key)
            if isinstance(value, (str, int)) and value not in parts:
                parts.append(str(value))
    elif isinstance(error, str):
        parts.append(error)
    detail = payload.get('detail')
    if isinstance(detail, str):
        parts.append(detail)
    if not parts:
        parts.append('Request rejected without additional server details.')
    text = ' · '.join(parts)
    for secret in private:
        if isinstance(secret, str) and secret:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'Bearer\s+\S+|sk-[\w-]+|eyJ[\w-]+\.[\w-]+\.[\w-]+', '[REDACTED]', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip()[:600]
    title = f'OpenAI HTTP {status}' if status else 'OpenAI'
    if request_id:
        request_id = re.sub(r'[^\w-]', '', str(request_id))[:100]
        text += f' (request: {request_id})'
    return f'{title} — {text}'
