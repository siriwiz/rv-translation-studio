"""Repeatable RapidOCR -> translation -> blended overlay benchmark.

Loads deployed 2.9.2 translation modules from its PyInstaller build archive.
Only public generated fixtures are sent to OpenAI, with --live-openai opt-in.
User translation caches, settings and executable entry points are not modified.
"""
import argparse,copy,csv,hashlib,importlib,json,os,platform,re,statistics,subprocess,sys,time,types
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.build-tools')]
import desktop
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage,QColor,QPainter,QFont,QFontMetrics,QFontDatabase
from PyQt6.QtCore import QPointF
from desktop.rapid_ocr import recognize_rapid
from desktop.blend import image_to_bgr,make_patch,make_patches
from desktop.glyphs import refine_rapid_regions
from desktop.colors import sample_text_color
from desktop.paragraphs import group_dialogue
from desktop.text_layout import paint_translation
from desktop.storage import read_json

CASES={
    'short':('Short sentence',['Are you ready to leave?']),
    'long_sentence':('Long single sentence',[
        'Before we leave the valley and return to the old station near the river, please check that everyone has enough food and water, collect the maps from the table beside the broken radio, and tell the people waiting outside that we will travel together through the forest because the northern road is flooded and the bridge will not be safe until tomorrow morning.']),
    'paragraph':('Long paragraph',[
        "You hungry? What can we get you? We've got those leftovers from that Thai Me To The Moon place, the slice of cake from I Like Big Bundts, or the pizza from Pie On Life. Which will it be?",
        'After dinner we should return to the old station before the storm arrives. I left a notebook on the wooden table beside the broken radio, and there might be a map inside it. Please bring a warm coat and enough water for the walk through the forest. If the bridge is still closed, we can follow the narrow path along the river instead. We should stay together and wait for the others before crossing the valley.']),
    'screen_batch':('Screen batch / 10 text rows',[
        'The valley remembers everyone who comes home.',
        'We should return before the storm arrives.',
        'Please bring the map and a warm coat.',
        'Did you leave the notebook at the station?',
        'There is a small boat beside the river.',
        'I will wait here until everyone is ready.',
        'The northern road is closed until tomorrow.',
        'Can you hear the music from the old radio?',
        'We have enough food for another two days.',
        'Let us cross the bridge together before sunset.']),
}


def summary(values):
    values=list(values)
    if not values:return None
    return dict(n=len(values),median=statistics.median(values),minimum=min(values),maximum=max(values),mean=statistics.mean(values),stdev=statistics.stdev(values) if len(values)>1 else 0.)


