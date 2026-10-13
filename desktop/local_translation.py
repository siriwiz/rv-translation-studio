"""Offline Argos model inference; no server, credentials or runtime downloads.

Uses Argos' tokenizer and packaged CTranslate2 models directly. Input passages
are reconstructed by Studio, then split with offline rules before inference.
Only two CPU model sessions are retained; no Stanza/PyTorch is needed.
"""
import json
import threading
import time
from collections import OrderedDict,deque
from functools import cached_property
from .storage import resource
from .language_detection import LocalLanguageDetector
from .sentence_boundaries import split_sentences,join_sentences,split_auto_sentences

MODES={'argos-fast-v1':1,'argos-balanced-v1':2,'argos-quality-v1':4}


class LocalTranslator:
    def __init__(self):
        self.cancel=threading.Event();self.lock=threading.RLock();self.sessions=OrderedDict()
        self.detector=LocalLanguageDetector()
        self.credentials={'active':'argos-local','accounts':[dict(client_id='argos-local',email='Bundled offline models')]}

    @property
    def root(self):return resource('assets/argos')

    @cached_property
    def catalog(self):
        try:return json.loads((self.root/'manifest.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):return {'languages':{},'models':[]}

    @property
    def connected(self):
        return bool(self.catalog['models']) and all((self.root/m['directory']/'model/model.bin').is_file() for m in self.catalog['models'])

    @property
    def account(self):return self.credentials['accounts'][0] if self.connected else None

    def select(self,identifier):pass

    def models(self):
        if not self.connected:raise RuntimeError('Bundled Argos models are missing. Reinstall the full offline build.')
        return [('argos-balanced-v1','Argos Local · Balanced'),('argos-fast-v1','Argos Local · Fast'),('argos-quality-v1','Argos Local · Quality')]

    def validate_pair(self,source,target):
        # Auto has no route until text has been recognized. Validate the target
        # here so it remains usable in Studio before any capture exists.
        self.route(target,target) if source=='auto' else self.route(source,target)

    def route(self,source,target):
        if source.startswith('zh') and any(part in source for part in ('Hant','TW','HK','MO')):source='zt'
        if target.startswith('zh') and any(part in target for part in ('Hant','TW','HK','MO')):target='zt'
        source=source.split('-')[0];target=target.split('-')[0]
        # Argos names traditional Chinese "zt" rather than zh-Hant.
        supported=self.catalog['languages']
        if source not in supported or target not in supported:
            raise RuntimeError('Argos Local supports '+', '.join(supported.values())+'. Choose Auto detect or a supported source and target in Studio; use a cloud provider for other languages.')
        if source==target:return []
        graph={}
        for model in self.catalog['models']:graph.setdefault(model['source'],[]).append(model)
        search=deque([(source,[])]);seen={source}
        while search:
            node,path=search.popleft()
            for model in graph.get(node,[]):
                destination=model['target'];next_path=path+[model]
                if destination==target:return next_path
                if destination not in seen:seen.add(destination);search.append((destination,next_path))
        raise RuntimeError('No bundled Argos route exists for this language pair.')

    def _session(self,model):
        directory=model['directory']
        if directory in self.sessions:
            self.sessions.move_to_end(directory);return self.sessions[directory]
        import ctranslate2
        from argostranslate.tokenizer import SentencePieceTokenizer,BPETokenizer
        path=self.root/directory
        tokenizer=(SentencePieceTokenizer(path/'sentencepiece.model') if (path/'sentencepiece.model').exists()
                   else BPETokenizer(path/'bpe.model',model['source'],model['target']))
        # Evict before loading another model so pivoting cannot grow memory unbounded.
        while len(self.sessions)>=2:
            _,(old,_,_)=self.sessions.popitem(last=False);old.unload_model()
        translator=ctranslate2.Translator(str(path/'model'),device='cpu',compute_type='int8',inter_threads=1,intra_threads=2)
        metadata=json.loads((path/'metadata.json').read_text(encoding='utf-8'))
        session=(translator,tokenizer,metadata.get('target_prefix',''))
        self.sessions[directory]=session;return session

    def complete_screen(self,*args,**kwargs):
        return self.complete(*args,**kwargs,allow_partial=True)

    def complete(self,token,model,texts,timeout=90,source='en',target='th',allow_partial=False):
        if model not in MODES:raise ValueError('Choose an available Argos Local mode.')
        if not texts or not all(isinstance(text,str) and text.strip() for text in texts):raise ValueError('Enter nonempty text to translate.')
        self.validate_pair(source,target);deadline=time.monotonic()+timeout
        with self.lock:
            passages=[split_auto_sentences(text) if source=='auto' else [text] for text in texts]
            units=[part for passage in passages for part in passage]
            groups=OrderedDict();output=list(units)
            for index,text in enumerate(units):
                try:detected=self.detector.detect(text) if source=='auto' else source
                except RuntimeError:
                    if not allow_partial:raise
                    output[index]=None;continue
                if detected is not None:groups.setdefault(detected,[]).append(index)
            for detected,indices in groups.items():
                options={'allow_partial':True} if allow_partial else {}
                values=self._translate(model,[units[i] for i in indices],self.route(detected,target),deadline,**options)
                for index,value in zip(indices,values):output[index]=value
            if time.monotonic()>deadline:raise RuntimeError('Local translation timed out. Output was not saved; try Fast mode.')
            combined=[];offset=0
            for original,passage in zip(texts,passages):
                values=output[offset:offset+len(passage)];offset+=len(passage)
                combined.append(None if any(value is None for value in values) else original if values==passage else join_sentences(values,target))
            return combined

    def _translate(self,model,texts,route,deadline,allow_partial=False):
        output=list(texts)
        for step in route:
            if time.monotonic()>=deadline:raise RuntimeError('Local translation timed out. Use Fast mode or shorter passages.')
            translator,tokenizer,prefix=self._session(step)
            active=[i for i,text in enumerate(output) if text is not None]
            if not active:break
            sentences=[split_sentences(output[i],step['source']) for i in active]
            flat=[sentence for passage in sentences for sentence in passage]
            translated=self._sentence_batch(translator,tokenizer,prefix,model,flat,deadline,allow_partial)
            offset=0
            for index,passage in zip(active,sentences):
                count=len(passage)
                values=translated[offset:offset+count]
                output[index]=join_sentences(values,step['target']) if all(value is not None for value in values) else None
                offset+=count
        if time.monotonic()>deadline:raise RuntimeError('Local translation timed out. Output was not saved; try Fast mode.')
        return output

    def _sentence_batch(self,translator,tokenizer,prefix,model,texts,deadline,allow_partial):
        # HUD counters, punctuation and OCR separators have no text to translate.
        # Sending them to a sentence model can produce EOS/empty output.
        translated=list(texts);pending=[]
        for index,text in enumerate(texts):
            if not any(char.isalpha() for char in text):continue
            tokens=tokenizer.encode(text)
            if len(tokens)>512:
                if not allow_partial:raise RuntimeError('A sentence exceeds the local 512-token limit. Split it into shorter sentences or use a cloud provider; text was not truncated.')
                translated[index]=None;continue
            translated[index]=None
            if tokens:pending.append((index,tokens))

        def infer(batch,beam):
            if time.monotonic()>=deadline:raise RuntimeError('Local translation timed out. Use Fast mode or a smaller capture region.')
            return translator.translate_batch([tokens for _,tokens in batch],target_prefix=[[prefix]]*len(batch) if prefix else None,
                beam_size=beam,num_hypotheses=1,replace_unknowns=True,max_batch_size=8,
                max_input_length=0,max_decoding_length=1024,length_penalty=.2)

        def decode(result):
            if not getattr(result,'hypotheses',None):return None
            pieces=result.hypotheses[0]
            if len(pieces)>=1024:return None
            value=tokenizer.decode(pieces)
            if prefix and value.startswith(prefix):value=value[len(prefix):]
            return value.strip() or None

        for start in range(0,len(pending),8):
            batch=pending[start:start+8];results=infer(batch,MODES[model])
            # A wrong count has no safe index mapping. Retry each input alone.
            if len(results)==len(batch):
                for (index,_),result in zip(batch,results):translated[index]=decode(result)
            for item in batch:
                index=item[0]
                if translated[index] is not None:continue
                retried=infer([item],4 if MODES[model]!=4 else 2)
                if len(retried)==1:translated[index]=decode(retried[0])
        if not allow_partial and any(value is None for value in translated):
            raise RuntimeError('Local translation returned incomplete text after retry. Choose another local mode or a smaller capture region.')
        return translated

    def sign_in(self,*args,**kwargs):return self.account
    def sign_out(self):return False

    def stop(self):
        with self.lock:
            for translator,_,_ in self.sessions.values():translator.unload_model()
            self.sessions.clear()
