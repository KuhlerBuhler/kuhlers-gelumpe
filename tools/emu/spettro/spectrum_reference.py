"""Offline frequency-spectrum reference. No USB, firmware or SD access.
Levels are relative to signed-16 PCM full scale, not acoustic SPL.
"""
import numpy as np


def spectrum(pcm, rate=48000):
    data=np.asarray(pcm,dtype=np.float64)
    if data.ndim==1:data=data[:,None]
    if data.ndim!=2 or data.shape[1] not in (1,2) or len(data)<128:
        raise ValueError('Expected mono or stereo PCM window')
    if not np.isfinite(data).all() or np.max(np.abs(data))>32768:
        raise ValueError('Expected finite signed-16 PCM units')
    n=len(data)
    if n & (n-1):raise ValueError('FFT size must be a power of two')
    window=np.hanning(n)
    # Remove the constant offset from the spectrum only, not from recorded data.
    centered=data-data.mean(axis=0)
    transformed=np.fft.rfft(centered*window[:,None],axis=0)
    amplitude=np.abs(transformed)*(2/window.sum())/32768
    amplitude[0]*=.5;amplitude[-1]*=.5
    # Combine component powers: opposite stereo phases must not cancel out.
    power=np.mean(amplitude**2,axis=1)
    frequency=np.fft.rfftfreq(n,1/rate)
    return frequency,power


def logarithmic_columns(frequency,power,width=128,low=20,high=20000,floor=-90):
    frequency=np.asarray(frequency);power=np.asarray(power)
    if len(frequency)!=len(power) or width<2 or not 0<low<high:
        raise ValueError('Invalid spectrum/axis')
    edges=np.geomspace(low,high,width+1)
    centers=np.sqrt(edges[:-1]*edges[1:])
    db=np.full(width,np.nan)
    positive=frequency>0
    for column,(a,b,center) in enumerate(zip(edges[:-1],edges[1:],centers)):
        # Below the first FFT bin we lack resolution: leave an explicit gap.
        if center<frequency[1] or center>frequency[-1]:continue
        selected=(frequency>=a)&(frequency<b)&positive
        if np.any(selected):value=np.max(power[selected])
        else:value=np.interp(np.log(center),np.log(frequency[positive]),power[positive])
        db[column]=max(floor,10*np.log10(max(value,10**(floor/10))))
    return centers,db
