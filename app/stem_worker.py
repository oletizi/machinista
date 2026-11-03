"""Memory-bounded Spleeter inference; optional dependencies stay off the audio path.

Each downloaded U-Net consumes magnitudes [2, 1, 512, 1024]. Sessions run
sequentially; ratio masks retain original phase and sum to the input spectrum.
"""
import gc
import json
from pathlib import Path
import sys
import time
import wave

RATE=44100
FFT=4096
HOP=1024
PAD=FFT-HOP
BINS=1024
BLOCK=512
STEMS=('vocals','drums','bass','other')


def spectrum(audio):
    import numpy as np
    frames=(PAD+audio.shape[1]+HOP-1)//HOP
    padded=np.pad(audio,((0,0),(PAD,(frames-1)*HOP+FFT-PAD-audio.shape[1])))
    windows=np.lib.stride_tricks.sliding_window_view(padded,FFT,axis=1)[:,::HOP,:]
    hann=np.hanning(FFT+1)[:-1].astype(np.float32)
    return np.fft.rfft(windows*hann,axis=-1).astype(np.complex64)


def reconstruct(spec,length):
    import numpy as np
    hann=np.hanning(FFT+1)[:-1].astype(np.float32)
    size=(spec.shape[1]-1)*HOP+FFT
    audio=np.zeros((2,size),dtype=np.float32);weights=np.zeros(size,dtype=np.float32)
    for i in range(spec.shape[1]):
        at=i*HOP;frame=np.fft.irfft(spec[:,i,:],n=FFT).astype(np.float32)
        audio[:,at:at+FFT]+=frame*hann;weights[at:at+FFT]+=hann*hann
    np.divide(audio,weights,out=audio,where=weights>1e-8)
    return audio[:,PAD:PAD+length]


def separate(model,source,destination):
    import numpy as np
    import onnxruntime as ort
    started=time.monotonic();destination=Path(destination)
    samples=np.fromfile(source,dtype='<f4')
    if not 0<len(samples)<=RATE*60*2 or len(samples)%2:raise ValueError('Use audio up to 60 seconds.')
    audio=samples.reshape(-1,2).T.copy();del samples
    if not np.isfinite(audio).all():raise ValueError('Invalid audio samples.')
    spec=spectrum(audio);length=audio.shape[1];frames=spec.shape[1]
    magnitude=np.abs(spec[:,:,:BINS]);estimates=[]
    options=ort.SessionOptions();options.intra_op_num_threads=1;options.inter_op_num_threads=1
    options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL;options.log_severity_level=3
    options.enable_cpu_mem_arena=False
    parts=(frames+BLOCK-1)//BLOCK
    for index,stem in enumerate(STEMS):
        session=ort.InferenceSession(str(Path(model)/(stem+'.fp16.onnx')),sess_options=options,providers=['CPUExecutionProvider'])
        inputs=session.get_inputs()
        if len(inputs)!=1 or inputs[0].name!='x' or session.get_outputs()[0].name!='y':raise ValueError('Unsupported stem model.')
        estimate=np.empty_like(magnitude)
        for part in range(parts):
            start=part*BLOCK;count=min(BLOCK,frames-start)
            chunk=np.zeros((2,1,BLOCK,BINS),dtype=np.float32);chunk[:,0,:count]=magnitude[:,start:start+count]
            value=session.run(['y'],{'x':chunk})[0]
            if value.shape!=chunk.shape or not np.isfinite(value).all():raise ValueError('Invalid stem model output.')
            estimate[:,start:start+count]=np.maximum(0,value[:,0,:count])
            print(json.dumps(dict(progress=round(((index*parts)+part+1)*85/(4*parts)),message=f'Separating {stem} {part+1}/{parts}')),flush=True)
        estimates.append(np.square(estimate));del session,estimate,value,chunk;gc.collect()
    denominator=np.sum(estimates,axis=0)+1e-10
    result=[]
    for estimate in estimates:
        mask=(estimate+2.5e-11)/denominator
        # Carry the modeled band's average into the unmodeled top octave.
        full=np.empty(spec.shape,dtype=np.float32);full[:,:,:BINS]=mask
        full[:,:,BINS:]=mask.mean(axis=-1,keepdims=True)
        result.append(reconstruct(spec*full,length))
    reconstructed=np.sum(result,axis=0)
    reconstruction_error=float(np.max(np.abs(reconstructed-audio)))
    if reconstruction_error>max(2e-5,float(np.max(np.abs(audio)))*2e-5):raise ValueError('Stem reconstruction check failed.')
    peak=max(float(np.max(np.abs(s))) for s in result);gain=min(1,.98/max(peak,1e-12))
    destination.mkdir(exist_ok=True)
    for name,stem in zip(STEMS,result):
        pcm=np.ascontiguousarray(np.rint(np.clip(stem.T*gain,-1,1)*8388607),dtype='<i4').view(np.uint8).reshape(-1,4)[:,:3]
        with wave.open(str(destination/(name+'.wav')),'wb') as output:
            output.setparams((2,3,RATE,length,'NONE','not compressed'));output.writeframes(pcm.tobytes())
    details=dict(model='Spleeter 4-stem ONNX',rate=RATE,frames=length,seconds=length/RATE,gain=gain,peak=peak,reconstruction_error=reconstruction_error,elapsed=time.monotonic()-started,stems=list(STEMS))
    (destination/'Separation.json').write_text(json.dumps(details,indent=2)+'\n')
    print(json.dumps(dict(progress=100,message='Separation finished.',result=details)),flush=True)
    return details


if __name__=='__main__':
    try:separate(*sys.argv[1:])
    except Exception as error:
        print(json.dumps(dict(error=str(error))),flush=True);raise SystemExit(1)
