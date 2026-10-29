"""The original contrast page with BLECHTRIBE's moving calibration picture."""
from menu_cases import boot, go, KILL

GLOBALS = 0xC033E6A0
DISPLAY = 0xC031B310
CIRCLE = bytes([0x1C,0x3E,0x7F,0x7F,0x7F,0x3E,0x1C])


def picture(dev):
    return dev.read(DISPLAY,1024)


def balls(frame):
    positions=[]
    for page in (3,4,5):
        row=frame[page*128:(page+1)*128]
        at=row.find(CIRCLE)
        if at<2 or at>118 or row!=bytes(at)+CIRCLE+bytes(128-at-7):
            return None
        positions.append(at)
    return positions


def contrast_page(dev):
    go(dev,8)
    dev.press(0x09,wait=0.12)
    for _ in range(24):
        if dev.screen()['page']==12:
            break
        dev.press(0x0C,wait=0.08)
    dev.run(0.12)


def cases(payload,flash=None):
    out=[]
    def add(name,ok,detail):
        out.append({'id':'menu:display_calibration_'+name,'ok':bool(ok),'detail':detail})
    dev=boot(payload,flash)
    contrast_page(dev)
    ptr=dev.u32(GLOBALS)
    before=dev.read(ptr+4,256)
    first=picture(dev)
    add('page',dev.screen()['number']==9 and dev.screen()['page']==12 and balls(first) is not None,
        'Global page 13 shows three balls and keeps the original contrast parameter')
    frames=[balls(first)]
    for _ in range(3):
        dev.run(0.12);frames.append(balls(picture(dev)))
    add('animation',all(f is not None for f in frames) and len({tuple(f) for f in frames if f})>1,
        'The normal UI frame hook animates the picture without user input')
    add('read_only',dev.read(ptr+4,256)==before,
        'Drawing leaves the complete 256-byte global settings block unchanged')
    dev.turn(-127,wait=0.16)
    low=dev.read(ptr+4,256)
    dev.turn(127,wait=0.16)
    high=dev.read(ptr+4,256)
    add('limits',low[30]==18 and high[30]==42,
        f'The original dial clamps contrast to 1..25 (raw bytes {low[30]}..{high[30]})')
    add('only_contrast',all(a==b==c for i,(a,b,c) in enumerate(zip(before,low,high)) if i!=30),
        'Dial changes touch only the existing contrast byte, not another global setting')
    add('value',first[256:384]!=picture(dev)[256:384] and balls(picture(dev)) is not None,
        'The displayed value follows the original parameter while the balls continue')
    dev.press(0x0C,wait=0.3)
    left=picture(dev)
    ref=boot(payload,flash,held=KILL)
    contrast_page(ref)
    ref.press(0x0C,wait=0.3)
    # rows 8 and 9 (blue) hold the foot of the tab with the counter: 14/21 with PLUGIN RUNTIME, 14/20 without the runtime
    leftover=[i for i,(a,b) in enumerate(zip(left[128:896],picture(ref)[128:896])) if (a^b)&(0xFC if i<128 else 0xFF)]
    add('next_page_clean',dev.screen()['page']==13 and ref.screen()['page']==13 and not leftover and not dev.m.asserts,
        f'EDIT to the next page draws it whole, as the firmware alone does (bytes of pages 1 to 6 that differ: {leftover[:8]})')
    contrast_page(dev)
    dev.press(0x0D,wait=0.2)
    exit_state=dev.screen()
    exit_clean=exit_state['number']!=9 and balls(picture(dev)) is None and not dev.m.asserts
    contrast_page(dev)
    dev.press(0x0E,wait=0.2)
    add('write',dev.screen()['number']==9 and dev.read(ptr+34,1)==bytes([42]) and not dev.m.asserts,
        'WRITE uses the original global handler with contrast unchanged')
    off=boot(payload,flash,held=KILL)
    contrast_page(off)
    add('failsafe',balls(picture(off)) is None and off.screen()['number']==9 and not off.m.asserts,
        'Holding EXIT at power-on leaves the original contrast page without the animation')
    off.press(0x0D,wait=0.2)
    exit_target=(exit_state['number'],bool(exit_state['window']))
    original_target=(off.screen()['number'],bool(off.screen()['window']))
    add('exit',exit_target==original_target and exit_clean and not off.m.asserts,
        f'EXIT matches the original screen and window state and removes the calibration picture: {exit_target}, original {original_target}')
    return out
