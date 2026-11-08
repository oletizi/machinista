// SPDX-License-Identifier: GPL-3.0-or-later
// Fixed, model-specific output allowlists. No arbitrary HID or feature writes.
function reports(device,kind){const list=[];const visit=c=>{list.push(...c[kind]||[]);for(const child of c.children||[])visit(child);};for(const c of device.collections||[])visit(c);return list;}
const size=r=>(r.items||[]).reduce((n,i)=>n+i.reportSize*i.reportCount,0)/8;
async function bounded(p){let timer;try{return await Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('HID output timed out. Reconnect the controller.')),4000);})]);}finally{clearTimeout(timer);}}
function target(profile,devices,rid,bytes,kind='outputReports'){
 const matches=[...new Set(devices.map(e=>e.device))].filter(d=>d.vendorId===0x17cc&&profile.product_ids.includes(d.productId)&&reports(d,kind).some(r=>r.reportId===rid&&size(r)===bytes));
 if(matches.length!==1)throw new Error(`Output 0x${rid.toString(16)} requires one compatible HID interface (${matches.length} found). Add its HID interface or mark it untested.`);return matches[0];
}
const savedLights=new Map();
export async function enableBacklight(profile,devices){
 if(profile.id!=='maschine_mk2')return;
 for(const rid of [0xf8,0xf9]){
  const d=target(profile,devices,rid,10,'featureReports'),key=rid;
  const view=await bounded(d.receiveFeatureReport(rid)),data=new Uint8Array(view.buffer,view.byteOffset,view.byteLength).slice();
  if(data.length!==11||data[0]!==rid||data[1]!==0||data[2]!==1||data[3]!==64||data[4]!==0||data[8]>100||data[9]>100)throw new Error('Unexpected MK2 display settings; backlight was not changed.');
  if(!savedLights.has(key))savedLights.set(key,{device:d,data:data.slice()});
  data[8]=85;if(data[9]<10)data[9]=50;
  await bounded(d.sendFeatureReport(rid,data.subarray(1)));
 }
}
export async function restoreBacklight(){const entries=[...savedLights];savedLights.clear();for(const [,r] of entries)try{await bounded(r.device.sendFeatureReport(r.data[0],r.data.subarray(1)));}catch{} }
export function ledInventory(profile){return profile.led_tests||[];}
export async function clearLeds(profile,devices){for(const b of profile.led_banks||[]){const d=target(profile,devices,b.report_id,b.size-1);await bounded(d.sendReport(b.report_id,new Uint8Array(b.size-1)));}}
export async function showLed(profile,devices,test){
 const known=ledInventory(profile).find(t=>t.id===test.id);if(!known)throw new Error('Unknown LED test.');
 await clearLeds(profile,devices);
 const b=profile.led_banks.find(b=>b.report_id===known.bank),d=target(profile,devices,b.report_id,b.size-1),data=new Uint8Array(b.size-1);
 for(const offset of [known.offset,...known.extra_offsets]){if(offset<1||offset>=b.size)throw new Error('Invalid LED address.');data[offset-1]=known.value;}
 await bounded(d.sendReport(b.report_id,data));return {transport:'hid',report_id:b.report_id,offset:known.offset,value:known.value};
}
export function sanitizeLeds(input,profile){
 if(input===undefined)return [];if(!Array.isArray(input)||input.length>1024)throw new Error('Invalid LED observations.');const seen=new Set();
 // Old JAM exports included padding bytes as unsent LED probes.
 return input.filter(r=>!(profile.id==='maschine_jam'&&r.sent===false&&
  /^led_(80_(5[4-9]|6[0-5])|82_89)_observe$/.test(r.id))).map(r=>{
  // Preserve historical Studio probe files, without treating them as confirmed.
  if(!r.id&&profile.id==='maschine_studio'&&Number.isInteger(r.bank)&&Number.isInteger(r.offset)&&profile.led_banks?.some(b=>b.report_id===r.bank&&r.offset>0&&r.offset<b.size)&&typeof r.observed==='string'&&r.observed.length<=120)return {bank:r.bank,offset:r.offset,observed:r.observed};
  const t=ledInventory(profile).find(t=>t.id===r.id);
  if(!t||seen.has(r.id)||!['confirmed','failed','not_tested','blocked'].includes(r.status)||typeof r.observed!=='string'||r.observed.length>120||typeof (r.color||'')!=='string'||(r.color||'').length>30||typeof (r.note||'')!=='string'||(r.note||'').length>300)throw new Error('Invalid LED observation.');
  seen.add(r.id);if(r.status==='confirmed'&&(!r.observed.trim()||r.sent!==true))throw new Error('LED confirmation needs a visible observation and successful output.');
  return {id:t.id,bank:t.bank,offset:t.offset,value:t.value,status:r.status,observed:r.observed,color:r.color||'',note:r.note||'',sent:r.sent===true};
 });
}
export function ledCoverage(report,profile){const tests=ledInventory(profile),rows=report.leds||[],confirmed=tests.filter(t=>rows.some(r=>r.id===t.id&&r.status==='confirmed')).length;return {total:tests.length,confirmed,available:tests.length>0,complete:!report.demo&&tests.length>0&&confirmed===tests.length};}
