"""Real plugin/menu/task on the user's image; synthetic DSP capture only."""
import hashlib
import json
import struct
import sys
import math
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tools.patch.spettro import CONTEXT_SIZE
import menu_cases, script_cases
READ, BEGIN, END = 0xC00141F8, 0xC0014368, 0xC00143E4
DSP_STATE, RING, RING_BYTES = 0xFF9031D0, 0x01C722A0, 19200
from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_PC,UC_ARM_REG_LR

def verify(image, blob, layout):
    s = layout['symbols']
    digest = hashlib.sha256(image).hexdigest()
    print('Boot spectrum image with real companion on virtual SD',flush=True)
    dev=menu_cases.boot(image[256:],files={script_cases.CARD_FILE:script_cases.archive([blob])},seconds=2.5,adapter=True)
    entry=script_cases.plugin_entry(dev,s['HOOK_RUNTIME'])
    if entry and dev.u32(entry+s['SCRIPT_ENTRY_STATE'])==s['SCRIPT_STATE_LOADED']:
        menu_cases.goto_plugin(dev,0);menu_cases.press(dev,'write',wait=.6)
    control=layout['entries']['scope_control']
    state=[0,RING_BYTES,RING,0]+[0]*7
    start=[0];ring=bytearray(RING_BYTES);events=[]
    wave=[round(16000*math.sin(2*math.pi*80*i/4096)) for i in range(4096)]
    def dsp(uc,at,size,data):
        args=[uc.reg_read(UC_ARM_REG_R0+i) for i in range(4)]
        ctx=dev.u32(control+24)
        if at==READ:
            src,dest,count,width=args
            if ctx in (0,0xFFFFFFFF) or not ctx+64<=dest<ctx+CONTEXT_SIZE:return
            assert width==2
            if src==DSP_STATE:
                elapsed=(dev.u32(0xC06A292C)-start[0])&0xFFFFFFFF
                pos=elapsed*48
                state[2]=RING+pos%4800*4
                for frame in range(max(0,pos-4800),pos):
                    v=wave[frame%4096];off=frame%4800*4
                    ring[off:off+4]=struct.pack('<hh',v,v)
                payload=struct.pack('<11I',*state)
            else:
                off=src-RING;amount=count*2
                assert 0<=off<off+amount<=RING_BYTES
                payload=ring[off:off+amount]
            uc.mem_write(dest,bytes(payload))
        elif at==BEGIN:
            selector=args[0];assert 1<=selector<=24
            state[0]=1;state[2]=RING;start[0]=dev.u32(0xC06A292C)
            state[3]=(0xFF90197C+(selector-1)*0x118 if selector<=16 else 0xFF901A98+(selector-17)*0x230)
            events.append(['begin',selector])
        elif at==END:
            state[0]=0;events.append(['end'])
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
    for at in (READ,BEGIN,END):dev.m.uc.hook_add(UC_HOOK_CODE,dsp,begin=at,end=at)
    def shot(name):
        ctx=dev.u32(control+24)
        return {'name':name,'requested':dev.u32(control),'status':dev.u32(control+28),
                'context':hex(ctx),'frame':hex(dev.u32(ctx+56)) if ctx not in (0,0xFFFFFFFF) else None,
                'part':dev.u32(s['HW_PART']),'asserts':dev.m.asserts}
    stages=[shot('before-open')]
    assert stages[0]['requested']==0
    print('Open native Tools / Spettro',flush=True)
    menu_cases.goto_group(dev,menu_cases.GROUP_TOOLS,0)
    title=menu_cases.text(dev,menu_cases.S_TITLE)
    assert title=='SPETTRO',title
    menu_cases.press(dev,'menu',wait=.4);dev.run(.25)
    stages.append(shot('spectrum-live'))
    print(json.dumps(stages[-1]),flush=True)
    ctx=dev.u32(control+24)
    assert ctx not in (0,0xFFFFFFFF) and dev.u32(ctx+56)!=0,'No completed spectrum bitmap'
    entry=dev.u32(s['APP_STATE']);store=entry+s['SCRIPT_ENTRY_STORE'];keys=layout['keys']
    script_cases.tap(dev,keys['BAR_1']);frozen=dev.u32(store)==1
    script_cases.tap(dev,keys['BAR_2']);bass=dev.u32(store+12)==1 and dev.u32(control+40)==1
    shift=dev.u32(store+4);script_cases.tap(dev,keys['BAR_3']);gain=dev.u32(store+4)==shift-1
    part=dev.u32(s['HW_PART']);script_cases.tap(dev,keys['PART_RIGHT']);dev.run(.15)
    changed=dev.u32(s['HW_PART'])==(part+1)%16 and dev.u32(control+4)==(part+1)%16
    script_cases.tap(dev,keys['BAR_1']);dev.run(.2)
    stages.append(shot('spectrum-bass-part2'))
    dispatched=[]
    def dispatch(uc,at,size,data):
        ptr=uc.reg_read(UC_ARM_REG_R0);dispatched.append(list(uc.mem_read(ptr+0xC,5)))
    dev.m.uc.hook_add(UC_HOOK_CODE,dispatch,begin=0xC0028380,end=0xC0028380)
    knob=[2,0,0,100,0];dev.m.send(knob);dev.run(.1)
    script_cases.tap(dev,keys['TRIGGER'])
    down=[4,6,0,100,1];up=[4,6,0,0,0]
    dev.m.send(down);dev.run(.1);dev.m.send(up);dev.run(.2)
    pad=dev.u32(s['HW_PART'])==6 and dev.u32(control+4)==6
    before_play=dev.u32(0xC06BC318)
    script_cases.tap(dev,keys['PLAY']);dev.run(.2)
    started=dev.u32(0xC06BC318)
    script_cases.tap(dev,keys['STOP']);dev.run(.2)
    stopped=dev.u32(0xC06BC318)
    menu_cases.press(dev,'exit',wait=.35)
    stages.append(shot('after-exit'))
    fault=dev.u32(entry+s['SCRIPT_ENTRY_FAULT'])
    checks={'freeze':frozen,'bassView':bass,'gain':gain,'partArrows':changed,'nativeKnob':knob in dispatched,
            'triggerPadEvents':down in dispatched and up in dispatched,'triggerPadSelection':pad,
            'nativeTransport':(before_play,started,stopped)==(0,1,0),
            'exitStopsCapture':state[0]==0 and dev.u32(control)==0 and dev.u32(s['APP_STATE'])==0,
            'pluginNoFault':fault==0,'noFirmwareAsserts':not dev.m.asserts}
    report={'ok':all(checks.values()),'checks':checks,'firmwareSha256':digest,
            'menuTitle':title,'stages':stages,'events':events,
            'scope':'Original firmware UI/plugin/task, synthetic DSP stream only; not physical validation'}
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', required=True, type=Path)
    parser.add_argument('--layout', required=True, type=Path)
    parser.add_argument('--plugin', required=True, type=Path)
    args = parser.parse_args()
    report = verify(args.patched.read_bytes(), args.plugin.read_bytes(), json.loads(args.layout.read_text()))
    print(json.dumps(report, indent=2))
    sys.exit(0 if report['ok'] else 1)
