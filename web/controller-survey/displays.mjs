// SPDX-License-Identifier: GPL-3.0-or-later
// Fixed diagnostic images only. Never accepts user-defined USB commands.
export const PATTERNS=['border','grid','levels'];
export function displayInventory(profile){ return profile.displays || []; }
// A tiny deterministic diagnostic font; no system-font rasterization involved.
const FONT={D:[30,17,17,17,17,17,30],I:[31,4,4,4,4,4,31],S:[15,16,16,14,1,1,30],P:[30,17,17,30,16,16,16],L:[16,16,16,16,16,16,31],A:[14,17,17,31,17,17,17],Y:[17,17,10,4,4,4,4],1:[4,12,4,4,4,4,14],2:[14,17,1,2,4,8,31],3:[30,1,1,14,1,1,30],4:[2,6,10,18,31,2,2],5:[31,16,16,30,1,1,30],6:[14,16,16,30,17,17,14],7:[31,1,2,4,8,8,8],8:[14,17,17,14,17,17,14]};
export function testImage(display,pattern){
 if(!PATTERNS.includes(pattern))throw new Error('Unknown diagnostic pattern.');
 const {width:w,height:h,color}=display;
 if(!Number.isInteger(w)||!Number.isInteger(h)||w*h>614400)throw new Error('Invalid diagnostic dimensions.');
 const rgb=new Uint8Array(w*h*3), scale=w>=480?5:1;
 const bars=color?[[255,0,0],[0,255,0],[0,0,255],[255,255,255],[255,136,0],[128,128,128]]:[[0,0,0],[64,64,64],[128,128,128],[255,255,255]];
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  let c=[0,0,0];
  if(pattern==='grid')c=(Math.floor(x/(color?16:4))+Math.floor(y/(color?16:4)))%2?[255,255,255]:[0,0,0];
  if(pattern==='levels'&&y>=h/2)c=bars[Math.min(bars.length-1,Math.floor(x*bars.length/w))];
  if(pattern==='border'&&(x===0||x===w-1||y===0||y===h-1))c=color?[255,136,0]:[255,255,255];
  if(!color&&pattern==='levels'&&y>=h/2){const value=c[0]>[0,128,192,64][(y%2)*2+x%2]?255:0;c=[value,value,value];}
  rgb.set(c,(y*w+x)*3);
 }
 if(pattern!=='grid'){
  const label='DISPLAY'+(display.index+1), startX=4*scale,startY=4*scale;
  for(let i=0;i<label.length;i++)for(let row=0;row<7;row++)for(let col=0;col<5;col++)if(FONT[label[i]][row]&(16>>col))for(let dy=0;dy<scale;dy++)for(let dx=0;dx<scale;dx++){
   const x=startX+i*6*scale+col*scale+dx,y=startY+row*scale+dy;if(x<w&&y<h)rgb.set([255,255,255],(y*w+x)*3);
  }
 }
 return rgb;
}
export function monoPackets(display,pattern,payloadSize){
 if(!['mono-pages','mono-oled'].includes(display.protocol))throw new Error('Not a monochrome display.');
 const rgb=testImage(display,pattern),pages=new Uint8Array(display.width*display.height/8);
 for(let y=0;y<display.height;y++)for(let x=0;x<display.width;x++)if(rgb[(y*display.width+x)*3]>=128)pages[Math.floor(y/8)*display.width+x]|=1<<(y%8);
 const id=0xe0+display.index;
 if(display.protocol==='mono-oled'&&payloadSize===pages.length)return [{reportId:id,data:pages}];
 if(payloadSize!==264)throw new Error('The HID report length does not match the known display protocol. No output sent.');
 const packets=[];for(let page=0;page<display.height/8;page+=2){const data=new Uint8Array(264),view=new DataView(data.buffer);view.setUint16(2,page,true);view.setUint16(4,display.width,true);view.setUint16(6,2,true);data.set(pages.subarray(page*display.width,(page+2)*display.width),8);packets.push({reportId:id,data});}return packets;
}
export function colorPacket(display,pattern){
 if(display.protocol!=='ni-color'||display.width!==480||display.height!==272||![0,1].includes(display.index))throw new Error('Unknown color display protocol.');
 const rgb=testImage(display,pattern),packet=new Uint8Array(480*272*2+32),view=new DataView(packet.buffer);
 packet.set([0x84,0,display.index,0x60]);view.setUint16(12,480);view.setUint16(14,272);view.setUint32(16,480*272/2);
 for(let i=0;i<480*272;i++){const r=rgb[i*3],g=rgb[i*3+1],b=rgb[i*3+2];view.setUint16(20+i*2,((b>>3)<<11)|((g>>2)<<5)|(r>>3));}
 packet.set([3,0,0,0,0x40,0,0,0],packet.length-8);return packet;
}
function reports(device){const all=[];const visit=c=>{all.push(...(c.outputReports||[]));for(const child of c.children||[])visit(child);};for(const c of device.collections||[])visit(c);return all;}
function reportSize(r){return (r.items||[]).reduce((n,i)=>n+i.reportSize*i.reportCount,0)/8;}
function checkIdentity(profile,device){
 if(device.vendorId!==0x17cc)throw new Error('Not an NI controller.');
 if(profile.product_ids.length){if(!profile.product_ids.includes(device.productId))throw new Error('USB model does not match.');}
 else{const model=profile.id.match(/kk_([am]\d+)/)?.[1];if(!model||!(device.productName||'').toLowerCase().includes(model))throw new Error('The HID device name does not identify this model. Leave the display test blocked for review.');}
}
export async function sendMono(profile,display,pattern,devices){
 if(!['mono-pages','mono-oled'].includes(display.protocol))throw new Error('No known HID display protocol.');
 const matches=[];for(const entry of devices){const device=entry.device;checkIdentity(profile,device);for(const r of reports(device))if(r.reportId===0xe0+display.index&&[264,display.width*display.height/8].includes(reportSize(r)))matches.push({device,size:reportSize(r)});}
 if(matches.length!==1)throw new Error('A unique compatible display output report was not found. Add the display HID interface, or mark this test blocked.');
 const packets=monoPackets(display,pattern,matches[0].size);for(const p of packets)await matches[0].device.sendReport(p.reportId,p.data);
 return {transport:'hid',packets:packets.map(p=>new Uint8Array([p.reportId,...p.data]))};
}
async function bounded(promise){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Display access timed out. Reconnect and repeat this test.')),8000);})]);}finally{clearTimeout(timer);}}
export async function sendColor(profile,display,pattern,usb){
 if(!usb)throw new Error('WebUSB is unavailable in this browser.');
 if(display.protocol!=='ni-color')throw new Error(display.reason||'Unknown USB display protocol.');
 const device=await usb.requestDevice({filters:profile.product_ids.map(productId=>({vendorId:0x17cc,productId}))});checkIdentity(profile,device);
 let claimed=false;
 try{
  await device.open();if(!device.configuration)throw new Error('The USB display has no active configuration. No configuration was changed.');
  const iface=device.configuration.interfaces.find(i=>i.interfaceNumber===display.usbInterface),alt=iface?.alternate;
  if(!alt||alt.interfaceClass!==0xff||!alt.endpoints.some(e=>e.direction==='out'&&e.type==='bulk'&&e.endpointNumber===display.endpoint))throw new Error('Known vendor display interface/endpoint not found. No output sent.');
  await bounded(device.claimInterface(display.usbInterface));claimed=true;
  const packet=colorPacket(display,pattern),result=await bounded(device.transferOut(display.endpoint,packet));
  if(result.status!=='ok'||result.bytesWritten!==packet.length)throw new Error('Incomplete display transfer. Repeat after reconnecting.');
  return {transport:'webusb',packets:[packet]};
 }finally{if(claimed)try{await device.releaseInterface(display.usbInterface);}catch{}try{await device.close();}catch{}}
}
export async function transmissionEvidence(result){
 const size=result.packets.reduce((n,p)=>n+p.length,0),all=new Uint8Array(size);let offset=0;for(const p of result.packets){all.set(p,offset);offset+=p.length;}
 const hash=await crypto.subtle.digest('SHA-256',all);
 return {transport:result.transport,transfer_count:result.packets.length,bytes_sent:size,sha256:Array.from(new Uint8Array(hash),n=>n.toString(16).padStart(2,'0')).join('')};
}
export function sanitizeDisplayChecks(input,profile){
 const inventory=displayInventory(profile);if(input===undefined)return [];
 if(!Array.isArray(input)||input.length>inventory.length*PATTERNS.length)throw new Error('Invalid display observations.');
 const seen=new Set();return input.map(r=>{
  const display=inventory.find(d=>d.id===r.display_id),key=r.display_id+':'+r.pattern;
  if(!display||!PATTERNS.includes(r.pattern)||seen.has(key)||!['sent','confirmed','failed','blocked','not_tested'].includes(r.status)||typeof r.note!=='string'||r.note.length>300)throw new Error('Invalid display observation.');seen.add(key);
  const clean={display_id:display.id,pattern:r.pattern,status:r.status,note:r.note};
  if(['sent','confirmed','failed'].includes(r.status)){
   if(display.protocol==='pending-odr'||!['hid','webusb'].includes(r.transport)||!Number.isInteger(r.transfer_count)||r.transfer_count<1||r.transfer_count>4||!Number.isInteger(r.bytes_sent)||r.bytes_sent<1||r.bytes_sent>261152||!/^[a-f0-9]{64}$/.test(r.sha256||''))throw new Error('Missing or unsupported display transmission evidence.');
   Object.assign(clean,{transport:r.transport,transfer_count:r.transfer_count,bytes_sent:r.bytes_sent,sha256:r.sha256});
  }
  return clean;
 });
}
export function displayCoverage(report,profile){const inventory=displayInventory(profile),checks=report.display_checks||[];const missing=inventory.flatMap(d=>PATTERNS.filter(pattern=>!checks.some(r=>r.display_id===d.id&&r.pattern===pattern&&r.status==='confirmed')).map(p=>d.name+' / '+p));return {total:inventory.length*PATTERNS.length,confirmed:inventory.length*PATTERNS.length-missing.length,missing,complete:!report.demo&&!missing.length};}
