'use strict';
window.RVControls=(()=>{
  const widgets=[];let active=null,serial=0;
  const node=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  function chevron(){const s=document.createElementNS('http://www.w3.org/2000/svg','svg');s.setAttribute('viewBox','0 0 20 20');s.setAttribute('class','rv-chevron');s.setAttribute('aria-hidden','true');const p=document.createElementNS(s.namespaceURI,'path');p.setAttribute('d','m5 7 5 5 5-5');p.setAttribute('fill','none');p.setAttribute('stroke','currentColor');p.setAttribute('stroke-width','1.5');s.append(p);return s;}
  class Select {
    constructor(input,languageChoices=null){
      this.input=input;this.language=!!languageChoices;this.choices=languageChoices;this.id='rv-list-'+(++serial);this.index=0;this.items=[];
      this.wrapper=node('div',this.language?'rv-select rv-language':'rv-select');input.before(this.wrapper);this.wrapper.append(input);
      if(this.language){input.removeAttribute('list');input.setAttribute('role','combobox');input.setAttribute('aria-autocomplete','list');this.trigger=input;this.arrow=node('button');this.arrow.type='button';this.arrow.setAttribute('aria-label','Show '+(input.id==='source-language'?'source':'target')+' languages');this.arrow.tabIndex=-1;this.arrow.append(chevron());this.wrapper.append(this.arrow);this.arrow.addEventListener('click',()=>this.popup?this.close():this.open(''));input.addEventListener('focus',()=>{if(!this.suppressOpen)this.open('');});input.addEventListener('input',()=>this.open(input.value));}
      else{input.classList.add('rv-select-native');input.tabIndex=-1;input.setAttribute('aria-hidden','true');this.trigger=node('button','rv-select-trigger');this.trigger.type='button';this.trigger.id=(input.id||this.id)+'-trigger';this.value=node('span','rv-select-value');this.trigger.append(this.value,chevron());this.wrapper.append(this.trigger);const label=input.id?document.querySelector(`label[for="${input.id}"]`):null;if(label)label.htmlFor=this.trigger.id;this.trigger.setAttribute('aria-label',input.getAttribute('aria-label')||label?.textContent||input.closest('label')?.querySelector('strong,span')?.textContent||'Choose an option');this.trigger.addEventListener('click',()=>this.popup?this.close():this.open(''));input.addEventListener('change',()=>this.sync());}
      this.trigger.setAttribute('aria-controls',this.id);this.trigger.setAttribute('aria-haspopup','listbox');this.trigger.setAttribute('aria-expanded','false');
      this.trigger.addEventListener('keydown',event=>this.key(event));this.sync();widgets.push(this);
    }
    options(){return this.language?this.choices():[...this.input.options].filter(o=>!o.disabled).map(o=>({value:o.value,label:o.textContent,code:''}));}
    sync(){
      this.trigger.disabled=this.input.disabled;if(this.arrow)this.arrow.disabled=this.input.disabled;
      if(!this.language){const selected=this.input.selectedOptions[0];this.value.textContent=selected?.textContent||'No options available';this.trigger.title=this.value.textContent;}
      if(this.popup&&this.input.disabled)this.close();
    }
    open(query=''){
      if(this.input.disabled)return;
      if(active&&active!==this)active.close();active=this;
      if(!this.popup){
        this.popup=node('div','rv-select-popup');this.popup.addEventListener('pointerdown',event=>event.stopPropagation());
        if(!this.language&&this.options().length>6){this.search=node('input','rv-select-search');this.search.type='search';this.search.placeholder='Search options…';this.search.setAttribute('aria-label','Search '+this.trigger.getAttribute('aria-label'));this.search.addEventListener('input',()=>this.render(this.search.value));this.search.addEventListener('keydown',event=>this.key(event));this.popup.append(this.search);}
        this.list=node('div','rv-select-list');this.list.id=this.id;this.list.setAttribute('role','listbox');this.list.setAttribute('aria-label',this.language?'Languages':this.trigger.getAttribute('aria-label'));this.popup.append(this.list);document.body.append(this.popup);this.trigger.setAttribute('aria-expanded','true');
      }
      this.render(query);this.position();
      if(this.search&&document.activeElement!==this.search){this.search.focus();this.search.value=query;}
    }
    render(query){
      const q=query.toLocaleLowerCase().trim();this.items=this.options().filter(o=>!q||`${o.label} ${o.code||o.value}`.toLocaleLowerCase().includes(q));
      if(this.language&&q&&!this.items.length)this.items=[{value:query,label:'Use “'+query+'”',code:'Custom',custom:true}];
      this.list.replaceChildren();
      const current=this.language?this.input.value:this.input.value;
      this.index=Math.max(0,this.items.findIndex(o=>o.value===current||o.label===current));
      if(!this.items.length){this.list.append(node('div','rv-select-empty','No matching options'));return;}
      this.items.forEach((option,i)=>{
        const item=node('button','rv-option');item.type='button';item.id=this.id+'-'+i;item.tabIndex=-1;item.setAttribute('role','option');item.setAttribute('aria-selected',String(option.value===current||option.label===current));item.append(node('span','rv-option-label',option.label));item.append(node('span','rv-option-code',option.value===current||option.label===current?'✓':option.code||''));
        item.addEventListener('pointerdown',event=>event.preventDefault());item.addEventListener('click',()=>this.choose(i));item.addEventListener('pointermove',()=>{this.index=i;this.focused(false);});this.list.append(item);
      });this.focused(false);
    }
    focused(scroll=true){
      const rows=[...this.list.querySelectorAll('.rv-option')];rows.forEach((n,i)=>n.classList.toggle('focused',i===this.index));const row=rows[this.index];
      if(row){this.trigger.setAttribute('aria-activedescendant',row.id);if(this.search)this.search.setAttribute('aria-activedescendant',row.id);if(scroll)row.scrollIntoView({block:'nearest'});}
    }
    choose(index){
      const option=this.items[index];if(!option)return;
      this.input.value=this.language?(option.custom?option.value:option.label):option.value;
      this.input.dispatchEvent(new Event('change',{bubbles:true}));this.close();this.suppressOpen=true;this.trigger.focus();this.suppressOpen=false;this.sync();
    }
    key(event){
      if(event.key==='Escape'&&this.popup){event.preventDefault();event.stopPropagation();this.close();this.trigger.focus();return;}
      if(event.key==='Tab'){this.close();return;}
      if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
        event.preventDefault();if(!this.popup){this.open('');return;}
        this.index=event.key==='Home'?0:event.key==='End'?this.items.length-1:Math.max(0,Math.min(this.items.length-1,this.index+(event.key==='ArrowDown'?1:-1)));this.focused();return;
      }
      if((event.key==='Enter'||(!this.language&&event.key===' '))){event.preventDefault();if(!this.popup)this.open('');else this.choose(this.index);}
    }
    position(){
      if(!this.popup)return;const r=this.wrapper.getBoundingClientRect(),width=Math.min(Math.max(r.width,this.language?240:220),innerWidth-20);
      this.popup.style.width=width+'px';this.popup.style.left=Math.max(10,Math.min(r.left,innerWidth-width-10))+'px';
      const below=innerHeight-r.bottom-12,above=r.top-12,up=below<180&&above>below,available=Math.max(100,Math.min(320,(up?above:below)-12));
      this.list.style.maxHeight=Math.max(70,available-(this.search?46:12))+'px';
      this.popup.style.top=up?'auto':Math.max(8,r.bottom+6)+'px';this.popup.style.bottom=up?Math.max(8,innerHeight-r.top+6)+'px':'auto';
    }
    close(){
      this.popup?.remove();this.popup=null;this.search=null;this.list=null;this.trigger.setAttribute('aria-expanded','false');this.trigger.removeAttribute('aria-activedescendant');if(active===this)active=null;
    }
  }
  document.addEventListener('pointerdown',event=>{if(active&&!active.wrapper.contains(event.target)&&!active.popup?.contains(event.target))active.close();});
  window.addEventListener('resize',()=>active?.position());
  return {
    enhance(languageProvider){document.querySelectorAll('select').forEach(n=>new Select(n));for(const id of ['source-language','target-language'])new Select(document.getElementById(id),()=>languageProvider(id));},
    sync(){widgets.forEach(w=>w.sync());},close(){active?.close();}
  };
})();
