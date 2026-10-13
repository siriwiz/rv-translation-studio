"""Gemini's public API: text only, API key in a header, never in URLs."""
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .translation import translation_instructions, parse_translations

API = 'https://generativelanguage.googleapis.com/v1beta/'


class GeminiAPIError(RuntimeError):
    def __init__(self, message, invalid_credentials=False):
        super().__init__(message)
        self.invalid_credentials = invalid_credentials


def request(key, path, body=None, timeout=30):
    from .gemini import safe_error
    req = Request(API + path, None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8'),
                  {'x-goog-api-key': key, 'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        try: detail = json.loads(exc.read()).get('error', {})
        except (ValueError, AttributeError): detail = {}
        if not isinstance(detail,dict):detail={}
        # Never include the raw request, key, server body or URL in diagnostics.
        invalid = exc.code == 401 or any(item.get('reason') in ('API_KEY_INVALID', 'API_KEY_EXPIRED')
                       for item in detail.get('details', []) if isinstance(item, dict))
        if invalid: message = 'The Gemini API key is invalid or expired. Connect a new key in Connection.'
        elif exc.code == 403: message = 'Gemini API access denied. Check key restrictions and project permissions in Google AI Studio.'
        elif exc.code == 429: message = 'Gemini API quota reached. Check your API limits in Google AI Studio or retry later.'
        elif exc.code >= 500: message = 'Gemini API is temporarily unavailable. Please retry.'
        else: message = 'Gemini API HTTP ' + str(exc.code) + ': ' + safe_error(detail.get('message', 'Request rejected.'), private=(key,))
        raise GeminiAPIError(message, invalid) from None
    except (URLError, TimeoutError):
        raise GeminiAPIError('Unable to reach Gemini API. Check your connection and retry.') from None


def list_models(key):
    models = {}; token = ''; seen = set()
    while True:
        query = urlencode(dict(pageSize=100, **({'pageToken': token} if token else {})))
        data = request(key, 'models?' + query)
        for model in data.get('models', []):
            name = model.get('name', '').removeprefix('models/')
            # Image/audio-only generators and embedding models cannot localize dialogue.
            if ('generateContent' in model.get('supportedGenerationMethods', []) and
                    name.startswith('gemini-') and not any(word in name for word in ('image', 'tts', 'audio', 'robotics', 'computer-use'))):
                models[name] = model.get('displayName') or name
        token = data.get('nextPageToken', '')
        if not token: break
        if token in seen: raise GeminiAPIError('Gemini returned a repeated model page. Please retry.')
        seen.add(token)
    return list(models.items())


def complete(key, model, texts, timeout=90, source='en', target='th'):
    if not re.fullmatch(r'gemini-[A-Za-z0-9._-]+', model):
        raise ValueError('Choose an available Gemini API text model.')
    body = dict(systemInstruction=dict(parts=[dict(text=translation_instructions(source, target))]),
                contents=[dict(role='user', parts=[dict(text=json.dumps(texts, ensure_ascii=False))])],
                generationConfig=dict(responseMimeType='application/json', responseSchema=dict(type='OBJECT',
                    properties=dict(translations=dict(type='ARRAY', items=dict(type='STRING'))), required=['translations'])))
    result = request(key, 'models/' + model + ':generateContent', body, timeout)
    candidates = result.get('candidates', [])
    if not candidates or candidates[0].get('finishReason') != 'STOP':
        raise GeminiAPIError('Gemini did not complete the translation. Retry; incomplete output was not saved.')
    parts = candidates[0].get('content', {}).get('parts', [])
    return parse_translations(''.join(p.get('text', '') for p in parts if not p.get('thought')), len(texts))
