// SPDX-License-Identifier: GPL-3.0-or-later
// Shared data-only validation for browser exports.
import {sanitizeDisplayChecks,displayCoverage} from './displays.mjs?v=8';
import {sanitizeLeds,ledCoverage} from './outputs.mjs?v=8';
export const MAX_BYTES = 8 * 1024 * 1024;
export const FORMAT = 'Machinista-controller-survey';
const assert = (yes, message) => { if (!yes) throw new Error(message); };
const text = (v, n) => typeof v === 'string' && v.length <= n && !/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v);
export function stepsFor(profile, extras = [], version = 3, keyboardTest = 'quick') {
  const steps = [];
  const add = (kind, name, instruction, optional = false) => steps.push({id: kind + '_' + name.toLowerCase().replace(/\+/g, ' plus ').replace(/-/g, ' minus ').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''), kind, name, instruction, optional});
  for (const name of profile.buttons) add('button', name, 'Press and release this button three times. Test only this control.');
  for (const name of profile.encoders) {if(version===1)for (const d of ['clockwise', 'counterclockwise']) add('encoder', name + ' / ' + d, 'Turn slowly ' + d + ' through several steps. Do not press.');else add('encoder',name,'Turn clockwise through a few steps, then stop. Do not press.');}
  for (const name of profile.touches) add('touch', name + ' TOUCH', 'Touch and release three times without turning.');
  for (let n=1;n<=profile.pads;n++) add('pad', 'PAD ' + n, 'Play soft, medium and firm, releasing between hits. Pad 1 is bottom left; pad 16 top right.');
  for (const name of profile.strips) add('slider', name, 'Move slowly over the whole range, then return to rest.');
  const keyNumbers=profile.keys&&version>=3&&keyboardTest==='quick'?[1,profile.keys,2]:Array.from({length:profile.keys},(_,i)=>i+1);
  for (const n of keyNumbers) add('key','KEY '+n+' FROM LEFT',version>=3&&keyboardTest==='quick'&&n===2?'Play the first black key from the left (second physical key), then release.':'Play this physical key, then release. Leave octave/transpose unchanged.');
  if (profile.pressure) for (const n of [1, Math.floor((profile.keys+1)/2), profile.keys]) add('pressure', 'AFTERTOUCH KEY ' + n + ' FROM LEFT', 'Hold this key, vary pressure, then release. Do not force the mechanism.');
  for (const name of profile.pedals) add('pedal', name, 'Operate a connected pedal. Mark untested if no pedal is available.', true);
  assert(Array.isArray(extras) && extras.length <= 64, 'Too many extra controls.');
  for (const e of extras) {
    assert(text(e.name,60) && e.name.trim() && ['button','encoder','touch','pad','slider','key','pressure','pedal'].includes(e.kind), 'Invalid extra control.');
    add(e.kind, 'EXTRA ' + e.name, 'Operate only this additional control, then release. Add separate entries for each encoder direction.');
  }
  assert(new Set(steps.map(s=>s.id)).size === steps.length, 'Duplicate control name.');
  return steps;
}
export function validateReport(input, profiles) {
  assert(input && input.format===FORMAT && input.version===2, 'Unsupported survey format.');
  const profile=profiles[input.profile_id]; assert(profile, 'Unknown controller model.');
  assert(typeof input.demo==='boolean' && typeof input.layout_audited==='boolean', 'Missing test markers.');
  const d=input.device;
  assert(d && d.vendor_id===0x17cc && Number.isInteger(d.product_id) && d.product_id>=0 && d.product_id<=65535, 'Invalid USB identity.');
  assert(!profile.product_ids.length || profile.product_ids.includes(d.product_id), 'USB product does not match the chosen model.');
  assert(Array.isArray(d.interfaces) && d.interfaces.length>0 && d.interfaces.length<=8, 'Invalid interfaces.');
  const interfaces=d.interfaces.map(i=>{assert(text(i.id,32) && /^(hid|midi)\d+$/.test(i.id), 'Invalid interface ID.');assert(i.fingerprint===undefined||(text(i.fingerprint,512)&&/^[0-9:;]*$/.test(i.fingerprint)), 'Invalid interface descriptor.');return {id:i.id,transport:i.id.startsWith('midi')?'midi':'hid',...(i.fingerprint?{fingerprint:i.fingerprint}:{})};});
  assert(new Set(interfaces.map(i=>i.id)).size===interfaces.length, 'Duplicate interface.');
  const ids=new Set(interfaces.map(i=>i.id)), extras=input.extra_controls || [];
  const inventoryVersion=input.checklist_version??1;assert([1,2,3].includes(inventoryVersion),'Unsupported checklist version.');
  const keyboardTest=inventoryVersion>=3?(input.keyboard_test??'quick'):'full';assert(['quick','full'].includes(keyboardTest),'Invalid keyboard test mode.');
  const steps=stepsFor(profile,extras,inventoryVersion,keyboardTest), known=new Map(steps.map(s=>[s.id,s])), seen=new Set();
  assert(Array.isArray(input.controls) && input.controls.length<=steps.length, 'Invalid control list.');
  const controls=input.controls.map(r=>{
    const s=known.get(r.id);
    assert(s && !seen.has(r.id) && r.kind===s.kind && r.name===s.name, 'Unknown or duplicate control.'); seen.add(r.id);
    assert(['captured','skipped','confirmed'].includes(r.status), 'Invalid status.');
    assert(Array.isArray(r.frames) && r.frames.length<=320, 'Too many raw frames.');
    let last=-1;
    const frames=r.frames.map(f=>{
      assert(Number.isInteger(f.ms) && f.ms>=last && f.ms<=10000 && ids.has(f.interface) && typeof f.hex==='string' && /^(?:[0-9a-f]{2}){1,512}$/i.test(f.hex), 'Invalid raw frame.');last=f.ms;
      return {ms:f.ms,interface:f.interface,hex:f.hex.toLowerCase()};
    });
    assert(text(r.note || '',300), 'Observation is too long.');
    // Claimed mappings are intentionally discarded. Maintainers derive them from raw evidence.
    return {id:s.id,name:s.name,kind:s.kind,status:r.status==='skipped'?'skipped':'captured',frames,tester_confirmed:r.tester_confirmed===true,note:r.note || '',...(r.detection&&typeof r.detection.signature==='string'&&r.detection.signature.length<=180&&/^[a-zA-Z0-9:._-]+$/.test(r.detection.signature)?{detection:{method:'automatic',signature:r.detection.signature}}:{})};
  });
  const out={format:FORMAT,version:2,checklist_version:inventoryVersion,keyboard_test:keyboardTest,profile_id:profile.id,demo:input.demo,layout_audited:input.layout_audited,extra_controls:extras.map(e=>({name:e.name,kind:e.kind})),device:{vendor_id:0x17cc,product_id:d.product_id,name:profile.name,identity_verified:input.device.identity_verified===true,interfaces},controls,leds:sanitizeLeds(input.leds,profile),displays:{},display_checks:sanitizeDisplayChecks(input.display_checks,profile),tool:{name:'Machinista Browser Survey',version:1}};
  if(input.legacy_controls!==undefined){assert(inventoryVersion>=2&&Array.isArray(input.legacy_controls)&&input.legacy_controls.length<=profile.encoders.length*2,'Invalid legacy captures.');out.legacy_controls=validateReport({...input,checklist_version:1,controls:input.legacy_controls,legacy_controls:undefined},profiles).controls;}
  assert(new TextEncoder().encode(JSON.stringify(out)).length<=MAX_BYTES, 'Survey is too large.');
  return out;
}
export function coverage(report, profiles) {
  const steps=stepsFor(profiles[report.profile_id],report.extra_controls,report.checklist_version??1,report.keyboard_test??'quick'), rows=new Map(report.controls.map(r=>[r.id,r]));
  const done=s=>{const r=rows.get(s.id);return r && r.status!=='skipped' && r.tester_confirmed && r.frames.some(f=>f.ms>=1000 && f.ms<5000);};
  const required=steps.filter(s=>!s.optional), missing=required.filter(s=>!done(s)).map(s=>s.name);
  return {total:required.length,recorded:required.length-missing.length,missing,optional_untested:steps.filter(s=>s.optional&&!done(s)).map(s=>s.name),
    leds:ledCoverage(report,profiles[report.profile_id]),displays:displayCoverage(report,profiles[report.profile_id]),physical_check_complete:!report.demo && !missing.length && report.layout_audited,driver_ready:false};
}
export function compactFrames(frames) {
  // Preserve low-rate button/key events; decimate continuous pad traffic separately.
  const low=frames.filter(f=>!f.interface.startsWith('hid') || !f.hex.startsWith('20'));
  const high=frames.filter(f=>f.interface.startsWith('hid') && f.hex.startsWith('20'));
  const sample=(a,n)=>n<=0?[]:n===1?a.slice(0,1):a.length<=n?a:a.filter((_,i)=>i===0||i===a.length-1||Math.floor(i*(n-2)/(a.length-2))!==Math.floor((i-1)*(n-2)/(a.length-2))).slice(0,n-1).concat(a.at(-1));
  const l=sample(low,Math.min(240,low.length)), h=sample(high,320-l.length);
  return [...l,...h].sort((a,b)=>a.ms-b.ms).slice(0,320);
}
export function matchedMidiPorts(ports, profile) {
  const words=profile.name.toLowerCase().replace(/komplete |kontrol |controller mode|[+\/]/g,' ').split(/\s+/).filter(w=>w && w!=='mk1');
  return ports.filter(p=>{const name=p.name.toLowerCase();return words.every(w=>name.includes(w)) || (profile.family==='Komplete Kontrol' && words.some(w=>/^[sam]\d+$/.test(w)&&name.includes(w)));});
}

