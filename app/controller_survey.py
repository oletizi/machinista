"""Portable controller survey evidence. Data only; never loads a live driver.

SPDX-License-Identifier: GPL-3.0-or-later
Studio identity/output framing references are documented in CONTROLLER_SURVEY.md.
"""
from collections import defaultdict
import copy,json,math,re,statistics

FORMAT='Machinista-controller-survey'
VERSION=2
MAX_FILE=16*1024**2
STUDIO=0x1300
LED_BANKS={0x80:63,0x81:45,0x82:53,0x83:56}
from app.controller_survey_catalog import PROFILES,checklist
STEPS=checklist('maschine_studio')

def summarize(kind,frames):
 """Find candidates, not authoritative mappings. Preserve ambiguous captures."""
 groups=defaultdict(list)
 for row in frames:
  data=bytes.fromhex(row['hex'])
  if data:groups[(row['interface'],data[0],len(data))].append((row['ms'],data))
 candidates=[]
 for (interface,rid,length),rows in groups.items():
  quiet=[p for ms,p in rows if ms<1000];active=[p for ms,p in rows if 1000<=ms<5000]
  if interface.startswith('midi'):
   channel=rid&15;rid&=0xf0
   if kind in ('key','pad','button','touch') and rid==0x90:
    notes={p[1] for p in active if len(p)==3 and p[2]>0}
    for note in sorted(notes):
     on=sum(len(p)==3 and p[1]==note and p[2]>0 for p in active)
     released=any(bytes.fromhex(f['hex'])[0]&0xf0 in (0x80,0x90) and len(bytes.fromhex(f['hex']))==3 and bytes.fromhex(f['hex'])[1]==note and (bytes.fromhex(f['hex'])[0]&0xf0==0x80 or bytes.fromhex(f['hex'])[2]==0) for f in frames if f['interface']==interface and bytes.fromhex(f['hex'])[0]&15==channel)
     candidates.append(dict(kind='midi_note',interface=interface,channel=channel,note=note,attacks=on,returned_to_idle=released,confidence='candidate'))
   elif kind=='pressure' and rid in (0xa0,0xd0):
    if len({p[-1] for p in active})>=2:candidates.append(dict(kind='midi_pressure',interface=interface,channel=channel,type='poly' if rid==0xa0 else 'channel',confidence='candidate'))
   elif rid in (0xb0,0xe0) and kind in ('slider','pedal','encoder','button','touch'):
    numbers={p[1] for p in active if len(p)==3} if rid==0xb0 else {None}
    for number in sorted(numbers,key=lambda n:n or 0):
     values=[p[2] if rid==0xb0 else p[1]|p[2]<<7 for p in active if len(p)==3 and (number is None or p[1]==number)]
     if len(set(values))>=2:candidates.append(dict(kind='midi_cc' if rid==0xb0 else 'midi_pitch',interface=interface,channel=channel,controller=number,min=min(values),max=max(values),decoder='unresolved' if kind=='encoder' else 'absolute',confidence='candidate'))
   continue
  if not quiet or not active:continue
  if kind=='pad' and rid==0x20 and length==65:
   def adc(p):
    values=defaultdict(list)
    for i in range(1,65,2):values[p[i+1]>>4].append(p[i]|((p[i+1]&15)<<8))
    return values
   idle=defaultdict(list);peaks=defaultdict(int)
   for p in quiet:
    for ch,values in adc(p).items():idle[ch].extend(values)
   for p in active:
    for ch,values in adc(p).items():peaks[ch]=max(peaks[ch],max(values))
   scores=sorted(((max(0,peak-statistics.median(idle[ch])),ch,peak) for ch,peak in peaks.items() if idle[ch]),reverse=True)
   if scores and scores[0][0]>=20:
    score,ch,peak=scores[0];ratio=score/max(1,scores[1][0] if len(scores)>1 else 1)
    candidates.append(dict(kind='pad_adc12',interface=interface,report_id=rid,length=length,channel=ch,idle=round(statistics.median(idle[ch])),peak=peak,dominance=round(ratio,2),confidence='candidate' if ratio>=1.5 else 'ambiguous'))
   continue
  if kind=='pad' or rid==0x20:continue
  for offset in range(1,min(length,128)):
   q={p[offset] for p in quiet};values=[p[offset] for p in active]
   if kind in ('button','touch'):
    for bit in range(8):
     mask=1<<bit;baseline={v&mask for v in q}
     if len(baseline)!=1:continue
     normal=next(iter(baseline));states=[bool(p[offset]&mask) for _,p in rows];edges=sum(a!=b for a,b in zip(states,states[1:]))
     if edges>=2 and any((v&mask)!=normal for v in values):
      candidates.append(dict(kind='button_bit',interface=interface,report_id=rid,length=length,byte=offset,mask=mask,active_high=normal==0,edges=edges,returned_to_idle=(rows[-1][1][offset]&mask)==normal,confidence='candidate'))
   elif kind in ('encoder','slider','pedal','pressure') and len(set(values))>=3:
    candidates.append(dict(kind='encoder_bytes' if kind=='encoder' else 'analog_bytes',interface=interface,report_id=rid,length=length,byte=offset,unique=len(set(values)),min=min(values),max=max(values),decoder='unresolved',confidence='candidate'))
 return candidates[:64]

