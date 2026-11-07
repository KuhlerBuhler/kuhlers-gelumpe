"""Own ARM spectrum sources; no firmware is read during assembly."""
import math
from pathlib import Path

CONTEXT_SIZE = 103424
HERE = Path(__file__).resolve().parent

def tables():
    sections=[]
    for name,high in (('full',20000),('bass',2000)):
        edges=[20*(high/20)**(i/128) for i in range(129)]
        rows=[]
        for a,b in zip(edges,edges[1:]):
            if (b-a)*4096/48000<1:
                position=math.sqrt(a*b)*4096/48000
                start=min(2047,max(1,math.floor(position)))
                weight=round((position-start)*256)
                if weight==256:start+=1;weight=0
                end=0x80000000|weight  # interpolate power, not extra FFT resolution
            else:
                start=min(2048,max(1,math.ceil(a*4096/48000)))
                end=min(2049,max(start+1,math.ceil(b*4096/48000)))
            rows.append(f'    .word {start}, {end}')
        sections.append('spectrum_bins_'+name+':\n'+'\n'.join(rows))
    sections.append('spectrum_log_fraction:\n    .word '+', '.join(str(round(256*math.log2(1+i/16))) for i in range(16)))
    return '\n'.join(sections)


def source():
    names = ("capture.s", "spectrum_worker.s", "stream_capture.s", "coefficients.s",
             "fft_fixed.s", "fft_frontend.s", "spectrum_render.s", "command_adapter.s")
    return "\n".join((HERE / name).read_text(encoding="utf-8") for name in names) + "\n" + tables()