export function emailDraft(address, model, summary) {
  assert(typeof address==='string' && /^[A-Za-z0-9.!#$%&'*+\/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(address) && address.length<=254, 'The submission email address is not configured yet. Download your JSON instead.');
  const subject='Machinista controller survey: '+model;
  const body=`Controller: ${model}\n\n${summary.recorded}/${summary.total} required actions recorded.\n\nI agree to publish the attached controller measurements under GPL-3.0-or-later.\n\nPlease attach the downloaded .json file before sending.\n\nOptional observations:\n`;
  return 'mailto:'+encodeURIComponent(address)+'?subject='+encodeURIComponent(subject)+'&body='+encodeURIComponent(body);
}

export function availableProfiles(profiles) { return Object.values(profiles).filter(p=>p.survey_required===true||p.survey_test===true); }

export function upgradeChecklist(input,profiles){
 const report=validateReport(input,profiles);if(report.checklist_version>=2)return report;
 const modern=stepsFor(profiles[report.profile_id],report.extra_controls,2),oldEncoders=report.controls.filter(r=>r.kind==='encoder');
 report.legacy_controls=oldEncoders;report.controls=report.controls.filter(r=>r.kind!=='encoder');
 for(const step of modern.filter(s=>s.kind==='encoder')){
  const matches=oldEncoders.filter(r=>r.name===step.name+' / clockwise'||r.name===step.name+' / counterclockwise');
  const chosen=matches.find(r=>r.tester_confirmed&&r.name.endsWith('/ clockwise'))||matches.find(r=>r.tester_confirmed)||matches[0];
  if(chosen)report.controls.push({...chosen,id:step.id,name:step.name,note:('Legacy capture: '+chosen.name+'. '+chosen.note).slice(0,300)});
 }
 report.checklist_version=2;return validateReport(report,profiles);
}