def validate(value):
 if not isinstance(value,dict) or value.get('format')!=FORMAT or value.get('version')!=VERSION:raise ValueError('Not a supported Machinista controller survey.')
 device=value.get('device')
 if not isinstance(device,dict) or type(device.get('vendor_id')) is not int or device['vendor_id']!=0x17cc or type(device.get('product_id')) is not int or not 0<=device['product_id']<=65535:raise ValueError('Invalid device identity.')
 if not isinstance(device.get('interfaces'),list) or not 1<=len(device['interfaces'])<=8:raise ValueError('Invalid interfaces.')
 allowed=set()
 for item in device['interfaces']:
  if not isinstance(item,dict) or not isinstance(item.get('id'),str) or not 1<=len(item['id'])<=32 or item['id'] in allowed:raise ValueError('Invalid interface identity.')
  allowed.add(item['id'])
 if type(value.get('layout_audited',False)) is not bool:raise ValueError('Invalid inventory audit.')
 if type(value.get('demo')) is not bool:raise ValueError('Missing demo marker.')
 profile=value.get('profile_id');extras=value.get('extra_controls',[])
 if not isinstance(extras,list) or len(extras)>64:raise ValueError('Invalid additional controls.')
 inventory_version=value.get('checklist_version',1)
 if type(inventory_version) is not int or inventory_version not in (1,2):raise ValueError('Unsupported checklist version.')
 expected=checklist(profile,extras,inventory_version)
 if PROFILES[profile]['product_ids'] and device['product_id'] not in PROFILES[profile]['product_ids']:raise ValueError('USB device does not match model.')
 controls=value.get('controls');known={s['id']:s for s in expected}
 if not isinstance(controls,list) or len(controls)>len(expected):raise ValueError('Invalid controls.')
 seen=set()
 for row in controls:
  if not isinstance(row,dict) or row.get('id') not in known or row['id'] in seen or row.get('kind')!=known[row['id']]['kind'] or row.get('name')!=known[row['id']]['name']:raise ValueError('Invalid or duplicate control.')
  seen.add(row['id'])
  if row.get('status') not in ('confirmed','captured','skipped'):raise ValueError('Invalid control status.')
  if type(row.get('tester_confirmed',False)) is not bool:raise ValueError('Invalid observation marker.')
  if not isinstance(row.get('note',''),str) or len(row.get('note',''))>300:raise ValueError('Invalid observation.')
  detection=row.get('detection')
  if detection is not None and (not isinstance(detection,dict) or detection.get('method')!='automatic' or not isinstance(detection.get('signature'),str) or len(detection['signature'])>180 or re.fullmatch('[a-zA-Z0-9:._-]+',detection['signature']) is None):raise ValueError('Invalid automatic detection metadata.')
  frames=row.get('frames')
  if not isinstance(frames,list) or len(frames)>320:raise ValueError('Too many raw frames.')
  last=-1
  for f in frames:
   if not isinstance(f,dict) or f.get('interface') not in allowed or type(f.get('ms')) is not int or not 0<=f['ms']<=10000 or f['ms']<last:raise ValueError('Invalid raw-frame timing/interface.')
   last=f['ms'];text=f.get('hex')
   if not isinstance(text,str) or len(text)>1024 or len(text)%2:raise ValueError('Invalid raw report.')
   try:data=bytes.fromhex(text)
   except ValueError as e:raise ValueError('Invalid raw-report hex.') from e
   if not data:raise ValueError('Empty raw report.')
  candidates=summarize(row['kind'],frames)
  selected=row.get('selected')
  if selected is not None and (type(selected) is not int or not 0<=selected<len(candidates)):raise ValueError('Invalid candidate selection.')
  if row['status']=='confirmed' and selected is None:raise ValueError('Confirmed control has no measured candidate.')
 leds=value.get('leds',[])
 if not isinstance(leds,list) or len(leds)>250:raise ValueError('Invalid LED evidence.')
 for led in leds:
  if device['product_id']!=STUDIO or not isinstance(led,dict) or type(led.get('bank')) is not int or led['bank'] not in LED_BANKS or type(led.get('offset')) is not int or not 1<=led['offset']<LED_BANKS[led['bank']]:raise ValueError('Invalid LED probe.')
  if not isinstance(led.get('observed'),str) or len(led['observed'])>120:raise ValueError('Invalid LED observation.')
 displays=value.get('displays',{})
 if not isinstance(displays,dict) or any(k not in ('left','right') or not isinstance(v,dict) or v.get('status') not in ('not_tested','sent','confirmed','incorrect','unavailable') or not isinstance(v.get('note',''),str) or len(v.get('note',''))>300 for k,v in displays.items()):raise ValueError('Invalid display observations.')
 checks=value.get('display_checks',[]);inventory={d['id']:d for d in PROFILES[profile].get('displays',[])}
 if not isinstance(checks,list) or len(checks)>len(inventory)*3:raise ValueError('Invalid display checks.')
 seen_checks=set()
 for check in checks:
  if not isinstance(check,dict):raise ValueError('Invalid display check.')
  key=(check.get('display_id'),check.get('pattern'));display=inventory.get(key[0])
  if display is None or key[1] not in ('border','grid','levels') or key in seen_checks or check.get('status') not in ('sent','confirmed','failed','blocked','not_tested') or not isinstance(check.get('note'),str) or len(check['note'])>300:raise ValueError('Invalid display check.')
  seen_checks.add(key)
  if check['status'] in ('sent','confirmed','failed'):
   if display['protocol']=='pending-odr' or check.get('transport') not in ('hid','webusb') or type(check.get('transfer_count')) is not int or not 1<=check['transfer_count']<=4 or type(check.get('bytes_sent')) is not int or not 1<=check['bytes_sent']<=261152 or not isinstance(check.get('sha256'),str) or re.fullmatch('[a-f0-9]{64}',check['sha256']) is None:raise ValueError('Invalid display transmission evidence.')
 legacy=value.get('legacy_controls')
 if legacy is not None:
  if inventory_version!=2 or not isinstance(legacy,list) or len(legacy)>len(PROFILES[profile]['encoders'])*2:raise ValueError('Invalid legacy encoder evidence.')
  original=dict(value,checklist_version=1,controls=legacy);original.pop('legacy_controls',None);validate(original)
 return value