def legacy_modules():
    from PyInstaller.archive.readers import ZlibArchiveReader
    path=ROOT/'build/RVTranslationStudio-2.9.2/PYZ-00.pyz'
    if not path.is_file():raise RuntimeError('The deployed 2.9.2 build archive is required for an exact translation baseline.')
    archive=ZlibArchiveReader(str(path));package=types.ModuleType('rv_bench_292');package.__path__=[str(ROOT/'desktop')]
    sys.modules[package.__name__]=package
    for name in ('storage','languages','auth','errors'):
        sys.modules[package.__name__+'.'+name]=importlib.import_module('desktop.'+name)
    modules={}
    for name in ('sentence_boundaries','language_detection','local_translation','translation'):
        module=types.ModuleType(package.__name__+'.'+name);module.__package__=package.__name__
        module.__file__=str(ROOT/'desktop'/f'{name}.py');sys.modules[module.__name__]=module
        exec(archive.extract('desktop.'+name),module.__dict__);modules[name]=module
    return modules,dict(version='2.9.2',archive=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def wrap(text,metrics,width):
    lines=[];line=''
    for word in text.split():
        candidate=(line+' '+word).strip()
        if line and metrics.horizontalAdvance(candidate)>width:lines.append(line);line=word
        else:line=candidate
    if line:lines.append(line)
    return lines


def fixtures(out):
    images={};folder=out/'fixtures';folder.mkdir(exist_ok=True)
    for key,(label,paragraphs) in CASES.items():
        width,height=(1920,1080) if key=='screen_batch' else (1600,900)
        image=QImage(width,height,QImage.Format.Format_RGB32);image.fill(QColor('#202d2b'))
        painter=QPainter(image);font=QFont('Arial');font.setPixelSize(30);painter.setFont(font);painter.setPen(QColor('#e7bc66'))
        metrics=QFontMetrics(font);y=62;line_count=0
        for paragraph in paragraphs:
            for text in wrap(paragraph,metrics,width-100):
                painter.drawText(45,y,text);y+=40;line_count+=1
            y+=15
        painter.end()
        if y>height-20:raise RuntimeError('Fixture text would be clipped: '+key)
        path=folder/(key+'.png');image.save(str(path))
        images[key]=dict(label=label,path=str(path),width=width,height=height,source_text=' '.join(paragraphs),source_words=len(' '.join(paragraphs).split()),painted_lines=line_count)
    return images


def words(text):return re.findall(r"[a-z0-9]+(?:'[a-z]+)?",text.lower())


def wer(expected,actual):
    a,b=words(expected),words(actual);row=list(range(len(b)+1))
    for i,word in enumerate(a,1):
        following=[i]
        for j,other in enumerate(b,1):following.append(min(following[-1]+1,row[j]+1,row[j-1]+(word!=other)))
        row=following
    return row[-1]/max(1,len(a))


def ocr_child(profile,manifest,out,rounds):
    images=json.loads(Path(manifest).read_text());result={};first=True
    for key,image in images.items():
        times=[];recognized=[]
        for index in range(rounds+1):
            start=time.perf_counter();lines=recognize_rapid(image['path'],profile);elapsed=(time.perf_counter()-start)*1000
            times.append(elapsed);recognized=[line['text'] for line in lines]
            print(f'OCR {profile} {key} {index}: {elapsed:.1f} ms',flush=True)
        result[key]=dict(first_ms=times[0],includes_initial_engine_load=first,warm=summary(times[1:]),rounds_ms=times,
                         recognized_lines=recognized,word_error_rate=wer(image['source_text'],' '.join(recognized)))
        first=False
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


class ObservedStream:
    def __init__(self,response,meter,origin):self.response=response;self.meter=meter;self.origin=origin
    def __enter__(self):self.response.__enter__();return self
    def __exit__(self,*args):return self.response.__exit__(*args)
    def __iter__(self):
        data=[]
        for raw in self.response:
            text=raw.decode('utf-8').rstrip('\r\n')
            if text.startswith('data:'):data.append(text[5:].lstrip())
            elif not text and data:
                payload='\n'.join(data);data=[]
                if payload!='[DONE]':
                    event=json.loads(payload);kind=event.get('type')
                    if kind=='response.output_text.delta' and event.get('delta') and 'first_text_delta_ms' not in self.meter:
                        self.meter['first_text_delta_ms']=(time.perf_counter()-self.origin)*1000
                    if kind=='response.completed':
                        usage=event.get('response',{}).get('usage') or {}
                        self.meter['usage']={key:usage.get(key) for key in ('input_tokens','output_tokens','total_tokens')}
                        self.meter['cached_input_tokens']=(usage.get('input_tokens_details') or {}).get('cached_tokens')
                        self.meter['reasoning_tokens']=(usage.get('output_tokens_details') or {}).get('reasoning_tokens')
            yield raw


def cloud_completion(module,meter):
    def complete(token,model,texts,**options):
        origin=meter['_origin'];real=module.urlopen
        def observe(request,**kwargs):
            response=real(request,**kwargs);meter['http_headers_ms']=(time.perf_counter()-origin)*1000
            return ObservedStream(response,meter,origin)
        with patch.object(module,'urlopen',observe):return module.stream_translation(token,model,texts,**options)
    return complete


def fresh_translator(module):
    with patch.object(module,'read_json',return_value={}):return module.Translator()


def hardware_metadata():
    info=dict(cpu=platform.processor(),logical_processors=os.cpu_count(),platform=platform.platform(),python=platform.python_version())
    if os.name=='nt':
        command="$p=Get-CimInstance Win32_Processor; $m=Get-CimInstance Win32_ComputerSystem; @{cpu=$p.Name.Trim();physical_cores=$p.NumberOfCores;usable_ram_bytes=$m.TotalPhysicalMemory}|ConvertTo-Json -Compress"
        try:info.update(json.loads(subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,timeout=15,check=True).stdout))
        except (subprocess.SubprocessError,ValueError):pass
    return info


