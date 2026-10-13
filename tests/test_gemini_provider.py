import os,sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.build-tools'))
from desktop.translation import Translator
from desktop.gemini import GeminiAuth,GeminiCLI,safe_error,connection_error
from desktop.storage import write_json
from desktop import gemini_api
from urllib.error import HTTPError
from io import BytesIO


class GeminiProviderTests(unittest.TestCase):
    def test_provider_cache_is_separate_and_cache_hit_needs_no_login(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            translator=Translator()
            with patch('desktop.translation.stream_translation',return_value=['OpenAI text']):
                translator.translate(['Hello'],'token','same-model')
            complete=lambda *a,**k:['Gemini text']
            self.assertEqual(translator.translate(['Hello'],None,'same-model',provider='gemini',complete=complete)[0],['Gemini text'])
            self.assertEqual(translator.translate(['Hello'],None,'same-model',provider='gemini')[1],1)

    def test_auth_uses_cli_oauth_and_does_not_store_tokens(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            write_json('settings.json',{'gemini_auth_mode':'enterprise'})
            auth=GeminiAuth()
            session={'models':{'availableModels':[{'modelId':'gemini-test','name':'Gemini test'}]}}
            with patch.object(auth.cli,'start'),patch.object(auth.cli,'new_session',return_value=session),patch.object(auth.cli,'request',return_value={}) as request:
                auth.sign_in();self.assertTrue(auth.connected)
                self.assertEqual(request.call_args.args[0],'authenticate')
                self.assertEqual(request.call_args.args[1],{'methodId':'oauth-personal'})
            saved=json.loads((Path(tmp)/'gemini-connection.json').read_text())
            self.assertNotIn('access_token',saved);self.assertNotIn('refresh_token',saved)
            auth.sign_out();self.assertFalse(auth.connected)

    def test_cli_is_isolated_and_has_no_tool_or_mcp_access(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp,GEMINI_API_KEY='private-test-key'):
            cli=GeminiCLI();env=cli.environment()
            self.assertNotIn('GEMINI_API_KEY',env)
            self.assertEqual(Path(env['GEMINI_CLI_HOME']).resolve(),(Path(tmp)/'gemini-home').resolve())
            config=json.loads(Path(env['GEMINI_CLI_SYSTEM_SETTINGS_PATH']).read_text())
            self.assertEqual(config['tools']['core'],[]);self.assertEqual(config['mcpServers'],{})
            self.assertEqual(env['GEMINI_FORCE_ENCRYPTED_FILE_STORAGE'],'true')

    def test_completion_accepts_only_final_text_for_its_session(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            write_json('settings.json',{'gemini_auth_mode':'enterprise'})
            auth=GeminiAuth();auth.credentials={'active':'gemini-google','accounts':[{'client_id':'gemini-google'}]}
            def request(method,params,**kwargs):
                if method=='session/prompt':
                    auth.cli.notifications=[dict(sessionId='other',update=dict(sessionUpdate='agent_message_chunk',content=dict(type='text',text='bad'))),dict(sessionId='ours',update=dict(sessionUpdate='agent_message_chunk',content=dict(type='text',text='{"translations":["Bonjour"]}')))]
                    return {'stopReason':'end_turn'}
                return {}
            with patch.object(auth.cli,'start'),patch.object(auth.cli,'new_session',return_value={'sessionId':'ours'}),patch.object(auth.cli,'request',side_effect=request):
                self.assertEqual(auth.complete(None,'model',['Hello'],source='en',target='fr'),['Bonjour'])
            self.assertNotIn('secret',safe_error('Bearer secret access_token=secret https://service.test/?code=secret'))

    def test_old_consumer_identity_is_not_a_connected_service(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            write_json('gemini-connection.json',{'signed_in':True,'name':'old@example.invalid'})
            self.assertFalse(GeminiAuth().connected)
            write_json('settings.json',{'gemini_auth_mode':'enterprise'})
            self.assertFalse(GeminiAuth().connected)

    def test_failed_service_verification_never_commits_connected_identity(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            write_json('settings.json',{'gemini_auth_mode':'enterprise'})
            auth=GeminiAuth()
            with patch.object(auth.cli,'start'),patch.object(auth.cli,'request',return_value={}),patch.object(auth.cli,'new_session',side_effect=RuntimeError('Google retired personal access')):
                with self.assertRaises(RuntimeError):auth.sign_in()
            self.assertFalse(auth.connected)
            self.assertFalse(json.loads((Path(tmp)/'gemini-connection.json').read_text())['signed_in'])

    def test_error_keeps_code_assist_words_but_never_secrets(self):
        self.assertEqual(safe_error('Gemini Code Assist for individuals'),'Gemini Code Assist for individuals')
        self.assertNotIn('secret',safe_error('code = secret id_token: secret Bearer secret https://x/?code=secret'))
        self.assertIn('Google AI Studio',connection_error('This client is no longer supported for Gemini Code Assist for individuals.'))

    def test_api_key_is_verified_before_encrypted_storage_and_not_in_metadata(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp,patch.dict(os.environ,RUEVALLEY_DATA_DIR=tmp):
            auth=GeminiAuth();key='fixture-secret-key-0123456789'
            # Stub Windows encryption for deterministic storage boundaries; production uses DPAPI.
            crypt=lambda data,decrypt=False: data[4:] if decrypt else b'ENC:'+data
            with patch('desktop.gemini_api.list_models',return_value=[('gemini-test','Gemini test')]),patch('desktop.gemini.protect',side_effect=crypt) as protect:
                auth.connect_api_key(key);self.assertTrue(auth.connected);self.assertTrue(protect.called)
                self.assertNotIn(key,(Path(tmp)/'gemini-connection.json').read_text())
                self.assertNotIn('access_token',auth.account)
                auth.sign_out();self.assertFalse(auth.connected)
                self.assertNotIn(key,(Path(tmp)/'gemini-api.dat').read_text())
            with patch('desktop.gemini_api.list_models',side_effect=RuntimeError('invalid')):
                with self.assertRaises(RuntimeError):auth.connect_api_key(key)
            self.assertFalse(auth.connected)

    def test_models_are_paginated_and_exclude_non_text_generators(self):
        pages=[{'models':[{'name':'models/gemini-flash','supportedGenerationMethods':['generateContent']},{'name':'models/gemini-image','supportedGenerationMethods':['generateContent']}],'nextPageToken':'next page'},
               {'models':[{'name':'models/gemini-pro','displayName':'Gemini Pro','supportedGenerationMethods':['generateContent']},{'name':'models/embedding','supportedGenerationMethods':['embedContent']}]}]
        with patch('desktop.gemini_api.request',side_effect=pages) as request:
            self.assertEqual(gemini_api.list_models('key'),[('gemini-flash','gemini-flash'),('gemini-pro','Gemini Pro')])
            self.assertIn('pageToken=next+page',request.call_args.args[1])

    def test_api_request_keeps_key_in_header_and_validates_finished_output(self):
        class Response(BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        result={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'do not include thought','thought':True},{'text':'{"translations":["Bonjour"]}'}]}}]}
        with patch('desktop.gemini_api.urlopen',return_value=Response(json.dumps(result).encode())) as open_request:
            self.assertEqual(gemini_api.complete('fixture-secret','gemini-test',['Hello'],source='en',target='fr'),['Bonjour'])
            req=open_request.call_args.args[0]
            self.assertNotIn('fixture-secret',req.full_url)
            self.assertEqual(req.get_header('X-goog-api-key'),'fixture-secret')
            payload=json.loads(req.data);self.assertNotIn('tools',payload)
            self.assertIn('French',payload['systemInstruction']['parts'][0]['text'])
        result['candidates'][0]['finishReason']='MAX_TOKENS'
        with patch('desktop.gemini_api.request',return_value=result):
            with self.assertRaises(gemini_api.GeminiAPIError):gemini_api.complete('key','gemini-test',['Hello'])

    def test_api_quota_and_bad_credentials_have_different_recovery(self):
        error=HTTPError('https://service',429,'quota',{},BytesIO(b'{"error":{"message":"fixture-secret"}}'))
        with patch('desktop.gemini_api.urlopen',side_effect=error):
            with self.assertRaises(gemini_api.GeminiAPIError) as caught:gemini_api.request('fixture-secret','models')
            self.assertIn('quota',str(caught.exception));self.assertFalse(caught.exception.invalid_credentials)
            self.assertNotIn('fixture-secret',str(caught.exception))
        error=HTTPError('https://service',400,'invalid',{},BytesIO(b'{"error":{"details":[{"reason":"API_KEY_INVALID"}]}}'))
        with patch('desktop.gemini_api.urlopen',side_effect=error):
            with self.assertRaises(gemini_api.GeminiAPIError) as caught:gemini_api.request('fixture-secret','models')
            self.assertTrue(caught.exception.invalid_credentials)
