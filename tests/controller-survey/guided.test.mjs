import test from 'node:test';import assert from 'node:assert/strict';
import {ActionDetector,createActionDetector} from '../../web/controller-survey/guided.mjs';
const idle=[{interface:'hid0',hex:'010000'}];
test('one button advances only after press, release and debounce',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),1100);assert.equal(d.tick(1500).state,'release');d.feed('hid0',new Uint8Array([1,0,0]),1600);assert.notEqual(d.tick(1700).state,'complete');const r=d.tick(1900);assert.equal(r.state,'complete');assert.match(r.signature,/bit:1:1:4/);assert(r.frames.some(f=>f.ms>=1000));});
test('steady periodic idle packets cannot postpone release completion',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),1100);d.feed('hid0',new Uint8Array([1,0,0]),1300);for(let t=1350;t<1800;t+=50)d.feed('hid0',new Uint8Array([1,0,0]),t);assert.equal(d.tick(1800).state,'complete');});
test('continuous pads cannot be mistaken for a button',()=>{const d=new ActionDetector({kind:'button'},idle,0);for(let t=0;t<90000;t+=20)d.feed('hid0',new Uint8Array(65).fill(0x20),t);assert.equal(d.tick(90000).state,'waiting');assert.equal(d.frames.length,0);});
test('two button bits pause instead of guessing',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,5,0]),1100);assert.equal(d.tick(1400).state,'ambiguous');});
test('one clockwise turn is sufficient, with no second-direction stage',()=>{const d=new ActionDetector({kind:'encoder'},idle,0);for(let n=1;n<=3;n++)d.feed('hid0',new Uint8Array([1,0,n]),1000+n*100);assert.notEqual(d.tick(1400).state,'complete');assert.equal(d.tick(1700).state,'complete');});
test('rotary touch bit alone cannot count as turning',()=>{const d=new ActionDetector({kind:'encoder'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),1100);d.feed('hid0',new Uint8Array([1,0,0]),1300);assert.equal(d.tick(1800).state,'waiting');});
test('MIDI note-off must match the played key and channel',()=>{const d=new ActionDetector({kind:'key'},[],0);d.feed('midi0',new Uint8Array([0x90,60,100]),1100);d.feed('midi0',new Uint8Array([0x81,60,0]),1300);assert.equal(d.tick(1600).state,'release');d.feed('midi0',new Uint8Array([0x80,60,0]),1700);assert.equal(d.tick(2000).state,'complete');});
test('relative MIDI encoder repeated increments count as motion',()=>{const d=new ActionDetector({kind:'encoder'},[],0);for(let i=0;i<3;i++)d.feed('midi0',new Uint8Array([0xb0,20,1]),1100+i*100);assert.equal(d.tick(1700).state,'complete');});
test('Mikro event pad must be played and released',()=>{const d=new ActionDetector({kind:'pad'},[],0);const on=new Uint8Array(64);on.set([2,12,0x12,0x40]);d.feed('hid0',on,1100);assert.equal(d.tick(1500).state,'release');const off=new Uint8Array(64);off.set([2,12,0x20,0]);d.feed('hid0',off,1600);assert.equal(d.tick(1900).state,'complete');});
test('a long-held control pauses; waiting idle does not time out',()=>{const d=new ActionDetector({kind:'button'},idle,0);assert.equal(d.tick(20000).state,'waiting');d.feed('hid0',new Uint8Array([1,4,0]),21000);assert.equal(d.tick(30000).state,'ambiguous');});
test('unknown initial HID idle state can be learned without permanently ignoring the button',()=>{const d=new ActionDetector({kind:'button'},[],0);d.feed('hid0',new Uint8Array([1,4]),1100);d.feed('hid0',new Uint8Array([1,0]),1300);assert.equal(d.tick(1800).state,'waiting');d.feed('hid0',new Uint8Array([1,4]),2000);d.feed('hid0',new Uint8Array([1,0]),2200);assert.equal(d.tick(2500).state,'complete');});
test('an early tap during settling does not permanently disable the expected bit',()=>{const d=new ActionDetector({kind:'button'},idle,0);d.feed('hid0',new Uint8Array([1,4,0]),300);d.feed('hid0',new Uint8Array([1,0,0]),500);d.feed('hid0',new Uint8Array([1,4,0]),1300);d.feed('hid0',new Uint8Array([1,0,0]),1500);assert.equal(d.tick(1800).state,'complete');});
test('a fast first press after a new prompt is captured once with normalized evidence',()=>{const d=new ActionDetector({kind:'button'},idle,10000);d.feed('hid0',new Uint8Array([1,4,0]),10050);d.feed('hid0',new Uint8Array([1,0,0]),10130);const r=d.tick(10400);assert.equal(r.state,'complete');assert(r.frames.some(f=>f.ms===1000&&f.hex==='010400'));});
function mk2Packet(knob=0,master=0,second=0){const b=new Uint8Array(25);b[0]=1;b[8]=master;new DataView(b.buffer).setUint16(9,knob,true);new DataView(b.buffer).setUint16(11,second,true);return b;}
function mk2Detector(base){return new ActionDetector({kind:'encoder',name:'KNOB 1'},[{interface:'hid0',hex:Array.from(base,n=>n.toString(16).padStart(2,'0')).join('')}],0,{profileId:'maschine_mk2'});}
test('MK2 knob 1 is one 16-bit counter across carries and modulus-1000 wrap',()=>{for(const values of [[254,255,256,257],[998,999,0,1],[510,511,512,513],[100,300,600,800]]){const d=mk2Detector(mk2Packet(values[0]));for(let n=1;n<values.length;n++)d.feed('hid0',mk2Packet(values[n]),100+n*80);const result=d.tick(700);assert.equal(result.state,'complete');assert.equal(result.signature,'hid0:counter:1:9:2:1000');}});
test('MK2 master 4-bit wrap works and knob 2 has its own signature',()=>{const m=mk2Detector(mk2Packet(400,15));m.feed('hid0',mk2Packet(400,0),100);m.feed('hid0',mk2Packet(400,1),200);assert.equal(m.tick(500).signature,'hid0:counter:1:8:1:16');const d=mk2Detector(mk2Packet(400,0,254));d.feed('hid0',mk2Packet(400,0,255),100);d.feed('hid0',mk2Packet(400,0,256),200);assert.equal(d.tick(500).signature,'hid0:counter:1:11:2:1000');});
test('MK2 held buttons and unchanged reports do not count as turning; two knobs pause',()=>{const d=mk2Detector(mk2Packet(100));const b=mk2Packet(100);b[1]=1;d.feed('hid0',b,100);assert.equal(d.tick(500).state,'waiting');d.feed('hid0',mk2Packet(101,0,1),600);assert.equal(d.tick(900).state,'ambiguous');});

