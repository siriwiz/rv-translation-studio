"""Translate through all 18 bundled directions with socket access blocked."""
import json,os,sys,time,socket,re
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'.build-tools')]
target=root/'artifacts/argos-acceptance';target.mkdir(parents=True,exist_ok=True)
os.environ['RUEVALLEY_DATA_DIR']=str(target/'test-data')
import desktop
from desktop.local_translation import LocalTranslator
from desktop.translation import Translator
engine=LocalTranslator();samples={'th':'หุบเขายังจำคุณได้','zh':'这个山谷还记得你。','ja':'この谷はあなたを覚えています。','ko':'이 계곡은 당신을 기억합니다.',
    'fr':'La vallée se souvient de vous.','de':'Das Tal erinnert sich an dich.','es':'El valle te recuerda.','vi':'Thung lũng vẫn nhớ bạn.','ru':'Долина помнит тебя.'}
checks={};results=[]
try:
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Local translation attempted a network connection')):
        for source in engine.catalog['languages']:
            for destination in engine.catalog['languages']:
                assert engine.route(source,destination) or source==destination
        checks['all_90_language_routes']=True
        for code,text in samples.items():
            for source,destination,original in [('en',code,'The valley remembers you.'),(code,'en',text)]:
                start=time.perf_counter();output=engine.complete(None,'argos-balanced-v1',[original],source=source,target=destination)
                assert len(output)==1 and output[0].strip()
                assert len(engine.sessions)<=2
                results.append(dict(source=source,target=destination,input=original,output=output[0],seconds=round(time.perf_counter()-start,3)))
                print(source+' → '+destination+': '+output[0],flush=True)
        checks['all_18_direct_directions']=True
        output=engine.complete(None,'argos-fast-v1',[samples['ja']],source='ja',target='th')
        checks['japanese_to_thai_pivot']=any('\u0e00'<=char<='\u0e7f' for char in output[0])
        checks['session_memory_bounded']=len(engine.sessions)<=2
        translator=Translator();translator.cache={}
        first,hits=translator.translate(['Hello, welcome back.'],None,'argos-balanced-v1',provider='argos',complete=engine.complete)
        cached,hits=translator.translate(['Hello, welcome back.'],None,'argos-balanced-v1',provider='argos')
        checks['cache_hit_without_inference']=hits==1 and first==cached
        auto_samples={'en':'The valley remembers you.',**samples}
        checks['auto_detect_all_ten_languages']=all(engine.detector.detect(text)==code for code,text in auto_samples.items())
        originals=list(auto_samples.values())+['123…']
        auto=engine.complete(None,'argos-balanced-v1',originals,source='auto',target='th')
        explicit=[engine.complete(None,'argos-balanced-v1',[text],source=code,target='th')[0] for code,text in auto_samples.items()]+['123…']
        checks['auto_mixed_batch_matches_explicit_routes']=auto==explicit
        checks['auto_identity_preserves_thai_and_numbers']=auto[1]==samples['th'] and auto[-1]=='123…'
        checks['auto_session_memory_bounded']=len(engine.sessions)<=2
        paragraph="You hungry?What can we get you? We've got those left overs from that Thai Me To The Moon place, the slice of cake from I Like Big Bundts. or the pizza from Pie On Life. Which will it be?"
        for mode in ('argos-fast-v1','argos-balanced-v1','argos-quality-v1'):
            translated=engine.complete(None,mode,[paragraph],source='auto',target='th')[0]
            checks['full_paragraph_'+mode]=all(word in translated for word in ('หิว','เค้ก','พิซซ่า','ไหนดี'))
            results.append(dict(source='auto',mode=mode,input=paragraph,output=translated))
        checks['symbols_do_not_break_quality_mode']='_' in engine.complete(None,'argos-quality-v1',['Continue.\n_\nBack.'],source='auto',target='th')[0]
        bilingual=['こんにちは。Hello, welcome back.','こんにちは Hello, welcome back.','Welcome back.\nこんにちは。']
        mixed=engine.complete(None,'argos-balanced-v1',bilingual,source='auto',target='th')
        checks['mixed_ja_en_same_passage']=all('สวัสดี' in value and 'ต้อนรับ' in value for value in mixed)
        for original,value in zip(bilingual,mixed):results.append(dict(source='auto',input=original,output=value))
        screen=engine.complete_screen(None,'argos-quality-v1',['Hello, welcome back.','X','こんにちは。'],source='auto',target='th')
        checks['screen_partial_keeps_valid_translations']=bool(screen[0]) and screen[1] is None and bool(screen[2])
        for code,text in auto_samples.items():results.append(dict(source='auto',detected=code,target='th',input=text,output=auto[list(auto_samples).index(code)]))
        try:engine.complete(None,'argos-fast-v1',['Hello'],source='ar',target='th')
        except RuntimeError:checks['unsupported_language_explicitly_rejected']=True
    checks['ok']=all(checks.values())
finally:
    engine.stop();(target/'result.json').write_text(json.dumps(dict(checks=checks,samples=results),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(checks));sys.exit(0 if checks.get('ok') else 1)