def pipeline(case,profile,provider,model,translator,complete,token,out,settings,cache=False):
    from PyQt6.QtCore import QRectF
    started=time.perf_counter();cpu=time.process_time();timings={};stage=started
    image=QImage(case['path']);working=out/'working.png';image.save(str(working))
    timings['input_serialize_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
    lines=recognize_rapid(working,profile)
    timings['ocr_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
    frame=image_to_bgr(image);refine_rapid_regions(frame,lines)
    if settings.get('match_colors',True):
        for line in lines:
            cleaned,rect=make_patch(frame,line,settings.get('inpaint_radius',3),settings.get('mask_padding',1))
            line.update(sample_text_color(frame,line,cleaned,rect))
    if settings.get('smart_grouping',True):lines=group_dialogue(lines,language='auto')
    lines=lines[:settings.get('max_passages',100)];texts=[line['text'] for line in lines]
    if not texts:raise RuntimeError('OCR returned no readable passages')
    timings['prepare_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
    meter={'_origin':stage}
    callback=cloud_completion(complete,meter) if provider=='openai' and not cache else complete
    translated,hits=translator.translate(texts,token,model,source='auto',target='th',provider=provider,complete=callback)
    timings['translation_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
    restored=make_patches(frame,lines,settings.get('inpaint_radius',3),settings.get('mask_padding',1))
    for line,value,(cleaned,rect) in zip(lines,translated,restored):
        line.update(translation=value,target_language='th',patch=cleaned,patch_rect=rect,text_bounds=(0,0,image.width(),image.height()))
    timings['blend_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
    after=image.copy();painter=QPainter(after)
    for line in lines:painter.drawImage(line['patch_rect'].topLeft(),line['patch'])
    for line in lines:paint_translation(painter,line,settings.get('font_size',20))
    painter.end();timings['render_ms']=(time.perf_counter()-stage)*1000
    result=dict(**timings,total_ms=(time.perf_counter()-started)*1000,cpu_ms=(time.process_time()-cpu)*1000,
                passages=len(texts),input_words=len(words(' '.join(texts))),input_chars=sum(map(len,texts)),output_chars=sum(map(len,translated)),
                recognized_passages=texts,translations=translated,cache_hits=hits)
    meter.pop('_origin');result.update(meter)
    if not cache:result['input_words_per_translation_second']=result['input_words']/(result['translation_ms']/1000)
    return result,after


def write_outputs(out,result):
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    flat=[]
    for row in result['runs']:
        entry={key:value for key,value in row.items() if not isinstance(value,(dict,list))}
        entry.update({'usage_'+key:value for key,value in (row.get('usage') or {}).items()});flat.append(entry)
    if flat:
        keys=list(dict.fromkeys(key for row in flat for key in row))
        with (out/'runs.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=keys);writer.writeheader();writer.writerows(flat)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live-openai',action='store_true');parser.add_argument('--openai-model',default='gpt-6-luna')
    parser.add_argument('--rounds',type=int,default=5);parser.add_argument('--output',default=str(ROOT/'artifacts/benchmark-rapid-argos-openai-2026-10-13'))
    parser.add_argument('--ocr-child');parser.add_argument('--manifest');parser.add_argument('--child-output')
    args=parser.parse_args();out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if not 1<=args.rounds<=10:raise ValueError('Choose 1–10 warm rounds.')
    app=QApplication(['RV-benchmark']);QFontDatabase.addApplicationFont(str(ROOT/'PlaypenSansThai-Light.ttf'));QFontDatabase.addApplicationFont(str(ROOT/'Sarabun-Regular.ttf'))
    if args.ocr_child:ocr_child(args.ocr_child,args.manifest,args.child_output,args.rounds);return
    modules,baseline=legacy_modules();translation=modules['translation'];Local=modules['local_translation'].LocalTranslator
    settings=read_json('settings.json',{});images=fixtures(out);manifest=out/'fixtures.json';manifest.write_text(json.dumps(images,ensure_ascii=False,indent=2),encoding='utf-8')
    result=dict(started=datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),baseline=baseline,source='auto (English fixture text)',target='th',rounds=args.rounds,
        hardware=hardware_metadata(),pipeline_settings={key:settings.get(key) for key in ('font_size','match_colors','smart_grouping','inpaint_radius','mask_padding','max_passages','capture_delay','capture_limit')},
        methodology=dict(translation_cache='disabled during inference measurements; cache-hit measurements separate',parallelism='serial provider calls; no competing benchmark workers',
            ocr='RapidOCR PP-OCRv5 CPU; intra_threads=4; inter_threads=1',argos='CTranslate2 CPU int8; intra_threads=2; inter_threads=1',
            cold='Argos first use of a new model/detector object per case, OS file cache may be warm. OpenAI first-request is not a server cold-start measurement.',
            total='Generated fixture PNG serialization + OCR + grouping/color preparation + translation + blend + overlay rasterization; excludes screen capture/hotkey settle/UI and program startup.',
            first_text_delta='First nonempty output_text.delta, including JSON scaffolding; the app waits for the complete JSON before drawing an overlay.',
            quality='Outputs and OCR word error rates retained for review; this is not a comprehensive translation-quality score.'),fixtures=images,ocr={},runs=[],errors=[])
    auth=None
    if args.live_openai:
        from desktop.auth import ChatGPTAuth
        auth=ChatGPTAuth();allowed={slug for slug,_ in auth.models()}
        if args.openai_model not in allowed:raise RuntimeError('Requested model is not available to the connected account.')
        result['openai_model']=args.openai_model
    for profile in ('rapid:ch','rapid:en'):
        child=out/('ocr-'+profile.split(':')[1]+'.json');started=time.perf_counter()
        command=[sys.executable,str(Path(__file__).resolve()),'--ocr-child',profile,'--manifest',str(manifest),'--child-output',str(child),'--rounds',str(args.rounds),'--output',str(out)]
        with (out/('ocr-'+profile.split(':')[1]+'.log')).open('w',encoding='utf-8') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        result['ocr'][profile]=dict(process_wall_ms=(time.perf_counter()-started)*1000,cases=json.loads(child.read_text(encoding='utf-8')))
        print('OCR profile measured: '+profile,flush=True);write_outputs(out,result)
    profile='rapid:ch';recognize_rapid(images['short']['path'],profile)
    capture=[]
    for _ in range(6):
        started=time.perf_counter();app.primaryScreen().grabWindow(0);capture.append((time.perf_counter()-started)*1000)
    result['screen_capture_only']=dict(first_ms=capture[0],warm=summary(capture[1:]),note='Read-only screen grabs timed; actual desktop images are not saved or sent to a provider.')
    providers=[('argos',mode) for mode in ('argos-fast-v1','argos-balanced-v1','argos-quality-v1')]
    if args.live_openai:providers.append(('openai',args.openai_model))
    previews=out/'previews';previews.mkdir(exist_ok=True)
    try:
        for key,case in images.items():
            for provider,model in providers:
                local=Local() if provider=='argos' else None;translator=fresh_translator(translation);translator.cache_enabled=False
                complete=local.complete if local else translation;token=None if local else auth.access_token
                valid=None
                try:
                    for index in range(args.rounds+1):
                        try:
                            row,after=pipeline(case,profile,provider,model,translator,complete,token,out,settings)
                            row.update(case=key,provider=provider,model=model,round=index,state='first' if index==0 else 'warm',ocr_profile=profile)
                            if index==0:after.save(str(previews/(key+'-'+model+'.png')))
                            result['runs'].append(row);valid=row
                            print(f"{key} {model} {row['state']} {index}: OCR={row['ocr_ms']:.1f} ms TRANSLATE={row['translation_ms']:.1f} ms TOTAL={row['total_ms']:.1f} ms",flush=True)
                        except RuntimeError as exc:
                            result['errors'].append(dict(case=key,provider=provider,model=model,round=index,error=str(exc)));print('Benchmark sample failed: '+str(exc),flush=True);break
                        finally:write_outputs(out,result)
                    if valid:
                        cached=fresh_translator(translation);cached.cache_enabled=True
                        cache_dir=out/'cache-data';cache_dir.mkdir(exist_ok=True)
                        def save(name,value):(cache_dir/(key+'-'+model+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
                        with patch.object(translation,'write_json',save):cached.translate(valid['recognized_passages'],None,model,source='auto',target='th',provider=provider,complete=lambda *a,**k:valid['translations'])
                        def no_inference(*args,**kwargs):raise AssertionError('Cache hit unexpectedly invoked translation/auth')
                        for index in range(args.rounds):
                            row,_=pipeline(case,profile,provider,model,cached,no_inference,no_inference,out,settings,cache=True)
                            assert row['cache_hits']==row['passages']
                            row.update(case=key,provider=provider,model=model,round=index,state='cached',ocr_profile=profile);result['runs'].append(row)
                        write_outputs(out,result)
                finally:
                    if local:local.stop()
    finally:
        result['finished']=datetime.now(ZoneInfo('Asia/Bangkok')).isoformat();write_outputs(out,result)
    print('Benchmark complete: '+str(out),flush=True)


if __name__=='__main__':main()