test('unchanged periodic reports cannot indefinitely postpone unknown-stream calibration',()=>{const d=new ActionDetector({kind:'encoder'},[],0);d.feed('hid0',new Uint8Array([1,0,10]),500);for(let t=550;t<1200;t+=50)d.feed('hid0',new Uint8Array([1,0,10]),t);d.feed('hid0',new Uint8Array([1,0,11]),1300);d.feed('hid0',new Uint8Array([1,0,12]),1400);assert.equal(d.tick(1700).state,'complete');});

const jamButton = bits => Uint8Array.of(1, 2, bits, ...new Uint8Array(14));
const jamOptions = {profileId:'maschine_jam',hidConnected:true};
const jamIdle = [{interface:'hid0',hex:'0102'+'00'.repeat(15)}];

test('JAM guided button uses its HID packet even when MIDI arrives first',()=>{
 const d=new ActionDetector({kind:'button'},jamIdle,0,jamOptions);
 d.feed('midi0',Uint8Array.of(0x90,60,100),1000);
 d.feed('midi1',Uint8Array.of(0xb0,20,127),1010);
 d.feed('hid0',jamButton(1),1020);
 assert.equal(d.tick(1200).state,'release');
 d.feed('hid0',jamButton(0),1300);
 const result=d.tick(1600);
 assert.equal(result.state,'complete');
 assert.equal(result.signature,'hid0:bit:1:2:1');
 assert(result.frames.every(frame=>frame.interface==='hid0'));
});

test('JAM guided mapping still pauses for a second physical button',()=>{
 const d=new ActionDetector({kind:'button'},jamIdle,0,jamOptions);
 d.feed('hid0',jamButton(1),1000);
 d.feed('hid0',jamButton(3),1100);
 assert.equal(d.tick(1400).state,'ambiguous');
});

test('JAM MIDI-only button capture still accepts MIDI',()=>{
 const d=new ActionDetector({kind:'button'},[],0,{profileId:'maschine_jam'});
 d.feed('midi0',Uint8Array.of(0x90,60,100),1000);
 d.feed('midi0',Uint8Array.of(0x80,60,0),1200);
 assert.equal(d.tick(1500).state,'complete');
});

test('JAM encoder push can arrive with its companion touch bit',()=>{
 const d=new ActionDetector({id:'button_encoder_push',kind:'button'},jamIdle,0,jamOptions);
 const held=jamButton(0);
 held[16]=0x18;
 d.feed('hid0',held,1000);
 held[16]=0x10;
 d.feed('hid0',held,1200);
 assert.equal(d.tick(1500).signature,'hid0:bit:1:16:8');
});

const jamDualOptions = {...jamOptions,midiSelected:true};
test('JAM with an open but silent HID interface can finish a Windows MIDI button',()=>{
 const d=createActionDetector({kind:'button'},[],0,jamDualOptions);
 d.feed('midi0',Uint8Array.of(0x90,60,100),100);
 d.feed('midi0',Uint8Array.of(0x80,60,0),200);
 assert.notEqual(d.tick(500).state,'complete');
 const result=d.tick(1150);
 assert.equal(result.state,'complete');
 assert.equal(result.signature,'midi0:note:0:60');
});

test('JAM keeps HID evidence when MIDI and HID mirror a press',()=>{
 const d=createActionDetector({kind:'button'},jamIdle,0,jamDualOptions);
 d.feed('midi0',Uint8Array.of(0x90,60,100),1000);
 d.feed('midi0',Uint8Array.of(0xb0,20,127),1005);
 d.feed('hid0',jamButton(1),1020);
 d.feed('hid0',jamButton(0),1300);
 assert.equal(d.tick(1600).signature,'hid0:bit:1:2:1');
});

test('JAM with no button reports times out with transport diagnostics',()=>{
 const d=createActionDetector({kind:'button'},[],0,jamDualOptions);
 assert.match(d.tick(15001).message,/HID: 0 reports, MIDI: 0 reports/);
});
