"""Official Sign in with ChatGPT public-client OAuth + PKCE."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
import uuid
import webbrowser
import jwt
from .storage import load_credentials, save_credentials, read_json, write_json
from .errors import openai_error

AUTH = 'https://auth.openai.com'
RESOURCE = 'https://api.openai.com/v1'
SCOPES = 'openid profile email offline_access resource.invoke chatgpt.tokens.use.direct'


def request_json(url, data=None, token=None, form=False):
    headers = {'Accept': 'application/json', 'User-Agent': 'RueValleyTranslator/2.0'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = None
    if data is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        body = (urlencode(data) if form else json.dumps(data)).encode()
    try:
        with urlopen(Request(url, body, headers), timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        private = [token]
        if isinstance(data, dict):
            private.extend(data.get(k) for k in ('refresh_token', 'access_token', 'id_token', 'token', 'code', 'code_verifier'))
        raise RuntimeError(openai_error(exc.code, exc.read(), exc.headers.get('x-request-id'), private=private)) from None
    except (URLError, TimeoutError):
        raise RuntimeError('Unable to connect to OpenAI. Check your internet connection and retry.') from None


def check_callback(query, state, prior_id=None):
    if not secrets.compare_digest(query.get('state', [''])[0], state):
        raise ValueError('OAuth state mismatch')
    if query.get('error'):
        raise RuntimeError('Sign-in was cancelled or plan usage was not authorized.')
    client_id = query.get('client_id', [prior_id or ''])[0]
    if not client_id or client_id == 'dynamic_agent_client':
        raise ValueError('OpenAI did not issue a client ID')
    if prior_id and client_id != prior_id:
        raise ValueError('OAuth client ID mismatch')
    code = query.get('code', [''])[0]
    if not code:
        raise ValueError('OAuth authorization code missing')
    return client_id, code


class ChatGPTAuth:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.credentials = load_credentials()
        settings = read_json('host.json', {})
        self.host_id = settings.get('id') or 'urn:uuid:' + str(uuid.uuid4())
        write_json('host.json', {'id': self.host_id})

    @property
    def account(self):
        return next((a for a in self.credentials['accounts'] if a['client_id'] == self.credentials.get('active')), None)

    def save(self):
        save_credentials(self.credentials)

    def select(self, client_id):
        with self.lock:
            self.credentials['active'] = client_id
            self.save()

    def sign_in(self, existing=None, on_url=None):
        self.cancel.clear()
        state, nonce, verifier = (secrets.token_urlsafe(40) for _ in range(3))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
        result = {}

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if urlsplit(self.path).path != '/auth/callback':
                    self.send_error(404)
                    return
                query = parse_qs(urlsplit(self.path).query)
                try:
                    client, code = check_callback(query, state, existing['client_id'] if existing else None)
                    result.update(client_id=client, code=code)
                    message = 'Authorization received. You can return to Rue Valley Translator.'
                    status = 200
                except ValueError:
                    self.send_error(400, 'Invalid OAuth callback')
                    return
                except RuntimeError as exc:
                    result['error'] = str(exc)
                    status, message = 400, 'Sign-in was cancelled. Return to the app to try again.'
                body = ('<!doctype html><title>Rue Valley Translator</title><body style="background:#101010;color:white;font:20px system-ui;padding:80px"><h1>Rue Valley Translator</h1><p>' + message + '</p></body>').encode()
                self.send_response(status)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with HTTPServer(('127.0.0.1', 0), Handler) as server:
            server.timeout = 0.5
            redirect = f'http://127.0.0.1:{server.server_port}/auth/callback'
            params = dict(client_id=existing['client_id'] if existing else 'dynamic_agent_client',
                          ext_agent_host_id=self.host_id, response_type='code', redirect_uri=redirect,
                          scope=SCOPES, resource=RESOURCE, state=state, nonce=nonce,
                          code_challenge_method='S256', code_challenge=challenge)
            if existing:
                if existing.get('id_token'):
                    params['id_token_hint'] = existing['id_token']
                elif existing.get('email'):
                    params['login_hint'] = existing['email']
            else:
                params['agent_name_hint'] = 'Rue Valley Translator'
            url = AUTH + '/api/accounts/authorize?' + urlencode(params)
            if on_url:
                on_url(url)
            webbrowser.open(url)
            deadline = time.monotonic() + 180
            while not result and time.monotonic() < deadline and not self.cancel.is_set():
                server.handle_request()
        if self.cancel.is_set():
            raise RuntimeError('Sign-in cancelled')
        if not result:
            raise RuntimeError('Sign-in timed out. Please try again.')
        if result.get('error'):
            raise RuntimeError(result['error'])
        tokens = request_json(AUTH + '/api/accounts/oauth/token', dict(
            grant_type='authorization_code', client_id=result['client_id'], code=result['code'],
            code_verifier=verifier, redirect_uri=redirect, resource=RESOURCE), form=True)
        metadata = request_json(AUTH + '/.well-known/openid-configuration')
        jwks_url = metadata['jwks_uri']
        if urlsplit(jwks_url).scheme != 'https' or urlsplit(jwks_url).hostname != 'auth.openai.com':
            raise RuntimeError('Invalid OpenAI identity configuration')
        signing_key = jwt.PyJWKClient(jwks_url, timeout=20).get_signing_key_from_jwt(tokens['id_token'])
        claims = jwt.decode(tokens['id_token'], signing_key.key, algorithms=['RS256'],
                            audience=result['client_id'], issuer=AUTH,
                            options={'require': ['exp', 'iss', 'aud', 'sub', 'nonce']})
        if not secrets.compare_digest(str(claims['nonce']), nonce):
            raise RuntimeError('OpenAI identity nonce mismatch')
        if existing and claims['sub'] != existing['subject']:
            raise RuntimeError('The signed-in account does not match the selected account.')
        account = dict(tokens, client_id=result['client_id'], subject=claims['sub'],
                       email=claims.get('email', 'ChatGPT account'), expires_at=time.time() + tokens.get('expires_in', 3600),
                       scopes=tokens.get('scope', '').split())
        with self.lock:
            self.credentials['accounts'] = [a for a in self.credentials['accounts'] if a['client_id'] != account['client_id']] + [account]
            self.credentials['active'] = account['client_id']
            self.save()
        return account

    def access_token(self):
        with self.lock:
            account = self.account
            if not account or not account.get('refresh_token') and not account.get('access_token'):
                raise RuntimeError('Choose Continue with ChatGPT before translating.')
            if 'chatgpt.tokens.use.direct' not in account.get('scopes', []):
                raise RuntimeError('Plan usage is not authorized. Please sign in again.')
            if account.get('expires_at', 0) < time.time() + 60:
                if not account.get('refresh_token'):
                    raise RuntimeError('Your session has expired. Please sign in again.')
                tokens = request_json(AUTH + '/api/accounts/oauth/token', dict(
                    grant_type='refresh_token', client_id=account['client_id'],
                    refresh_token=account['refresh_token'], resource=RESOURCE), form=True)
                account.update(tokens)
                account['expires_at'] = time.time() + tokens.get('expires_in', 3600)
                if 'scope' in tokens:
                    account['scopes'] = tokens['scope'].split()
                self.save()
                if 'chatgpt.tokens.use.direct' not in account['scopes']:
                    raise RuntimeError('Plan access was revoked. Please sign in again.')
            return account['access_token']

    def models(self):
        result = request_json(RESOURCE + '/models', token=self.access_token())
        return [(m['slug'], m.get('display_name', m['slug'])) for m in result.get('models', []) if m.get('visibility') == 'list']

    def sign_out(self):
        with self.lock:
            account = self.account
            if not account:
                return True
            revoked = True
            try:
                if account.get('refresh_token'):
                    meta = request_json(AUTH + '/.well-known/openid-configuration')
                    endpoint = meta['revocation_endpoint']
                    if urlsplit(endpoint).scheme != 'https' or urlsplit(endpoint).hostname != 'auth.openai.com':
                        raise RuntimeError('Invalid revocation endpoint')
                    request_json(endpoint, dict(token=account['refresh_token'], token_type_hint='refresh_token', client_id=account['client_id']), form=True)
            except Exception:
                revoked = False
            for field in ('access_token', 'refresh_token', 'id_token'):
                account.pop(field, None)
            account['expires_at'] = 0
            self.save()
            return revoked