def read_report(path):
 from pathlib import Path
 p=Path(path)
 if p.stat().st_size>MAX_FILE:raise ValueError('Survey exceeds 16 MiB.')
 def invalid(_):raise ValueError('Non-finite JSON is not allowed.')
 return validate(json.loads(p.read_text(encoding='utf-8'),parse_constant=invalid))

def review(value):
 """Recompute candidates: imported claimed mappings are never trusted/executed."""
 validate(value)
 mapped=[];unresolved=[];bindings={};conflicts=[]
 for row in value['controls']:
  candidates=summarize(row['kind'],row['frames']);selected=row.get('selected')
  if row['status']=='confirmed' and selected is not None:
   candidate=candidates[selected]
   if candidate.get('decoder')=='unresolved' or candidate['kind']=='encoder_bytes' or candidate.get('confidence')=='ambiguous' or candidate.get('returned_to_idle') is False:unresolved.append(row['id']);continue
   identity=tuple((k,candidate.get(k)) for k in ('kind','interface','report_id','length','byte','mask','channel','note','controller','type'))
   if identity in bindings:conflicts.append([bindings[identity],row['id']])
   bindings[identity]=row['id'];mapped.append(dict(id=row['id'],name=row['name'],binding=candidate))
  else:unresolved.append(row['id'])
 return dict(format='Machinista-controller-review',version=1,device=copy.deepcopy(value['device']),profile_id=value['profile_id'],demo=value['demo'],coverage=coverage(value),activation_allowed=False,legacy_controls=copy.deepcopy(value.get('legacy_controls',[])),candidates={r['id']:summarize(r['kind'],r['frames']) for r in value['controls']},mappings=mapped,unresolved=unresolved,conflicts=conflicts,missing=[s['id'] for s in checklist(value['profile_id'],value.get('extra_controls',[]),value.get('checklist_version',1)) if s['id'] not in {r['id'] for r in value['controls']}],leds=copy.deepcopy(value.get('leds',[])),displays=copy.deepcopy(value.get('displays',{})),display_checks=copy.deepcopy(value.get('display_checks',[])),display_inventory=copy.deepcopy(PROFILES[value['profile_id']].get('displays',[])),note='Evidence for driver development. No live controller driver is installed or enabled. Encoder decoding, timings and output mappings require hardware review.')


def coverage(value):
 required=[s for s in checklist(value['profile_id'],value.get('extra_controls',[]),value.get('checklist_version',1)) if not s['optional']]
 rows={r['id']:r for r in value['controls']}
 missing=[s['id'] for s in required if rows.get(s['id'],{}).get('status')!='confirmed']
 optional=[s['id'] for s in checklist(value['profile_id'],value.get('extra_controls',[]),value.get('checklist_version',1)) if s['optional'] and rows.get(s['id'],{}).get('status')!='confirmed']
 return dict(total=len(required),tested=len(required)-len(missing),untested=missing,optional_untested=optional,layout_audited=value.get('layout_audited',False),input_check_complete=not value['demo'] and not missing and value.get('layout_audited',False),driver_ready=False)
