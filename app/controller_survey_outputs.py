"""Bounded LED survey inventory. Sizes include report IDs, as in HID captures."""
import re

def output_inventory(identity,profile):
 banks={};tests=[]
 def bank(rid,size):banks[rid]=size
 def test(rid,offset,name,kind='button',color='white',extra=()):
  tests.append(dict(id=f'led_{rid:02x}_{offset}_{color}',bank=rid,offset=offset,name=name,kind=kind,color=color,value=60,extra_offsets=list(extra)))
 if identity=='maschine_mk2':
  from app.mk2_protocol import LED_BUTTONS,TRANSPORT,PAD_SLOTS
  bank(0x80,49);bank(0x81,57);bank(0x82,32)
  for i,name in enumerate(LED_BUTTONS):test(0x82,1+i,name)
  for i,name in enumerate(TRANSPORT):test(0x81,49+i,name)
  for i,c in enumerate('ABCDEFGH'):
   for channel,color in enumerate(('red','green','blue')):test(0x81,1+i*6+channel,'GROUP '+c,color=color,extra=(4+i*6+channel,))
  for raw,slot in enumerate(PAD_SLOTS):
   for channel,color in enumerate(('red','green','blue')):test(0x80,1+raw*3+channel,'PAD '+str(slot+1),'pad',color)
 elif identity=='maschine_jam':
  # WebHID lengths come from the USB HID descriptor, including the ID here.
  bank(0x80,54);bank(0x81,81);bank(0x82,89)
  controls=('SONG','STEP','PAD MODE','CLEAR','DUPLICATE','DPAD UP','DPAD LEFT',
            'DPAD RIGHT','DPAD DOWN','NOTE REPEAT','MST','GRP','IN1',None,'CUE',
            None,'BROWSE','MACRO','LEVEL','AUX','CONTROL','AUTO','PERFORM',
            'NOTES','LOCK','TUNE','SWING','SHIFT','PLAY','REC','PAGE LEFT',
            'PAGE RIGHT','TEMPO','GRID','SOLO','MUTE','SELECT')
  for i,name in enumerate(controls,1):
   test(0x80,i,name or f'OUTPUT 80 / {i}',kind='button' if name else 'unknown',color='observe')
  for i in range(16):test(0x80,38+i,f'VU {"LEFT" if i<8 else "RIGHT"} / {i%8+1}',kind='unknown',color='observe')
  for i,name in enumerate((*profile['buttons'][1:9],*profile['buttons'][-64:],
                           *('GROUP '+c for c in 'ABCDEFGH')),1):
   test(0x81,i,name,color='observe')
  for i in range(88):test(0x82,i+1,f'SMART STRIP {i//11+1} / LED {i%11+1}',kind='unknown',color='observe')
 else:
  if identity=='maschine_studio':banks={0x80:63,0x81:45,0x82:53,0x83:56}
  elif identity=='maschine_mikro_mk3':banks={0x80:48,0x81:20}
  elif re.fullmatch(r'kk_s\d+_mk1',identity):banks={0x80:54,0x81:profile['keys']*3+1}
  elif re.fullmatch(r'kk_s\d+_mk2',identity):banks={0x80:79,0x81:249}
  elif re.fullmatch(r'kk_s\d+_mk3',identity):banks={0x80:42,0x81:30,0x82:profile['keys']}
  # For unverified LED layouts, the tester names the illuminated physical item.
  for rid,size in banks.items():
   for offset in range(1,size):test(rid,offset,f'OUTPUT {rid:02X} / {offset}',kind='unknown',color='observe')
 return [dict(report_id=rid,size=size) for rid,size in banks.items()],tests
