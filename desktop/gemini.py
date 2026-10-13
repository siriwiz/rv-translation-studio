"""Gemini API credentials, plus official CLI access for licensed organizations.

OAuth is owned by the CLI. Studio never reads or copies its access/refresh tokens.
"""
import json,os,queue,re,subprocess,threading,time
from pathlib import Path
from .storage import data_dir,resource,read_json,write_json,protect,atomic_write


def safe_error(message,private=()):
    text=str(message)
    for secret in private:
        if secret:text=text.replace(secret,'[redacted]')
    text=re.sub(r'https?://\S+','[service URL]',text)
    text=re.sub(r'(?i)(?:bearer\s+|(?:access_token|refresh_token|id_token|api_key|code|code_verifier)["\']?\s*[:=]\s*["\']?)[^\s,}"\']+','[redacted]',text)
    return text[:500]


def connection_error(message):
    if 'no longer supported' in str(message).lower() or 'migrate to the antigravity' in str(message).lower():
        return ('Google retired Gemini CLI sign-in for personal accounts. In Connection, choose Gemini API key '
                'and create a key in Google AI Studio. Organization sign-in requires a licensed Code Assist Standard/Enterprise account.')
    return 'Gemini: '+safe_error(message)


class GeminiCLI:
    def __init__(self):
        self.process=None;self.pending={};self.sequence=0;self.lock=threading.RLock();self.write_lock=threading.Lock()
        self.notifications=[];self.turns=0

    @property
    def home(self):return data_dir()/'gemini-home'

    @property
    def workspace(self):return self.home/'translation-workspace'

    def environment(self):
        self.workspace.mkdir(parents=True,exist_ok=True)
        settings=self.home/'translation-settings.json'
        settings.write_text(json.dumps(dict(tools=dict(core=[],exclude=['*']),mcpServers={},mcp=dict(allowed=[]),
            hooksConfig=dict(enabled=False),telemetry=dict(enabled=False),privacy=dict(usageStatisticsEnabled=False),
            context=dict(fileName='RV_NO_CONTEXT.md',includeDirectories=[]),advanced=dict(ignoreLocalEnv=True,autoConfigureMemory=False),
            general=dict(enableAutoUpdate=False),experimental=dict(enableAgents=False))),encoding='utf-8')
        env=dict(os.environ)
        for key in ('GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_APPLICATION_CREDENTIALS','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GEMINI_BASE_URL','NODE_OPTIONS','GEMINI_CLI_AUTH_OVERRIDE','GEMINI_SYSTEM_MD'):
            env.pop(key,None)
        env.update(GEMINI_CLI_HOME=str(self.home),GEMINI_CLI_NO_RELAUNCH='true',GEMINI_CLI_SURFACE='rv-translation-studio',
            GEMINI_FORCE_ENCRYPTED_FILE_STORAGE='true',GEMINI_CLI_SYSTEM_SETTINGS_PATH=str(settings),
            GEMINI_CLI_SYSTEM_DEFAULTS_PATH=str(settings),GEMINI_SYSTEM_MD=str(resource('assets/gemini/system.md')),
            NO_COLOR='1',OTEL_SDK_DISABLED='true')
        project=read_json('settings.json',{}).get('gemini_project','').strip()
        env.pop('GOOGLE_CLOUD_PROJECT',None);env.pop('GOOGLE_CLOUD_PROJECT_ID',None)
        if project:env['GOOGLE_CLOUD_PROJECT']=project
        return env

    def start(self):
        if self.process and self.process.poll() is None:return
        node=resource('assets/gemini/runtime/node.exe');cli=resource('assets/gemini/runtime/cli/bundle/gemini.js')
        if not node.is_file() or not cli.is_file():raise RuntimeError('Bundled Gemini CLI runtime is missing. Reinstall the full build.')
        env=self.environment()
        self.process=subprocess.Popen([str(node),str(cli),'--acp','--extensions','none','--approval-mode','default',
            '--admin-policy',str(resource('assets/gemini/translation-only.toml')),'--skip-trust'],
            cwd=self.workspace,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',errors='replace',bufsize=1,creationflags=subprocess.CREATE_NO_WINDOW)
        self.notifications=[];self.turns=0
        threading.Thread(target=self._read,args=(self.process,),daemon=True,name='gemini-acp').start()
        threading.Thread(target=self._discard_errors,args=(self.process,),daemon=True,name='gemini-log').start()
        result=self.request('initialize',dict(protocolVersion=1,clientInfo=dict(name='rv-translation-studio',version='2.8.0'),
            clientCapabilities=dict(fs=dict(readTextFile=False,writeTextFile=False),terminal=False)),timeout=30)
        methods=[method['id'] for method in result.get('authMethods',[])]
        if 'oauth-personal' not in methods:raise RuntimeError('The bundled Gemini CLI does not offer Google account sign-in.')
        return result

    def _discard_errors(self,process):
        # OAuth browser URLs and SDK diagnostics never enter UI/log artifacts.
        for _ in process.stderr:pass

    def _send(self,payload):
        with self.write_lock:
            if not self.process or self.process.poll() is not None:raise RuntimeError('Gemini CLI stopped. Reconnect Google and retry.')
            self.process.stdin.write(json.dumps(payload,ensure_ascii=False)+'\n');self.process.stdin.flush()

    def _read(self,process):
        for line in process.stdout:
            try:message=json.loads(line)
            except ValueError:continue
            if 'method' in message:
                if 'id' in message:
                    if message['method']=='session/request_permission':
                        self._send(dict(jsonrpc='2.0',id=message['id'],result=dict(outcome=dict(outcome='cancelled'))))
                    else:self._send(dict(jsonrpc='2.0',id=message['id'],error=dict(code=-32601,message='Studio does not provide tool access.')))
                elif message['method']=='session/update':self.notifications.append(message.get('params',{}))
            elif 'id' in message:
                waiter=self.pending.get(message['id'])
                if waiter:waiter.put(message)
        for waiter in list(self.pending.values()):waiter.put({'error':{'message':'Gemini CLI stopped. Reconnect and retry.'}})

    def request(self,method,params,timeout=90,cancel=None):
        self.sequence+=1;identifier=self.sequence;waiter=queue.Queue();self.pending[identifier]=waiter
        try:
            self._send(dict(jsonrpc='2.0',id=identifier,method=method,params=params))
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                if cancel and cancel.is_set():self.stop();raise RuntimeError('Google sign-in cancelled.')
                try:message=waiter.get(timeout=.2)
                except queue.Empty:continue
                if 'error' in message:raise RuntimeError(connection_error(message['error'].get('message','Request failed.')))
                return message.get('result') or {}
            self.stop();raise RuntimeError('Gemini timed out. Reconnect Google or retry the request.')
        finally:self.pending.pop(identifier,None)

    def new_session(self):
        return self.request('session/new',dict(cwd=str(self.workspace),mcpServers=[]),timeout=90)

    def stop(self):
        process=self.process;self.process=None
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)


