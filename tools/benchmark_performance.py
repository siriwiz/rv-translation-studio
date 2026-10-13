"""Repeatable OCR comparison; optional real translation timing on public sample text."""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root),str(root/'.build-tools')]
from desktop.translation import recognize, recognize_legacy, stream_translation

parser = argparse.ArgumentParser()
parser.add_argument('--live-models',nargs='*')
args = parser.parse_args()
path = root/'artifacts/game-flow/captured.png'
result = {'image':str(path.relative_to(root)), 'ocr':{},'translation':[]}
outputs = {}
for name,fn,count in [('native',recognize,6),('powershell',recognize_legacy,3)]:
    elapsed = []
    for _ in range(count):
        start = time.perf_counter()
        outputs[name] = fn(path)
        elapsed.append(time.perf_counter()-start)
    result['ocr'][name] = dict(first_seconds=elapsed[0],warm_median_seconds=statistics.median(elapsed[1:]),rounds=elapsed)
def geometry(lines):
    return [dict(text=line['text'],**{key:line[key] for key in ('x','y','w','h')},
                 words=[{key:word[key] for key in ('x','y','w','h')} for word in line['words']]) for line in lines]
result['ocr_same_text_and_boxes'] = geometry(outputs['native']) == geometry(outputs['powershell'])
if args.live_models:
    from desktop.auth import ChatGPTAuth
    auth = ChatGPTAuth()
    allowed = {slug for slug,name in auth.models()}
    token = auth.access_token()
    for model in args.live_models:
        if model not in allowed:
            continue
        start = time.perf_counter()
        try:
            translated = stream_translation(token,model,[
                'I still remember the night you came back to the valley.',
                'We should return to the old station before the storm arrives.',
                'Do you think anyone still remembers what happened here?'])
            item = dict(model=model,seconds=time.perf_counter()-start,passages=3,translations=translated)
        except RuntimeError as exc:
            item = dict(model=model,seconds=time.perf_counter()-start,error=str(exc))
        result['translation'].append(item)
target = root/'artifacts/performance'
target.mkdir(parents=True,exist_ok=True)
if not args.live_models and (target/'benchmark.json').exists():
    result['translation'] = json.loads((target/'benchmark.json').read_text(encoding='utf-8')).get('translation',[])
(target/'benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=True))
