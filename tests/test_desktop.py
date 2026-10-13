import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.build-tools'))
from desktop.auth import check_callback, ChatGPTAuth
from desktop.storage import save_credentials, load_credentials
from desktop.translation import parse_translations, stream_translation, recognize


class Tests(unittest.TestCase):
    def test_callback_rejects_csrf_and_client_substitution(self):
        with self.assertRaises(ValueError):
            check_callback({'state':['bad'], 'code':['abc'], 'client_id':['oaiapp_x']}, 'good')
        with self.assertRaises(ValueError):
            check_callback({'state':['good'], 'code':['abc'], 'client_id':['oaiapp_bad']}, 'good', 'oaiapp_good')
        with self.assertRaises(ValueError):
            check_callback({'state':['good'], 'code':['abc']}, 'good')
        self.assertEqual(check_callback({'state':['good'], 'code':['abc'], 'client_id':['oaiapp_x']}, 'good'), ('oaiapp_x','abc'))

    def test_cancel_callback(self):
        with self.assertRaises(RuntimeError):
            check_callback({'state':['good'], 'error':['access_denied']}, 'good')

    def test_dpapi_roundtrip_no_plaintext(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp, patch.dict(os.environ, RUEVALLEY_DATA_DIR=tmp):
            value = {'accounts':[{'access_token':'secret-test-token'}], 'active':None}
            save_credentials(value)
            self.assertEqual(load_credentials(), value)
            self.assertNotIn(b'secret-test-token', (Path(tmp)/'accounts.dat').read_bytes())

    def test_translation_alignment(self):
        self.assertEqual(parse_translations('{"translations":["สวัสดี","ลาก่อน"]}', 2), ['สวัสดี','ลาก่อน'])
        with self.assertRaises(RuntimeError):
            parse_translations('{"translations":["สวัสดี"]}', 2)

    def test_stream_requires_terminal_success(self):
        import io
        stream = b'data: {"type":"response.output_text.delta","delta":"{\\"translations\\":[\\"Hello\\"]}"}\n\n'
        with patch('desktop.translation.urlopen', return_value=io.BytesIO(stream)):
            with self.assertRaises(RuntimeError):
                stream_translation('fake', 'model', ['Hello'])
        with patch('desktop.translation.urlopen', return_value=io.BytesIO(stream + b'data: {"type":"response.completed"}\n\n')):
            self.assertEqual(stream_translation('fake', 'model', ['Hello']), ['Hello'])

    def test_direct_route_request_uses_message_list(self):
        import io
        import json
        stream = b'data: {"type":"response.output_text.delta","delta":"{\\"translations\\":[\\"Hello\\"]}"}\n\ndata: {"type":"response.completed"}\n\n'
        with patch('desktop.translation.urlopen', return_value=io.BytesIO(stream)) as request:
            stream_translation('fake', 'model', ['Hello'])
        payload = json.loads(request.call_args.args[0].data)
        self.assertIsInstance(payload['input'], list)
        self.assertEqual(payload['input'][0]['role'], 'user')
        self.assertEqual(json.loads(payload['input'][0]['content']), ['Hello'])
        self.assertFalse(payload['store'])
        self.assertTrue(payload['stream'])

    def test_http_detail_error_is_preserved_without_token(self):
        import io
        from urllib.error import HTTPError
        from email.message import Message
        headers = Message()
        headers['x-request-id'] = 'req_test'
        error = HTTPError('https://api.openai.com/v1/responses', 400, 'Bad Request', headers, io.BytesIO(b'{"detail":"Input must be a list; fake-secret"}'))
        with patch('desktop.translation.urlopen', side_effect=error):
            with self.assertRaises(RuntimeError) as caught:
                stream_translation('fake-secret', 'model', ['Hello'])
        self.assertIn('Input must be a list', str(caught.exception))
        self.assertIn('req_test', str(caught.exception))
        self.assertNotIn('fake-secret', str(caught.exception))

    def test_structured_error_keeps_parameter(self):
        from desktop.errors import openai_error
        text = openai_error(400, {'error':{'type':'invalid_request_error','code':'unsupported_parameter','param':'input','message':'Input must be a list'}})
        self.assertIn('unsupported_parameter', text)
        self.assertIn('input', text)
        self.assertIn('Input must be a list', text)

    def test_refresh_rotates_atomically_and_checks_grant(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp, patch.dict(os.environ, RUEVALLEY_DATA_DIR=tmp):
            auth = ChatGPTAuth()
            auth.credentials = {'active':'oaiapp_x','accounts':[dict(client_id='oaiapp_x', access_token='old', refresh_token='old_refresh', expires_at=0, scopes=['chatgpt.tokens.use.direct'])]}
            with patch('desktop.auth.request_json', return_value=dict(access_token='new', refresh_token='new_refresh', expires_in=3600, scope='chatgpt.tokens.use.direct')):
                self.assertEqual(auth.access_token(), 'new')
            self.assertEqual(load_credentials()['accounts'][0]['refresh_token'], 'new_refresh')

    def test_oauth_loopback_pkce_and_signed_identity(self):
        import threading
        import time
        from types import SimpleNamespace
        from urllib.parse import urlsplit, parse_qs, urlencode
        from urllib.request import urlopen
        from cryptography.hazmat.primitives.asymmetric import rsa
        import jwt
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pending = {}
        browser_threads = []
        def browser(url):
            params = parse_qs(urlsplit(url).query)
            pending.update({k:v[0] for k,v in params.items()})
            self.assertEqual(pending['client_id'], 'dynamic_agent_client')
            self.assertEqual(pending['code_challenge_method'], 'S256')
            def callback():
                target = pending['redirect_uri'] + '?' + urlencode(dict(code='test-code',state=pending['state'],client_id='oaiapp_test'))
                with urlopen(target, timeout=5) as response:
                    self.assertEqual(response.status, 200)
            thread = threading.Thread(target=callback)
            thread.start()
            browser_threads.append(thread)
            return True
        def api(url, data=None, **kwargs):
            if url.endswith('openid-configuration'):
                return {'jwks_uri':'https://auth.openai.com/.well-known/jwks.json'}
            import hashlib, base64
            self.assertEqual(base64.urlsafe_b64encode(hashlib.sha256(data['code_verifier'].encode()).digest()).decode().rstrip('='), pending['code_challenge'])
            self.assertEqual(data['redirect_uri'], pending['redirect_uri'])
            self.assertEqual(data['client_id'], 'oaiapp_test')
            token = jwt.encode(dict(iss='https://auth.openai.com',aud='oaiapp_test',sub='user-test',email='test@example.invalid',exp=time.time()+3600,nonce=pending['nonce']), private, algorithm='RS256')
            return dict(id_token=token, access_token='test-access', refresh_token='test-refresh',scope='chatgpt.tokens.use.direct',expires_in=3600)
        with tempfile.TemporaryDirectory(dir='.') as tmp, patch.dict(os.environ, RUEVALLEY_DATA_DIR=tmp):
            auth = ChatGPTAuth()
            with patch('desktop.auth.webbrowser.open', side_effect=browser), patch('desktop.auth.request_json', side_effect=api), patch('desktop.auth.jwt.PyJWKClient') as jwks:
                jwks.return_value.get_signing_key_from_jwt.return_value = SimpleNamespace(key=private.public_key())
                account = auth.sign_in()
            for thread in browser_threads:
                thread.join(timeout=5)
            self.assertEqual(account['subject'], 'user-test')
            self.assertEqual(load_credentials()['active'], 'oaiapp_test')

    def test_windows_ocr_real_image(self):
        from PyQt6.QtGui import QImage, QPainter, QFont, QColor
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            path = Path(tmp).resolve()/'ocr.png'
            image = QImage(900, 180, QImage.Format.Format_RGB32)
            image.fill(QColor('white'))
            p = QPainter(image)
            p.setPen(QColor('black'))
            p.setFont(QFont('Arial', 34))
            p.drawText(25, 95, 'The valley remembers you.')
            p.end()
            image.save(str(path))
            lines = recognize(path)
            self.assertTrue(any('valley' in l['text'].lower() for l in lines), lines)
            self.assertTrue(all(l['w'] > 0 and l['h'] > 0 for l in lines))
            self.assertTrue(all(isinstance(w, dict) for l in lines for w in l['words']))

    def test_inpaint_removes_text_and_preserves_patch_border(self):
        import numpy as np
        from desktop.blend import make_patch, image_to_bgr
        image = np.full((120, 350, 3), 180, dtype=np.uint8)
        image[45:65, 60:140] = 20
        line = dict(x=60,y=45,w=80,h=20,words=[dict(x=60,y=45,w=80,h=20)])
        patch, rect = make_patch(image, line)
        out = image_to_bgr(patch)
        self.assertGreater(out[12:28,12:88].mean(), 150)
        np.testing.assert_array_equal(out[0], image[int(rect.y()),int(rect.x()):int(rect.right())])
        self.assertEqual(patch.width(), int(rect.width()))

    def test_physical_key_fallback_release_and_dedup(self):
        from desktop.hotkeys import GlobalHotkeys
        bridge = GlobalHotkeys()
        fired = []
        bridge.translate.connect(lambda: fired.append('f1'))
        with patch('desktop.hotkeys.ctypes.windll.user32.GetAsyncKeyState', side_effect=[0x8000,0,0,0]):
            bridge.poll()
            bridge.poll()
        bridge.emit_key(0x70)
        self.assertEqual(fired, ['f1'])


if __name__ == '__main__':
    unittest.main()