class GeminiAuth:
    def __init__(self):
        self.cli=GeminiCLI();self.cancel=threading.Event();self.lock=threading.RLock()
        self.credentials={'active':None,'accounts':[]};self.reload()

    def reload(self):
        metadata=read_json('gemini-connection.json',{})
        self.api_key=''
        if self.mode=='api':
            try:self.api_key=json.loads(protect((data_dir()/'gemini-api.dat').read_bytes(),decrypt=True).decode()).get('key','')
            except (OSError,ValueError):pass
        transport='gemini-api-v1' if self.mode=='api' else 'gemini-cli-enterprise-v1'
        if metadata.get('signed_in') and metadata.get('transport')==transport and (self.mode!='api' or self.api_key):
            self.credentials={'active':'gemini-google','accounts':[dict(client_id='gemini-google',email=metadata.get('name','Google account'),provider='gemini')]}
        else:self.credentials={'active':None,'accounts':[]}

    @property
    def mode(self):
        mode=read_json('settings.json',{}).get('gemini_auth_mode','api')
        return mode if mode in ('api','enterprise') else 'api'

    def disconnect(self):
        self.cli.stop();write_json('gemini-connection.json',dict(signed_in=False));self.reload()

    def connect_api_key(self,key):
        from .gemini_api import list_models
        key=key.strip()
        if not 16<=len(key)<=256 or any(c.isspace() for c in key):raise ValueError('Enter a valid Gemini API key from Google AI Studio.')
        with self.lock:
            models=list_models(key)
            if not models:raise RuntimeError('This API key has no compatible Gemini text models. Check its project in Google AI Studio.')
            atomic_write(data_dir()/'gemini-api.dat',protect(json.dumps(dict(key=key)).encode()))
            write_json('gemini-connection.json',dict(signed_in=True,name='Google AI Studio · API key',transport='gemini-api-v1'))
            self.reload();return self.account

    @property
    def account(self):return self.credentials['accounts'][0] if self.credentials['accounts'] else None

    @property
    def connected(self):return bool(self.account)

    def select(self,identifier):pass

    def sign_in(self,existing=None,on_url=None):
        if self.mode=='api':raise RuntimeError('Connect a Gemini API key in Connection. Personal Google CLI sign-in has been retired.')
        self.cancel.clear()
        with self.lock:
            self.disconnect()
            try:
                self.cli.start()
                if self.cancel.is_set():self.cli.stop();raise RuntimeError('Google sign-in cancelled.')
                self.cli.request('authenticate',dict(methodId='oauth-personal'),timeout=180,cancel=self.cancel)
                # Identity alone is insufficient: verify the licensed service accepts a session.
                session=self.cli.new_session()
                if not session.get('models',{}).get('availableModels'):raise RuntimeError('No Gemini CLI models are available for this organization account.')
            except Exception:
                self.disconnect();raise
            name='Google account'
            try:
                accounts=json.loads((self.cli.home/'.gemini/google_accounts.json').read_text(encoding='utf-8'))
                if isinstance(accounts.get('active'),str):name=accounts['active']
            except (OSError,ValueError):pass
            write_json('gemini-connection.json',dict(signed_in=True,name=name,transport='gemini-cli-enterprise-v1'))
            self.reload();return self.account

    def models(self):
        if not self.connected:raise RuntimeError('Sign in with Google in Connection first.')
        with self.lock:
            if self.mode=='api':
                from .gemini_api import list_models,GeminiAPIError
                try:return list_models(self.api_key)
                except GeminiAPIError as exc:
                    if exc.invalid_credentials:self.disconnect()
                    raise
            try:self.cli.start();session=self.cli.new_session()
            except RuntimeError as exc:
                if 'retired' in str(exc).lower():self.disconnect()
                raise
            return [(m['modelId'],m['name']) for m in session.get('models',{}).get('availableModels',[])]

    def complete(self,token,model,texts,timeout=90,source='en',target='th'):
        from .translation import translation_instructions,parse_translations
        if not self.connected:raise RuntimeError('Sign in with Google in Connection first.')
        with self.lock:
            if self.mode=='api':
                from .gemini_api import complete,GeminiAPIError
                try:return complete(self.api_key,model,texts,timeout,source,target)
                except GeminiAPIError as exc:
                    if exc.invalid_credentials:self.disconnect()
                    raise
            if self.cli.turns>=20:self.cli.stop()
            self.cli.start();session=self.cli.new_session();session_id=session['sessionId']
            self.cli.request('session/set_model',dict(sessionId=session_id,modelId=model))
            self.cli.notifications=[]
            prompt=translation_instructions(source,target)+'\nReturn JSON only.\n'+json.dumps(dict(texts=texts),ensure_ascii=False)
            result=self.cli.request('session/prompt',dict(sessionId=session_id,prompt=[dict(type='text',text=prompt)]),timeout=timeout)
            self.cli.turns+=1
            if result.get('stopReason')!='end_turn':raise RuntimeError('Gemini did not complete the translation. Retry; incomplete output was not saved.')
            output=[]
            for message in self.cli.notifications:
                update=message.get('update',{})
                if message.get('sessionId')==session_id and update.get('sessionUpdate')=='agent_message_chunk' and update.get('content',{}).get('type')=='text':output.append(update['content']['text'])
            return parse_translations(''.join(output),len(texts))

    def sign_out(self):
        if self.mode=='api':atomic_write(data_dir()/'gemini-api.dat',protect(b'{"key":""}'))
        self.disconnect();return True
