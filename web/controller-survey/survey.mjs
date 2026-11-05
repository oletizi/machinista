// SPDX-License-Identifier: GPL-3.0-or-later
import {FORMAT, MAX_BYTES, stepsFor, validateReport, coverage, compactFrames, matchedMidiPorts,emailDraft} from './core.mjs';
const $=id=>document.getElementById(id), profiles=await (await fetch('catalog.json')).json();
const config=await (await fetch('config.json')).json();
let report=null, devices=[], midi=null, selectedPorts=new Set(), capture=null, latest=new Map(), stepIndex=0, db=null, saveQueue=Promise.resolve();
const hex=b=>Array.from(b,n=>n.toString(16).padStart(2,'0')).join('');
const notify=s=>{$('message').textContent=s;};
const profile=()=>profiles[$('model').value];
const steps=()=>stepsFor(profile(),report?.extra_controls||[]);
const current=()=>steps()[stepIndex];
const row=()=>report?.controls.find(r=>r.id===current()?.id);
const safe=fn=>async(...args)=>{try{await fn(...args);}catch(e){notify(e.message || String(e));}};
for(const p of Object.values(profiles)){const o=document.createElement('option');o.value=p.id;o.textContent=p.name;$('model').append(o);}
function blank(demo,device){return {format:FORMAT,version:2,profile_id:profile().id,demo,layout_audited:false,extra_controls:[],device,controls:[],leds:[],displays:{},tool:{name:'Machinista Browser Survey',version:1}};}
async function persist(){if(!db||!report)return;const copy=structuredClone(report);saveQueue=saveQueue.catch(()=>{}).then(()=>new Promise((resolve,reject)=>{const tx=db.transaction('state','readwrite');tx.objectStore('state').put(copy,'survey');tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);}));try{await saveQueue;}catch{notify('Browser storage is unavailable. Download a JSON copy to keep your progress.');}}
function setInterface(id,fingerprint){if(!report.device.interfaces.some(i=>i.id===id)){if(report.device.interfaces.length>=8)throw new Error('At most eight inputs can be recorded.');report.device.interfaces.push({id,...(fingerprint?{fingerprint}:{})});}}
function receive(id,bytes){
 if(!report || bytes.length===0 || bytes.length>512)return;
 const h=hex(bytes), key=id+':'+(id.startsWith('midi')?bytes[0]&0xf0:bytes[0])+':'+bytes.length;
 latest.set(key,{interface:id,hex:h});
 if(!capture)return;
 const ms=Math.round(performance.now()-capture.started); if(ms>6000)return;
 const prev=capture.last.get(key);
 // Ignore unchanged continuous HID reports, but retain repeated MIDI attacks.
 if(id.startsWith('hid') && prev?.hex===h)return;
 if(bytes[0]===0x20 && id.startsWith('hid') && prev && ms-prev.ms<12)return;
 capture.last.set(key,{hex:h,ms});
 if(capture.frames.length>=3000){capture.overflow=true;return;}
 capture.frames.push({ms,interface:id,hex:h});
}
function draw(){
 const p=profile(), list=steps(), s=list[stepIndex];
 $('inventory').textContent=`${p.buttons.length} buttons · ${p.encoders.length} rotary controls (both directions) · ${p.pads} pads · ${p.keys} keys. Touch sensors, strips and pedal sockets have separate checks.`;
 $('manual').href=p.sources[0];$('step').replaceChildren();
 list.forEach((s,i)=>{const o=document.createElement('option');o.value=i;const r=report?.controls.find(r=>r.id===s.id);o.textContent=(r?.tester_confirmed?'✓ ':r?.status==='skipped'?'— ':'')+s.name+(s.optional?' (optional)':'');$('step').append(o);});$('step').value=stepIndex;
 $('kind').textContent=s.kind.toUpperCase();$('control').textContent=s.name;$('instruction').textContent=s.instruction;$('count').textContent=`${stepIndex+1} / ${list.length}`;
 $('note').value=row()?.note||'';$('audit').checked=report?.layout_audited||false;
 $('connection').textContent=report?(report.demo?'DEMO · no hardware measurements':`${report.device.name} · ${devices.length} HID interface(s) open · ${selectedPorts.size} MIDI input(s) selected`):'Not connected';
 $('model').disabled=!!report;$('connect').disabled=!!report;$('demo').disabled=!!report;
 $('more').disabled=!report||report.demo||!!capture;$('record').disabled=!report||!!capture||(!report.demo&&!devices.length);$('confirm').disabled=!row()||row().status==='skipped'||!!capture||!row().frames.some(f=>f.ms>=1000&&f.ms<5000);
 for(const id of ['skip','step','add','audit','resume','download','submit','discord','midi'])$(id).disabled=!!capture || (!report && !['resume','midi'].includes(id));
 $('evidence').textContent=row()?`${row().status==='skipped'?'Untested':row().tester_confirmed?'Action confirmed by tester':'Recording awaiting your confirmation'} · ${row().frames.length} raw frames${row().note?' · '+row().note:''}`:'No recording for this control yet.';
 $('visual').replaceChildren();
 if(s.kind==='pad'&&p.pads===16){const grid=document.createElement('div');grid.className='padgrid';for(let r=3;r>=0;r--)for(let c=1;c<=4;c++){const n=r*4+c,t=document.createElement('span');t.className='tile'+(s.name==='PAD '+n?' active':'');t.textContent=n;grid.append(t);}$('visual').append(grid);}
 else if(s.kind==='key'){for(let n=1;n<=p.keys;n++){const t=document.createElement('span');t.className='tile keytile'+(s.name==='KEY '+n+' FROM LEFT'?' active':'');$('visual').append(t);}}
 else {const t=document.createElement('span');t.className='symbol';t.textContent=s.kind==='encoder'?(s.name.includes('counterclockwise')?'↶':'↷'):s.kind==='slider'?'↔':s.kind==='touch'?'◎':s.kind==='pressure'?'⇓':'▣';$('visual').append(t);}
 if(midi)for(const checkbox of $('ports').querySelectorAll('input'))checkbox.disabled=!!capture||!report||report.demo;
 $('missing').replaceChildren();if(report){const c=coverage(report,profiles);$('coverage').textContent=`${report.demo?'DEMO · ':''}${c.recorded} / ${c.total} required actions recorded and confirmed. ${c.physical_check_complete?'Physical input check finished.':'Input check incomplete.'} Driver mappings still need review. LEDs and displays: not tested.`;for(const n of c.missing){const li=document.createElement('li');li.textContent=n;$('missing').append(li);}}
}
async function detach(){if(capture){clearInterval(capture.timer);capture=null;notify('Recording cancelled by disconnect. Repeat this control.');}for(const d of devices){d.device.removeEventListener('inputreport',d.listener);try{await d.device.close();}catch{}}devices=[];if(midi)for(const p of midi.inputs.values())p.onmidimessage=null;selectedPorts.clear();latest.clear();draw();}
async function openHid(additional=false){
 if(!navigator.hid)throw new Error('WebHID is unavailable. Open this page in desktop Chrome or Edge.');
 const filters=[{vendorId:0x17cc,...(additional?{productId:report.device.product_id}:{})}];
 const found=await navigator.hid.requestDevice({filters});if(!found.length)return;
 const first=found[0], p=profile();
 if(p.product_ids.length&&!p.product_ids.includes(first.productId))throw new Error('The USB device does not match the chosen model. Choose the correct model first.');
 if(additional&&first.productId!==report.device.product_id)throw new Error('Choose an interface of the same controller.');
 const old=report;
 try{
  if(!report)report=blank(false,{vendor_id:0x17cc,product_id:first.productId,name:p.name,identity_verified:p.product_ids.includes(first.productId),interfaces:[]});
  for(const device of found){if(devices.some(d=>d.device===device))continue;if(device.productId!==report.device.product_id)continue;if(devices.length>=4)throw new Error('At most four HID interfaces are supported.');const fingerprint=(device.collections||[]).map(c=>[c.usagePage,c.usage,...(c.inputReports||[]).map(r=>r.reportId)].join(':')).join(';').slice(0,512);
   const saved=report.device.interfaces.filter(i=>i.id.startsWith('hid')&&i.fingerprint===fingerprint&&!devices.some(d=>d.id===i.id));
   if(saved.length>1)throw new Error('These saved HID interfaces cannot be distinguished safely. Start a fresh session for this controller.');
   const id=saved[0]?.id || 'hid'+Array.from({length:4},(_,i)=>i).find(i=>!report.device.interfaces.some(r=>r.id==='hid'+i));
   if(id==='hidundefined')throw new Error('No free HID interface slot.');
   await device.open();
   const listener=e=>receive(id,new Uint8Array([e.reportId,...new Uint8Array(e.data.buffer,e.data.byteOffset,e.data.byteLength)]));
   device.addEventListener('inputreport',listener);devices.push({device,id,listener});setInterface(id,fingerprint);
  }
 }catch(e){await detach();report=old;throw e;}
 notify('USB connected. If some buttons send no data, try Add HID interface. MIDI keybeds may also need Find MIDI inputs.');await persist();draw();
}
$('connect').onclick=safe(()=>openHid());$('more').onclick=safe(()=>openHid(true));
$('disconnect').onclick=safe(async()=>{await persist();await detach();if(report?.controls.length && !confirm('End this session? Download a copy first if you need it. A browser recovery copy remains until the next session is saved.'))return;report=null;stepIndex=0;draw();});
if(navigator.hid)navigator.hid.addEventListener('disconnect',safe(async e=>{if(devices.some(d=>d.device===e.device)){await detach();notify('USB disconnected. Download your progress, then resume and reconnect the same controller.');}}));
$('model').onchange=()=>{stepIndex=0;draw();};$('step').onchange=()=>{stepIndex=Number($('step').value);draw();};
$('demo').onclick=()=>{report=blank(true,{vendor_id:0x17cc,product_id:profile().product_ids[0]||0,name:profile().name,identity_verified:false,interfaces:[{id:'hid0'}]});draw();notify('Demo mode. These measurements cannot be submitted as real hardware data.');};
$('record').onclick=()=>{
 const s=current();if(!report||capture)return;
 capture={step:s,started:performance.now(),frames:[...latest.values()].map(f=>({...f,ms:0})),last:new Map(),overflow:false};$('progress').value=0;draw();
 capture.timer=setInterval(()=>{
  if(!capture)return;const elapsed=(performance.now()-capture.started)/1000;$('progress').value=elapsed;
  $('phase').textContent=elapsed<1?'Keep all controls still…':elapsed<5?'NOW · '+s.instruction:'Release · keep still…';
  if(report.demo && elapsed>1 && elapsed<5 && capture.frames.length<20){const n=capture.frames.length;capture.frames.push({ms:Math.round(elapsed*1000),interface:'hid0',hex:'0100'+(n%2?'04':'00')});}
  if(elapsed>=6){const c=capture;clearInterval(c.timer);capture=null;const r={id:s.id,name:s.name,kind:s.kind,status:'captured',tester_confirmed:false,frames:compactFrames(c.frames),note:c.overflow?'Capture exceeded rate limit; repeat more slowly.':''};report.controls=report.controls.filter(r=>r.id!==s.id);report.controls.push(r);report.layout_audited=false;$('phase').textContent=c.overflow?'Too much data · repeat this control':r.frames.length?'Recorded · confirm only if you performed the requested action':'No input data · check interfaces, MIDI ports or app ownership';persist();draw();}
 },80);
};
$('confirm').onclick=safe(async()=>{if(!row()||!row().frames.some(f=>f.ms>=1000&&f.ms<5000))return;row().tester_confirmed=true;row().note=$('note').value;stepIndex=Math.min(stepIndex+1,steps().length-1);$('phase').textContent='Ready when you are';draw();await persist();});
$('skip').onclick=safe(async()=>{const s=current();report.controls=report.controls.filter(r=>r.id!==s.id);report.controls.push({id:s.id,name:s.name,kind:s.kind,status:'skipped',tester_confirmed:false,frames:[],note:$('note').value});report.layout_audited=false;stepIndex=Math.min(stepIndex+1,steps().length-1);draw();await persist();});
$('note').onchange=()=>{if(row()){row().note=$('note').value;persist();}};
$('audit').onchange=()=>{if(report){report.layout_audited=$('audit').checked;persist();draw();}};
$('add').onclick=safe(async()=>{const extra={name:$('extra-name').value.trim(),kind:$('extra-kind').value};const next=[...report.extra_controls,extra];stepsFor(profile(),next);report.extra_controls=next;report.layout_audited=false;stepIndex=steps().length-1;$('extra-name').value='';await persist();draw();});
$('midi').onclick=safe(async()=>{
 if(!navigator.requestMIDIAccess)throw new Error('Web MIDI is unavailable in this browser.');
 midi=await navigator.requestMIDIAccess({sysex:false});renderPorts();midi.onstatechange=()=>{for(const id of [...selectedPorts])if(!midi.inputs.has(id)){selectedPorts.delete(id);notify('A MIDI input disconnected. Repeat any interrupted capture.');}renderPorts();};
});
function renderPorts(){
 $('ports').replaceChildren();const ports=[...midi.inputs.values()], matches=matchedMidiPorts(ports,profile());
 if(!ports.length){$('ports').textContent='No USB-MIDI inputs exposed by the operating system.';return;}
 ports.forEach(port=>{const l=document.createElement('label'),c=document.createElement('input');c.type='checkbox';c.checked=selectedPorts.has(port.id);c.disabled=!report||report.demo||!!capture;l.className='check';l.append(c,document.createTextNode(port.name+(matches.includes(port)?' · suggested':'')));c.onchange=safe(async()=>{if(c.checked){if(selectedPorts.size>=4)throw new Error('Select at most four MIDI inputs.');const id='midi'+[...midi.inputs.values()].indexOf(port);setInterface(id);selectedPorts.add(port.id);port.onmidimessage=e=>{const b=new Uint8Array(e.data);if(b[0]<0xf0)receive(id,b);};}else{selectedPorts.delete(port.id);port.onmidimessage=null;}await persist();draw();renderPorts();});$('ports').append(l);});
}
function download(){if(!report)throw new Error('Record a controller first.');const clean=validateReport(report,profiles),blob=new Blob([JSON.stringify(clean,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='machinista-'+report.profile_id+'-'+(report.demo?'demo-':'')+Date.now()+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);return clean;}
$('download').onclick=safe(download);
$('submit').onclick=safe(async()=>{
 if(!report||report.demo)throw new Error('Demo reports cannot be submitted.');
 if(!$('consent').checked)throw new Error('Please agree to publication before preparing your email.');
 const draft=emailDraft(config.submissionEmail,profile().name,coverage(report,profiles));
 download();window.location.href=draft;
 notify('JSON downloaded. In your mail app, attach that downloaded file, then send the email. The browser cannot attach it automatically. If no mail app opens, use the address below with your webmail.');
});
$('discord').onclick=safe(()=>{
 if(!report||report.demo)throw new Error('Demo reports cannot be submitted.');
 if(!$('consent').checked)throw new Error('Please agree to publication before sharing your measurements.');
 if(!/^https:\/\/(discord\.gg\/[A-Za-z0-9-]+|discord\.com\/(channels\/\d+\/\d+|invite\/[A-Za-z0-9-]+))\/?$/.test(config.discordUrl||''))throw new Error('The Discord channel is not configured.');
 download();window.open(config.discordUrl,'_blank','noopener');notify('JSON downloaded. Join or open the Machinista server, choose #controllers, attach the downloaded .json file there, and send it. Discord sign-in may be required.');
});
$('discord').hidden=!config.discordUrl;
if(config.discordUrl)$('submit-info').append(document.createTextNode(' Discord submissions belong in #controllers. The invite may open another channel first; choose #controllers before attaching your file.'));
$('resume').onchange=safe(async()=>{const f=$('resume').files[0];if(!f)return;if(f.size>MAX_BYTES)throw new Error('The file exceeds 8 MiB.');const saved=validateReport(JSON.parse(await f.text()),profiles);if(!confirm('Resume this survey? Only reconnect the SAME physical controller and keep its settings unchanged.'))return;await detach();report=saved;$('model').value=report.profile_id;stepIndex=0;draw();notify('Progress restored. Click Add HID interface to reconnect the same controller. Re-select MIDI inputs.');});
try{db=await new Promise((resolve,reject)=>{const req=indexedDB.open('machinista-controller-lab',1);req.onupgradeneeded=()=>req.result.createObjectStore('state');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});const saved=await new Promise(resolve=>{const req=db.transaction('state').objectStore('state').get('survey');req.onsuccess=()=>resolve(req.result);req.onerror=()=>resolve(null);});if(saved && confirm('Restore your previous controller survey?')){report=validateReport(saved,profiles);$('model').value=report.profile_id;notify('Recovered progress. Reconnect the same controller with Add HID interface.');}}catch{notify('Browser recovery storage is unavailable. Download JSON regularly to save progress.');}
document.addEventListener('visibilitychange',()=>{if(document.hidden&&capture){clearInterval(capture.timer);capture=null;notify('Recording cancelled because the page was hidden. Keep this page visible and repeat.');draw();}});
$('submit-info').append(document.createTextNode(config.submissionEmail?' Send your downloaded JSON to '+config.submissionEmail+'. Prepare email opens your mail app; attach the file yourself. Webmail also works.':' The public email address has not been configured yet. You can already download your JSON.'));
window.addEventListener('beforeunload',e=>{if(capture){e.preventDefault();e.returnValue='';}});draw();
