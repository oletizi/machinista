"""Pixel-exact 104x20 machine drawings for the MK1/MK2 LCDs.

Original code-native artwork: readable outlines and solid mechanisms, no grey
conversion, scaling, bitmap file I/O or generated halftone noise at runtime.
"""
from functools import lru_cache
from app.instrument_art import EFFECT_ART
KINDS=frozenset(EFFECT_ART.values())

@lru_cache(maxsize=len(KINDS))
def pixels(kind):
    if kind not in KINDS:return ()
    w,h=104,20;p=bytearray(w*h)
    def dot(x,y):
        if 0<=x<w and 0<=y<h:p[y*w+x]=1
    def line(x,y,xx,yy):
        dx=abs(xx-x);dy=-abs(yy-y);sx=1 if x<xx else -1;sy=1 if y<yy else -1;e=dx+dy
        while True:
            dot(x,y)
            if x==xx and y==yy:break
            d=2*e
            if d>=dy:e+=dy;x+=sx
            if d<=dx:e+=dx;y+=sy
    def box(x,y,ww,hh,solid=False):
        if solid:
            for a in range(x,x+ww):
                for b in range(y,y+hh):dot(a,b)
        else:
            line(x,y,x+ww-1,y);line(x,y+hh-1,x+ww-1,y+hh-1);line(x,y,x,y+hh-1);line(x+ww-1,y,x+ww-1,y+hh-1)
    def wheel(x,y,r=4):
        points=((x-r,y-1),(x-r+1,y-r+1),(x-1,y-r),(x+1,y-r),(x+r-1,y-r+1),(x+r,y-1),(x+r,y+1),(x+r-1,y+r-1),(x+1,y+r),(x-1,y+r),(x-r+1,y+r-1),(x-r,y+1))
        for first,second in zip(points,points[1:]+points[:1]):line(*first,*second)
        dot(x,y)
    def gauge(x,y):
        box(x,y,17,11);line(x+3,y+7,x+8,y+2);line(x+8,y+2,x+13,y+7);line(x+8,y+8,x+11,y+4)
    def wave(x,y,ww=22):
        for a in range(ww-1):
            b=(0,-2,0,2,0,-1,0,1)[a%8];bb=(0,-2,0,2,0,-1,0,1)[(a+1)%8];line(x+a,y+b,x+a+1,y+bb)
    box(1,1,102,18);box(5,17,5,3,True);box(94,17,5,3,True)
    for x in (4,99):dot(x,4);dot(x,15)
    name=kind[3:]
    if name=='eq':
        for x,level in ((12,6),(26,11),(40,8),(54,5)):
            line(x,4,x,15);box(x-3,level,7,3,True)
        box(65,4,29,12);line(68,12,74,12);line(74,12,80,7);line(80,7,84,10);line(84,10,91,10)
    elif name in ('compressor','ducktor'):
        gauge(9,4);gauge(78,4)
        for x in (34,61):box(x,4,8,4,True);line(x+3,8,x+3,12);box(x-2,12,12,3,True)
        wave(45,9,12)
        if name=='ducktor':line(30,3,73,3);line(53,3,53,6);line(51,4,53,6);line(55,4,53,6)
        else:box(46,15,12,2,True)
    elif name=='limiter':
        box(10,4,65,12);line(13,7,71,7)
        for x,yy in ((17,11),(25,8),(33,10),(41,8),(49,12),(57,8),(65,9)):line(x,14,x,yy)
        wheel(86,9,4);box(80,15,14,1)
    elif name=='transient':
        for x in (12,34):box(x,4,12,3,True);line(x+5,7,x+5,11);box(x+1,11,10,3)
        line(55,14,61,14);line(61,14,63,5);line(63,5,69,11);line(69,11,91,14)
    elif name=='reverb':
        for x in (12,85):box(x,4,7,12);line(x+2,6,x+2,13)
        box(23,3,58,14);box(29,5,46,10)
        for x in range(34,72,8):line(x,6,x+3,8);line(x+3,8,x,11);line(x,11,x+3,13)
    elif name=='delay':
        wheel(25,9,6);wheel(77,9,6);wheel(25,9,2);wheel(77,9,2)
        line(30,5,72,5);line(30,13,72,13);box(44,8,15,3)
        for x in (10,94):box(x,6,2,8)
    elif name=='chorus':
        for x in (19,46,73):box(x,3,12,13);wave(x+2,9,8);box(x-2,15,16,2,True)
        line(31,10,45,10);line(58,10,72,10)
    elif name=='flanger':
        wheel(20,10,6);wheel(40,10,6);line(26,10,34,10)
        box(56,4,38,12)
        for x in range(60,92,6):line(x,7,x,13);line(x,13,x+3,13);line(x+3,13,x+3,7)
    elif name=='phaser':
        for x in (14,29,44,59,74,89):wheel(x,10,4)
        line(18,10,25,10);line(33,10,40,10);line(48,10,55,10);line(63,10,70,10);line(78,10,85,10)
    elif name=='tremolo':
        wheel(25,10,6);line(21,6,29,14);line(21,14,29,6);box(44,4,49,12)
        for x in range(49,89,10):line(x,13,x,7);line(x,7,x+5,7);line(x+5,7,x+5,13);line(x+5,13,x+9,13)
    elif name=='vibrato':
        line(19,4,19,10);line(29,4,29,10);line(19,10,24,14);line(29,10,24,14);line(24,14,24,16)
        box(43,4,50,12);wave(47,10,42)
    elif name=='autopan':
        box(11,7,5,7,True);line(16,7,24,4);line(24,4,24,16);line(24,16,16,13)
        box(88,7,5,7,True);line(88,7,80,4);line(80,4,80,16);line(80,16,88,13)
        line(35,8,68,8);line(35,8,39,5);line(35,8,39,11);line(68,8,64,5);line(68,8,64,11);box(47,12,10,3,True)
    return bytes(p)

def paint(canvas,kind,x=4,y=25):
    for i,value in enumerate(pixels(kind)):
        if value:canvas.rect(x+i%104,y+i//104,1,1)
