"""Summarize the measured OCR/translation samples and export standard plots."""
import argparse,csv,html,json,os,statistics,sys
from collections import defaultdict
from pathlib import Path

MODELS=('argos-fast-v1','argos-balanced-v1','argos-quality-v1','gpt-6-luna')
LABELS={'argos-fast-v1':'Argos Fast','argos-balanced-v1':'Argos Balanced','argos-quality-v1':'Argos Quality','gpt-6-luna':'GPT-6-Luna'}
METRICS=('input_serialize_ms','ocr_ms','prepare_ms','translation_ms','blend_ms','render_ms','total_ms','cpu_ms','first_text_delta_ms','http_headers_ms')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('directory');args=parser.parse_args();out=Path(args.directory).resolve()
    data=json.loads((out/'results.json').read_text(encoding='utf-8'))
    if not data.get('finished'):raise RuntimeError('The benchmark must finish before producing a report.')
    groups=defaultdict(list)
    for row in data['runs']:groups[row['case'],row['model'],row['state']].append(row)
    aggregate=[];lookup={}
    for (case,model,state),rows in groups.items():
        item=dict(case=case,label=data['fixtures'][case]['label'],model=model,provider=rows[0]['provider'],state=state,n=len(rows),passages=rows[0]['passages'],input_words=rows[0]['input_words'])
        for metric in METRICS:
            values=[row[metric] for row in rows if isinstance(row.get(metric),(int,float))]
            if values:
                item[metric+'_median']=statistics.median(values);item[metric+'_min']=min(values);item[metric+'_max']=max(values)
                item[metric+'_stdev']=statistics.stdev(values) if len(values)>1 else 0.
        aggregate.append(item);lookup[case,model,state]=item
    (out/'summary.json').write_text(json.dumps(aggregate,ensure_ascii=False,indent=2),encoding='utf-8')
    keys=list(dict.fromkeys(key for row in aggregate for key in row))
    with (out/'summary.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=keys);writer.writeheader();writer.writerows(aggregate)
    cases=list(data['fixtures']);models=[model for model in MODELS if any(key[1]==model for key in lookup)]
    def value(case,model,metric='translation_ms',state='warm'):
        return lookup.get((case,model,state),{}).get(metric+'_median')
    def fmt(v,unit='s'):return '—' if v is None else f'{v/1000:.3f}' if unit=='s' else f'{v:.2f}'
    text=['# RapidOCR + Argos / OpenAI benchmark','',
          f"Measured: {data['started']} → {data['finished']}",
          f"Machine: {data['hardware']['cpu']}, {data['hardware']['physical_cores']} physical / {data['hardware']['logical_processors']} logical processors; {data['hardware']['usable_ram_bytes']/1024**3:.2f} GiB usable RAM.",
          '',f"Translation baseline: deployed **{data['baseline']['version']}** modules from `{data['baseline']['archive']}`. The installed executable and its settings were not updated.",
          '',f"Source: Auto detect on English fixture text. Target: Thai. **{data['rounds']} warm rounds per case/provider**, plus the first request; client translation cache disabled during inference. Only generated public fixture text was sent to OpenAI.",
          '', 'The main comparison uses **RapidOCR PP-OCRv5 / rapid:ch**, matching Auto source’s English/Chinese/Japanese profile. `rapid:en` was also measured separately. Argos uses CPU int8 / 2 intra-op threads; RapidOCR uses CPU / 4 intra-op threads.',
          '', '**Observed output limitation:** In the 63-word single-sentence fixture, all three Argos modes omit later clauses. Fast/Quality stop after the food/water clause; Balanced reaches the map clause but omits the flooded-road/bridge/travel clauses. GPT-6-Luna retains those clauses. Argos Quality also omits the pizza option in one paragraph fixture. These latency results are not an equal-completeness or equal-quality comparison. See `output-review.md` for the actual outputs.',
          '', '## Translation only, warm median (seconds)','',
          '| Fixture | Words read | Passages | '+' | '.join(LABELS[m] for m in models)+' |',
          '|---|---:|---:|'+'---:|'*len(models)]
    for case in cases:
        item=lookup.get((case,models[0],'warm'),{})
        text.append(f"| {data['fixtures'][case]['label']} | {item.get('input_words','—')} | {item.get('passages','—')} | "+' | '.join(fmt(value(case,m)) for m in models)+' |')
    text+=['','## Complete fixture pipeline, warm median (seconds)','',
           'Includes PNG serialization, OCR, glyph/color preparation, grouping, translation, background restoration and overlay rasterization. This is **not measured F1-to-display latency**: screen capture, capture-settle delay, browser UI and one-file executable startup are excluded.','',
           '| Fixture | '+' | '.join(LABELS[m] for m in models)+' |','|---|'+'---:|'*len(models)]
    for case in cases:text.append('| '+data['fixtures'][case]['label']+' | '+' | '.join(fmt(value(case,m,'total_ms')) for m in models)+' |')
    text+=['','## Translation spread (milliseconds)','',
           '| Fixture | Model | First request | Warm median | Warm min–max | Warm standard deviation |','|---|---|---:|---:|---:|---:|']
    for case in cases:
        for model in models:
            item=lookup.get((case,model,'warm'),{});first=value(case,model,state='first')
            text.append(f"| {data['fixtures'][case]['label']} | {LABELS[model]} | {fmt(first,'ms')} | {fmt(value(case,model),'ms')} | {fmt(item.get('translation_ms_min'),'ms')}–{fmt(item.get('translation_ms_max'),'ms')} | {fmt(item.get('translation_ms_stdev'),'ms')} |")
    text+=['','First Argos requests include a new model/detector object per fixture; shared library language models and the OS disk cache may already be warm. OpenAI “first” means the first measured request for that fixture, **not a controlled server cold start**. No p95/p99 claim is made from five rounds.','',
           '## RapidOCR only (milliseconds)','',
           '| Profile | Fixture | First | Includes engine cold load? | Warm median | Warm min–max | Word error rate |','|---|---|---:|---|---:|---:|---:|']
    for profile,info in data['ocr'].items():
        for case,item in info['cases'].items():
            warm=item['warm'];text.append(f"| {profile} | {data['fixtures'][case]['label']} | {item['first_ms']:.2f} | {'Yes' if item['includes_initial_engine_load'] else 'No'} | {warm['median']:.2f} | {warm['minimum']:.2f}–{warm['maximum']:.2f} | {item['word_error_rate']*100:.2f}% |")
    text+=['','Each profile was measured in a fresh child process. Only its first fixture includes initial inference-library/engine loading; the remaining fixtures reuse the engine. WER normalizes English case/punctuation and compares recognized words to generated fixture text. These clean images do not measure OCR quality on textured game scenes.','',
           '## Client cache-hit pipeline (milliseconds)','',
           'Cache was seeded from an actual successful measured translation in an isolated benchmark cache. Cache-hit rounds assert that neither inference nor authentication is called. OCR and background preparation still run.','',
           '| Fixture | Model | Cache lookup median | Whole cached pipeline median |','|---|---|---:|---:|']
    for case in cases:
        for model in models:text.append(f"| {data['fixtures'][case]['label']} | {LABELS[model]} | {fmt(value(case,model,state='cached'),'ms')} | {fmt(value(case,model,'total_ms',state='cached'),'ms')} |")
    if 'gpt-6-luna' in models:
        text+=['','## OpenAI stream timing and tokens','',
               '| Fixture | First text delta median | Complete translation median | Mean input tokens | Mean output tokens |','|---|---:|---:|---:|---:|']
        for case in cases:
            rows=groups.get((case,'gpt-6-luna','warm'),[])
            ins=[row['usage']['input_tokens'] for row in rows if isinstance((row.get('usage') or {}).get('input_tokens'),int)]
            outs=[row['usage']['output_tokens'] for row in rows if isinstance((row.get('usage') or {}).get('output_tokens'),int)]
            text.append(f"| {data['fixtures'][case]['label']} | {fmt(value(case,'gpt-6-luna','first_text_delta_ms'))} s | {fmt(value(case,'gpt-6-luna'))} s | {statistics.mean(ins) if ins else 'unavailable'} | {statistics.mean(outs) if outs else 'unavailable'} |")
        text+=['','The first text delta can be JSON scaffolding. Studio waits for the completed translation array before painting; first-delta timing is not visible-overlay latency. The observer reads `response.output_text.delta` and `response.completed` while preserving the deployed request and prompt. [OpenAI Docs: streaming responses](https://developers.openai.com/api/docs/guides/streaming-responses).',
               '','Server prompt caching was not disabled; reported cached input token counts are retained per request in `results.json`. Client translation cache was disabled for inference comparisons.']
    capture=data['screen_capture_only']
    text+=['','## Screen capture overhead measured separately','',f"Read-only screen grab: first {capture['first_ms']:.2f} ms; five-round warm median {capture['warm']['median']:.2f} ms, range {capture['warm']['minimum']:.2f}–{capture['warm']['maximum']:.2f} ms. These grabs were timed only; actual desktop images were not retained or sent to OpenAI."]
    total_calls=sum(row['provider']=='openai' and row['state']!='cached' for row in data['runs'])
    text+=['','## Scope and reproducibility','',f"- Successful live OpenAI calls: {total_calls}; failed samples: {len(data['errors'])}.",
           '- Measurements are serial on this machine and network. Cloud load and network latency can change the result.',
           '- Timing and structural completeness are measured; output quality, named entities and omissions require review. All recognized inputs and translated outputs are retained.',
           '- `runs.csv`: every timing sample. `summary.csv`: group medians/ranges. `results.json`: inputs, outputs, stage timings, usage and metadata.',
           '- `fixtures/`: public benchmark images. `previews/`: rendered outputs. `cache-data/`: isolated benchmark translations only.',
           '- Re-run: `python tools/benchmark_rapid_translation.py --live-openai --openai-model gpt-6-luna --rounds 5 --output <new directory>`, then `python tools/report_rapid_benchmark.py <directory>`. Live requests consume connected-account quota.',
           '',f"Baseline archive SHA256: `{data['baseline']['sha256']}`."]
    if data['errors']:text+=['','Errors:',*['- '+json.dumps(error,ensure_ascii=False) for error in data['errors']]]
    report='\n'.join(text)+'\n';(out/'report.md').write_text(report,encoding='utf-8')
    os.environ['MPLCONFIGDIR']=str(out/'.matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogLocator,FuncFormatter
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,2,figsize=(14,5.5),layout='constrained')
    colors=['#777777','#333333','#aaaaaa','#207a98'];x=np.arange(len(cases));width=.18
    for axis,metric,title in zip(axes,('translation_ms','total_ms'),('Translation only · warm median','OCR → translated overlay · warm median')):
        for index,model in enumerate(models):
            vals=[value(case,model,metric) or float('nan') for case in cases]
            bars=axis.bar(x+(index-(len(models)-1)/2)*width,vals,width,label=LABELS[model],color=colors[index])
            for bar,val in zip(bars,vals):axis.annotate(f'{val/1000:.2f}s',(bar.get_x()+bar.get_width()/2,val),xytext=(0,4),textcoords='offset points',ha='center',fontsize=8,rotation=90)
        axis.set_yscale('log');axis.set_ylabel('Milliseconds · logarithmic scale');axis.set_xticks(x,['Short','Long sentence*','Paragraph','10 text rows'])
        axis.set_title(title,pad=14);axis.grid(axis='y',alpha=.18);axis.set_axisbelow(True);axis.set_ylim(8,max(value(case,model,metric) or 0 for case in cases for model in models)*3)
    handles,labels=axes[0].get_legend_handles_labels();fig.legend(handles,labels,loc='outside lower center',ncol=len(models),frameon=False)
    fig.suptitle('RapidOCR + Argos vs GPT-6-Luna · English → Thai\n*Argos omits later clauses in the long-sentence fixture; not equal-completeness timing.',fontsize=13)
    fig.savefig(out/'comparison.png',dpi=170);fig.savefig(out/'comparison.svg');plt.close(fig)
    # Self-contained, local-only interactive table; no CDN or network resources.
    table_rows=[]
    for row in aggregate:
        table_rows.append('<tr data-state="'+row['state']+'"><td>'+html.escape(row['label'])+'</td><td>'+LABELS.get(row['model'],html.escape(row['model']))+'</td><td>'+row['state']+'</td><td>'+str(row['n'])+'</td>'+''.join('<td>'+fmt(row.get(metric+'_median'),'ms')+'</td>' for metric in ('ocr_ms','prepare_ms','translation_ms','blend_ms','render_ms','total_ms'))+'</tr>')
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>RV Translation benchmark</title><style>body{font:15px/1.6 system-ui;margin:40px auto;max-width:1180px;padding:0 22px;background:#111;color:#eee}h1{line-height:1.2}p{color:#b8b8b8}img{width:100%;background:white;border-radius:8px}select,a{color:#ddd}select{background:#222;border:1px solid #555;padding:8px;border-radius:5px}table{width:100%;border-collapse:collapse;font-size:13px;margin-top:16px}th,td{text-align:right;padding:10px;border-bottom:1px solid #333}td:first-child,th:first-child,td:nth-child(2),th:nth-child(2){text-align:left}th{color:#aaa;position:sticky;top:0;background:#171717}.scroll{overflow:auto}code{background:#222;padding:3px 5px}label{display:block;margin-top:24px}</style><h1>RV Translation benchmark</h1><p>RapidOCR + Argos / GPT-6-Luna · English → Thai · deployed 2.9.2 translation baseline · warm n=5</p><p>Client cache disabled for inference. Totals begin with a generated fixture; they exclude screen capture, capture delay and executable startup. All table values are milliseconds.</p><img src="comparison.svg" alt="Measured translation and pipeline latencies on a logarithmic scale"><label>Show samples <select id="state"><option value="warm">Warm inference</option><option value="first">First request</option><option value="cached">Client cache hit</option><option value="all">All</option></select></label><div class="scroll"><table><thead><tr><th>Fixture</th><th>Model</th><th>State</th><th>n</th><th>OCR</th><th>Prepare</th><th>Translate</th><th>Blend</th><th>Render</th><th>Total</th></tr></thead><tbody>'''+''.join(table_rows)+'''</tbody></table></div><p><a href="report.md">Methodology and complete report</a> · <a href="runs.csv">Raw CSV</a> · <a href="summary.csv">Summary CSV</a> · <a href="results.json">JSON, inputs and translated outputs</a></p><script>const state=document.getElementById('state');function filter(){document.querySelectorAll('tbody tr').forEach(row=>row.hidden=state.value!=='all'&&row.dataset.state!==state.value)}state.addEventListener('change',filter);filter();</script></html>'''
    page=page.replace('<img src="comparison.svg"','<p><strong>Output review:</strong> Argos omits later clauses in the 63-word single sentence. Faster timing does not imply complete translation. <a href="output-review.md">Read the actual outputs</a>.</p><img src="comparison.svg"')
    (out/'report.html').write_text(page,encoding='utf-8')
    review=['# Actual translated-output review','', 'One representative warm round per model, with the exact OCR inputs shared by both providers. Observations are qualitative for these fixtures, not a general model accuracy score.','']
    for case in ('long_sentence','paragraph'):
        review+=['## '+data['fixtures'][case]['label'],'']
        first=groups[case,models[0],'warm'][0]
        review+=['### OCR input','',*first['recognized_passages'],'']
        for model in models:
            sample=groups[case,model,'warm'][0];review+=['### '+LABELS[model],'',*sample['translations'],'']
    (out/'output-review.md').write_text('\n'.join(review),encoding='utf-8')
    print(json.dumps(dict(samples=len(data['runs']),successful_live_calls=total_calls,errors=len(data['errors']),summary=str(out/'summary.csv'),report=str(out/'report.html'))))


if __name__=='__main__':main()
