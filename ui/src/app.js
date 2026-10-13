'use strict';
const $ = id => document.getElementById(id);
const pages = ['studio','library','connection','settings'];
let bridge = null, state = null, catalog = [], selectedHistory = new Set(), historySignature = '', previewMode = 'translated';
const samples = {th:'หุบเขาแห่งนี้ยังจดจำคุณได้',en:'The valley remembers you.',ja:'この谷はまだあなたを覚えている。','zh-Hans':'山谷依然记得你。','zh-Hant':'山谷依然記得你。',ko:'이 계곡은 아직 당신을 기억해요.',fr:'La vallée se souvient de vous.',es:'El valle te recuerda.',ar:'الوادي لا يزال يتذكرك.',de:'Das Tal erinnert sich an dich.',ru:'Долина помнит тебя.'};
const settingGroups = {
  capture: [
    ['ocr_backend','OCR engine','Read locally with Windows OCR or bundled multilingual models.','select',[['native','Windows OCR · fast'],['rapid','RapidOCR · multilingual'],['legacy','PowerShell · compatibility']]],
    ['capture_limit','Maximum image dimension','Smaller images process faster; small lettering may need more detail.','select',[[1280,'1280 px · speed'],[1920,'1920 px · balanced'],[2500,'2500 px · small text']]],
    ['capture_delay','Capture settle delay','Allow Studio to disappear before the screenshot.','number',[80,1000,'ms']],
    ['subtitle_percent','Subtitle zone','Percentage of the bottom of the display.','number',[15,70,'%']],
    ['max_passages','Passages per request','Limit how much text is sent for translation.','number',[1,100,'']]
  ],
  overlay: [
    ['inpaint_radius','Background repair radius','Controls how far background restoration samples around text.','number',[1,7,'px']],
    ['mask_padding','Text removal padding','Expand the mask around the recognized words.','number',[0,5,'px']],
    ['match_colors','Match source colors','Sample the original glyph color for each passage.','toggle'],
    ['smart_grouping','Smart dialogue','Join wrapped lines before translation.','toggle'],
    ['click_clear','Click overlay to clear','F2 always remains available.','toggle']
  ],
  performance: [
    ['request_timeout','Translation timeout','Maximum wait during a local or cloud translation request.','number',[30,180,'s']],
    ['cache_enabled','Reuse translations','Identical dialogue in the same language pair skips translation.','toggle']
  ],
  interface: [
    ['motion','Interface motion','Connection heartbeat, transitions and processing animation.','toggle'],
    ['hide_capture','Stay in game','Hide this dashboard for capture and keep it minimized afterward.','toggle']
  ]
};
function el(tag, cls, text) { const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; }
for(const [group,settings] of Object.entries(settingGroups)) {
  for(const [key,title,description,type,options] of settings) {
    const row=el('label','setting-line'), text=el('span','setting-description');
    text.append(el('strong','',title),el('p','',description)); row.append(text);
    let input;
    if(type==='select') { input=el('select','select'); options.forEach(([v,t])=>input.add(new Option(t,v))); }
    else { input=el('input',type==='toggle'?'toggle toggle-sm':'input'); input.type=type==='toggle'?'checkbox':'number'; if(options){input.min=options[0];input.max=options[1];input.setAttribute('aria-label',title+(options[2]?' in '+options[2]:''));} }
    input.dataset.setting=key; if(!input.hasAttribute('aria-label'))input.setAttribute('aria-label',title); row.append(input); $(group+'-settings').append(row);
  }
}
function command(action,payload={}) {
  if(!bridge) { $('status-message').textContent='Design preview · desktop actions require RV TRANSLATION STUDIO.'; return; }
  bridge.dispatch(JSON.stringify({action,...payload}));
}
function setPage(page,notify=true) {
  if(!pages.includes(page))return;
  document.querySelectorAll('.page').forEach(n=>n.classList.toggle('active',n.id==='page-'+page));
  document.querySelectorAll('.nav-item').forEach(n=>{n.classList.toggle('active',n.dataset.page===page); if(n.dataset.page===page)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');});
  $('breadcrumb').textContent={studio:'Studio',library:'Dialogue library',connection:'Connection',settings:'Settings'}[page];
  $('action-dock').classList.toggle('hidden',page!=='studio');
  $('viewport').classList.toggle('studio-viewport',page==='studio');
  window.RVControls?.close();
  $('viewport').scrollTop=0;
  if(notify)command('navigate',{index:pages.indexOf(page)});
}
document.querySelectorAll('[data-page]').forEach(n=>n.addEventListener('click',()=>setPage(n.dataset.page)));
document.querySelectorAll('.nav-item').forEach(n=>n.title=n.querySelector('.nav-text')?.textContent||'');
document.querySelectorAll('[data-help]').forEach(n=>{n.title='Workflow & Shortcuts';n.setAttribute('aria-label','Workflow & Shortcuts');});
document.querySelectorAll('[data-action]').forEach(n=>n.addEventListener('click',()=>{
  if(n.dataset.action==='capture')command('capture',{source:$('source-language').value,target:$('target-language').value});
  else command(n.dataset.action);
}));
document.querySelectorAll('[data-settings-page]').forEach(n=>n.addEventListener('click',()=>{
  document.querySelectorAll('.settings-tab').forEach(b=>b.classList.toggle('active',b===n));
  document.querySelectorAll('.settings-section').forEach(s=>s.classList.toggle('active',s.id==='settings-'+n.dataset.settingsPage));
}));
document.querySelectorAll('[data-help]').forEach(n=>n.addEventListener('click',()=>$('help-dialog').showModal()));
$('capture-setup-toggle').addEventListener('click',()=>{
  const open=$('page-studio').classList.toggle('capture-open');
  $('capture-setup-toggle').setAttribute('aria-expanded',String(open));
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&$('page-studio').classList.contains('capture-open')){
    $('page-studio').classList.remove('capture-open');$('capture-setup-toggle').setAttribute('aria-expanded','false');
  }
});
$('help-dialog').addEventListener('click',event=>{if(event.target===$('help-dialog'))$('help-dialog').close();});
document.addEventListener('change',event=>{
  const n=event.target;
  if(n.matches('[data-setting]'))command('setting',{key:n.dataset.setting,value:n.type==='checkbox'?n.checked:n.value});
  if(n.id==='source-language'||n.id==='target-language')command('languages',{source:$('source-language').value,target:$('target-language').value});
  if(n.id==='sample-input')command('sample_input',{text:n.value});
});
$('font-size').addEventListener('input',event=>{
  $('scale-value').textContent=Math.round(Number(event.target.value)/20*100)+'%';
  command('setting',{key:'font_size',value:event.target.value});
});
document.querySelectorAll('[data-preview]').forEach(n=>n.addEventListener('click',()=>{
  previewMode=n.dataset.preview; updatePreview(); command('preview',{translated:previewMode==='translated'});
}));
$('translate-sample').addEventListener('click',()=>command('sample',{text:$('sample-input').value}));
$('clear-sample').addEventListener('click',()=>{$('sample-input').value='';command('clear_sample');});
$('history-search').addEventListener('input',()=>renderHistory(true));
$('select-all-history').addEventListener('change',event=>{
  document.querySelectorAll('[data-history-index]').forEach(input=>{input.checked=event.target.checked;if(input.checked)selectedHistory.add(Number(input.dataset.historyIndex));else selectedHistory.delete(Number(input.dataset.historyIndex));}); updateSelection();
});
$('copy-history').addEventListener('click',()=>command('copy_history',{rows:[...selectedHistory]}));
function selectOptions(id,items,current) {
  const n=$(id), signature=JSON.stringify(items);
  if(n.dataset.signature!==signature){n.replaceChildren();for(const item of items)n.add(new Option(item.label,item.value));n.dataset.signature=signature;}
  if(document.activeElement!==n)n.value=String(current??'');
}
function setText(id,value) { const n=$(id); if(n && n.textContent!==String(value??''))n.textContent=value??''; }
function setValue(id,value) { const n=$(id);if(document.activeElement!==n && n.value!==String(value??''))n.value=value??''; }
function setDisabled(id,value) { const n=$(id);if(n)n.disabled=!!value; }
function languageName(code) { return catalog.find(x=>x.code===code)?.name || (code==='auto'?'Auto detect':code?.replace(/^custom:/,'')||''); }
function applyState(next) {
  const prior=state; state=next; window.rvState=state;
  if(prior&&JSON.stringify(prior.history)!==JSON.stringify(next.history))selectedHistory.clear();
  if(!prior||prior.page!==next.page)setPage(pages[next.page]||'studio',false);
  document.body.classList.toggle('reduced-motion',!next.settings.motion);
  const badge=$('connection-badge');badge.classList.toggle('connected',next.connected);badge.classList.toggle('busy',next.auth_busy);
  const local=next.provider==='argos',provider=next.provider_label||'ChatGPT';
  setText('connection-label',next.auth_busy?(local?'Loading local modes…':'Connecting…'):local&&next.connected?'Argos Local · Offline':next.connected?provider+' connected':'Connect '+provider);
  setValue('provider',next.provider||'openai');
  setText('account-provider-title',local?'OFFLINE TRANSLATION ENGINE':'CHATGPT ACCOUNT');
  setText('login','Continue with ChatGPT ↗');
  setText('sign-out','Sign out');
  $('add-account').classList.toggle('hidden',local);
  for(const id of ['login','sign-out','manage-usage','saved-accounts-field'])$(id).classList.toggle('hidden',local);
  setText('reload-models',local?'Reload local modes':'Reload models');
  setText('privacy-text-route',local?'Recognized text stays on this PC':'Only recognized text is sent');
  setText('manage-usage','Manage usage ↗');
  setText('provider-help',local?'Built in: '+(next.local_languages||[]).join(', ')+'. No sign-in, API key or runtime downloads. Language pairs may pivot through English; pivoting takes two translation steps. Auto detect identifies each recognized or pasted passage locally; choose a target language. Short ambiguous text may need an explicit source. Fast, Balanced and Quality modes adjust decoding effort.':'Sign in through your browser to use models available to your ChatGPT account. Tokens are protected by Windows encryption.');
  setText('privacy-credentials',local?'Offline translation · No credentials':'Windows-encrypted ChatGPT credentials');
  setValue('source-language',languageName(next.source));setValue('target-language',languageName(next.target));
  setText('ocr-short',next.ocr_active);
  setText('ocr-note',next.ocr_note);setText('region-summary',next.region);
  $('custom-area-hint').classList.toggle('hidden',next.settings.mode!==2);
  selectOptions('screen',next.screens,next.settings.screen);selectOptions('model',next.models,next.model);
  selectOptions('account',next.accounts,next.account_index);
  selectOptions('ocr-profile',[{label:'Follow source language',value:'auto'},...next.ocr_languages],next.settings.ocr_language||'auto');
  const rapid=next.settings.ocr_backend==='rapid';
  setText('ocr-engine-status',rapid?'LOCAL OCR / RAPIDOCR':next.settings.ocr_backend==='legacy'?'LOCAL OCR / POWERSHELL':'LOCAL OCR / WINDOWS');
  setText('ocr-engine-heading',rapid?'Bundled. Local. Ready.':'Your Windows reading profiles.');
  setText('ocr-engine-eyebrow',rapid?'RAPIDOCR / PP-OCRv5':'WINDOWS OCR / INSTALLED PACKS');
  setText('installed-ocr-note',rapid?'11 bundled profiles · CPU inference · No Windows language packs or runtime downloads.':next.ocr_languages.length?next.ocr_languages.map(x=>x.label).join(' / '):'No OCR packs found. Add a supported Windows language pack, then reload.');
  setText('ocr-profile-label',rapid?'Reading profile':'OCR language');
  setText('ocr-auto-note',rapid?'Follow source selects the model for supported languages. Auto source reads English, Chinese and Japanese by default; choose a reading profile for other scripts. First use loads the model; later captures reuse it.':'Auto detect identifies text after OCR. Screenshot recognition needs a matching installed Windows OCR profile.');
  $('ocr-windows-packs').classList.toggle('hidden',rapid);
  for(const input of document.querySelectorAll('[data-setting]')) {
    const key=input.dataset.setting;
    if(key==='model'||key==='account'||key==='screen'||key==='ocr_language')continue;
    const value=next.settings[key];
    if(input.type==='checkbox')input.checked=!!value;
    else if(document.activeElement!==input && value!==undefined)input.value=String(value);
    input.disabled=next.busy || (next.auth_busy&&['mode','smart_grouping','hide_capture','match_colors'].includes(key));
  }
  for(const id of ['source-language','target-language','swap-languages','screen','model','account','ocr-profile','provider'])setDisabled(id,next.busy||next.auth_busy);
  document.querySelectorAll('[data-action="pick_region"]').forEach(n=>n.disabled=next.busy||next.auth_busy);
  for(const id of ['login','add-account','reload-models','sign-out'])setDisabled(id,next.busy||next.auth_busy);
  setDisabled('translate-screen',!next.capture_enabled);setDisabled('translate-sample',!next.sample_enabled);
  setDisabled('copy-latest',!next.has_history);setDisabled('copy-sample',!next.sample_copy);
  setText('translate-screen-label',next.busy?'Translating…':next.auth_busy?(local?'Loading local modes…':'Loading account…'):next.local_route_error?'Choose supported languages':next.ready?(next.settings.mode===2?'Select & translate':'Translate screen'):'Connect '+provider);
  setText('dock-title',next.busy?{capture:'Capturing your screen.',recognize:'Reading the scene.',translate:'Translating the dialogue.',blend:'Restoring the background.'}[next.phase]||'Working on your translation.':next.local_route_error?'Choose your languages.':next.ready?(local?'Ready. Fully offline.':'Ready when you are.'):'A connection away.');
  setText('readiness',next.readiness);setText('status-message',next.message);$('status-message').title=next.message;
  if(next.phase==='error')$('status-message').style.color='#e5b9b9';else $('status-message').style.color='';
  setText('footer-pair',next.pair);setText('sample-pair',next.pair);
  setText('latest-source',next.latest_source||'Your captured dialogue will appear here.');
  setText('latest-translation',next.latest_translation||'Your next line starts here.');
  $('latest-translation').classList.toggle('empty-copy',!next.latest_translation);
  setText('metric-time',next.metric_time);setText('metric-passages',next.session_passages);setText('metric-cache',next.session_cache);
  setText('metric-note',next.metric_note);setText('scale-value',Math.round(next.settings.font_size/20*100)+'%');
  $('scene').classList.toggle('busy',next.busy);
  const phaseIndex=['capture','recognize','translate','blend'].indexOf(next.phase);
  document.querySelectorAll('.pipe-step').forEach((n,i)=>{n.classList.toggle('active',next.busy&&phaseIndex===i);n.classList.toggle('complete',next.phase==='complete'||next.busy&&phaseIndex>i);});
  setText('account-name',next.account_name);setText('account-plan',next.account_plan);
  setText('account-avatar',next.connected?next.account_name[0].toUpperCase():'↗');
  $('cancel-login').classList.toggle('hidden',!next.login_pending);
  setValue('sample-input',next.sample_input);setText('sample-output',next.sample_output);
  setText('cache-size',next.cache_size);$('undo-history').classList.toggle('hidden',!next.undo_history);
  setText('performance-detail',next.performance_detail);
  const timings=next.timings||{}, total=Object.values(timings).reduce((a,b)=>a+b,0);
  setText('performance-total',total?total.toFixed(2)+' s':'—');
  if(JSON.stringify(timings)!==$('timing-bar').dataset.signature) {
    $('timing-bar').replaceChildren();$('timing-legend').replaceChildren();
    const colors=['#77776c','#a1a196','#56564c','#e7e7d8','#b8b8a8'];
    Object.entries(timings).forEach(([name,seconds],i)=>{const segment=el('span');segment.style.width=seconds/total*100+'%';segment.style.background=colors[i%colors.length];segment.title=name+': '+Math.round(seconds*1000)+' ms';$('timing-bar').append(segment);const legend=el('span','',name.toUpperCase()+' ');legend.append(el('b','',Math.round(seconds*1000).toLocaleString()+' ms'));$('timing-legend').append(legend);});
    if(!total)$('timing-legend').textContent='Complete a capture to see measured timings.';
    $('timing-bar').dataset.signature=JSON.stringify(timings);
  }
  updatePreview();renderHistory();window.RVControls?.sync();
}
function updatePreview() {
  if(!state)return;
  $('preview-original').classList.toggle('tab-active',previewMode==='original');$('preview-translated').classList.toggle('tab-active',previewMode==='translated');
  $('preview-original').setAttribute('aria-selected',String(previewMode==='original'));$('preview-translated').setAttribute('aria-selected',String(previewMode==='translated'));
  const src=previewMode==='original'?state.preview_before:state.preview_after, image=$('capture-preview');
  $('scene').classList.toggle('has-capture',!!src);
  image.classList.toggle('hidden',!src);if(src && image.src!==src)image.src=src;
  $('scene-subtitle').classList.toggle('hidden',!!src);
  document.querySelector('.scene-label').classList.toggle('hidden',!!src);
  setText('scene-subtitle',previewMode==='original'?'The valley remembers you.':samples[state.target]||'Your translated dialogue appears here.');
  $('scene-subtitle').style.fontSize=(18*state.settings.font_size/20)+'px';
  setText('preview-caption',src?state.preview_caption:'ILLUSTRATIVE SCENE / YOUR CAPTURE APPEARS HERE');
}
function renderHistory(force=false) {
  if(!state)return;
  const query=$('history-search').value.toLocaleLowerCase().trim(), signature=JSON.stringify([state.history,query]);
  if(!force&&signature===historySignature)return;historySignature=signature;
  const rows=$('history-rows');rows.replaceChildren();let count=0;
  for(const [index,item] of state.history.entries()) {
    if(query&&!`${item.source} ${item.translation} ${item.pair}`.toLocaleLowerCase().includes(query))continue;
    count++;
    const tr=el('tr');tr.classList.toggle('selected',selectedHistory.has(index));
    const check=el('input','checkbox');check.type='checkbox';check.dataset.historyIndex=index;check.checked=selectedHistory.has(index);check.setAttribute('aria-label','Select passage '+(index+1));
    check.addEventListener('change',()=>{if(check.checked)selectedHistory.add(index);else selectedHistory.delete(index);updateSelection();});
    const select=el('td');select.append(check);tr.append(select);
    tr.append(el('td','muted',item.time.replace(' ','\n')));
    const text=el('td'), source=el('div','source-copy',item.source), translated=el('div','',item.translation);translated.dir='auto';text.append(source,translated);tr.append(text);
    tr.append(el('td','muted',item.pair));
    tr.addEventListener('click',event=>{if(event.target===check)return;selectedHistory=new Set([index]);renderHistory(true);updateSelection();});
    rows.append(tr);
  }
  $('history-empty').classList.toggle('hidden',count>0);
  if(!count){const empty=$('history-empty');empty.querySelector('h2').textContent=query?'No matching dialogue.':'A story waiting to be told.';empty.querySelector('p').textContent=query?'Try another word or language.':'Press F1 in your game. Your translated conversations will be collected here.';}
  setText('history-count',`${count} / ${state.history.length} passages`);updateSelection();
}
function updateSelection() {
  if(!state)return;
  selectedHistory=new Set([...selectedHistory].filter(i=>i<state.history.length));
  setDisabled('copy-history',!selectedHistory.size);
  document.querySelectorAll('[data-history-index]').forEach(input=>{input.checked=selectedHistory.has(Number(input.dataset.historyIndex));input.closest('tr').classList.toggle('selected',input.checked);});
  const item=state.history[[...selectedHistory][0]];
  setText('detail-source',item?.source||'Select a dialogue to read the full passage.');setText('detail-translation',item?.translation||'');
  $('detail-pair').classList.toggle('hidden',!item);setText('detail-pair',item?.pair||'');
}
function setup(initial) {
  catalog=initial.languages;
  for(const [id,auto] of [['source-languages',true],['target-languages',false]]) {
    const list=$(id);list.replaceChildren();if(auto)list.append(new Option('Auto detect','Auto detect'));
    catalog.forEach(item=>{const option=el('option');option.value=item.name;option.label=item.code;list.append(option);});
  }
  applyState(initial.state);document.documentElement.dataset.ready='true';
}
window.RVControls.enhance(id=>[
  ...(id==='source-language'?[{label:'Auto detect',value:'auto',code:'AUTO'}]:[]),
  ...(state?.provider==='argos'?state.local_language_choices||[]:catalog).map(item=>({label:item.name,value:item.code,code:item.code.toUpperCase()}))
]);
if(window.qt && window.QWebChannel) {
  new QWebChannel(qt.webChannelTransport,channel=>{
    bridge=channel.objects.studio;
    bridge.stateChanged.connect(payload=>applyState(JSON.parse(payload)));
    bridge.bootstrap(payload=>setup(JSON.parse(payload)));
  });
} else {
  document.documentElement.dataset.ready='preview';
  $('connection-label').textContent='Design preview';$('status-message').textContent='Offline design preview · open the .exe for desktop actions.';
  document.querySelectorAll('[data-action],[data-setting],#translate-sample,#copy-history,#copy-latest,#copy-sample').forEach(n=>n.disabled=true);
  window.RVControls.sync();
}
