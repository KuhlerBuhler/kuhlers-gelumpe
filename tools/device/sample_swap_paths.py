"""Measure bounded RAM to DSP and card to DSP paths on an expendable loaded sample.

Default is offline. --execute needs an own original Sampler VSB, an explicitly
unused loaded slot and a stopped or playback confirmation. Only CPU RAM and the
confirmed DSP span are written. Card access is read only; flash is never called.
Native FatFs calls remain unbounded: an unconfirmed EXEC stops all communication.
A DSP fault is latched until a power cycle; the tool never retries or clears it.
"""
import argparse
import json
import secrets
import struct
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'patch'))
import arm
import sample_swap_probe as old

STUB, RESULT = old.STUB, old.STUB + 0x300
IO_CODE, IO_STATE, MARKER = 0xC2760000, 0xC276F000, 0xC276EFFC
FIL, PATH, GOT = 0xC2770000, 0xC2771000, 0xC2771100
BACKUP, VERIFY = 0xC2780000, 0xC2790000
TIMER, TIMER_HZ, MAGIC = old.TIMER, old.TIMER_HZ, old.MAGIC
MMC_CLK = 0x01C40004
FS_OPEN, FS_READ, FS_CLOSE, FS_SEEK = 0xC009DB60, 0xC009DD74, 0xC009E3DC, 0xC009E404
BANK, LIVE_PTR = 0xC08B2940, 0xC033E6A4
MAPPING_TABLES = ((0xC035738C,32,16),(0xC035F06C,16,8),(0xC0350644,8,2))
MARK = 0x42535750
BUSY_ATTEMPTS, BUSY_DELAY = 8, 0.01
R_STATUS, R_COMPLETED, R_BEFORE, R_AFTER, R_PERIOD = 2, 3, 4, 5, 6
R_FILE, R_GOT, R_OPEN, R_CLOSE, R_CLOCK, R_CLOCK_AFTER, R_SEEK, R_READ, R_IO = range(7,16)
REGIONS = ((STUB, 0x400), (IO_CODE, 0x2000), (MARKER, 8), (FIL, 0x1000),
           (PATH, 0x100), (GOT, 4), (BACKUP, 65536), (VERIFY, 65536))
SPANS = ((0xC0000CA8, 0x190), (FS_OPEN, FS_READ-FS_OPEN),
         (FS_READ, 0x244), (FS_CLOSE, FS_SEEK-FS_CLOSE), (FS_SEEK, 0x100),
         (0xC004EBD4, 0x208))


def check_regions():
    for i,(a,n) in enumerate(REGIONS):
        if n<=0 or a+n>0xC4000000:
            raise ValueError('invalid scratch region')
        for b,m in REGIONS[i+1:]:
            if a < b+m and b < a+n:
                raise ValueError('scratch regions overlap')


class Link(old.Link):
    def read(self, address, count):
        return b''.join(super(Link,self).read(address+at,min(2048,self.largest,count-at))
                        for at in range(0,count,min(2048,self.largest)))

    def write_at(self, address, data):
        for at in range(0,len(data),min(2048,self.largest)):
            part=data[at:at+min(2048,self.largest)]
            dest=address+at
            crc=zlib.crc32(part)
            raw=self.call(0x62,struct.pack('<3I',dest,len(part),crc),0x6A)
            if raw!=struct.pack('<3I',0,dest,len(part)):
                raise ValueError('WRITE BEGIN refused')
            raw=self.call(0x63,part,0x6B)
            if raw!=struct.pack('<4I',0,dest,len(part),crc):
                raise ValueError('WRITE DATA status, range or CRC mismatch')
            if self.read(dest,len(part))!=part:
                raise ValueError('CPU upload readback differs')


def assemble(text):
    sections=arm.assemble(text,origin=STUB).sections
    if len(sections)!=1 or sections[0][0]!=STUB or len(sections[0][1])>0x300:
        raise ValueError('driver exceeds EXEC code region')
    return sections[0][1]


def prologue(token):
    return f'''
    push {{r4-r11, r12, lr}}
    ldr r4, ={RESULT}
    ldr r1, ={token}
    cmp r0, r1
    bne invalid
    str r1, [r4, #4]
    ldr r9, ={TIMER}
    ldr r0, [r9, #0x18]
    str r0, [r4, #{R_PERIOD*4}]
    ldr r1, ={TIMER_HZ-1}
    cmp r0, r1
    bne timer_bad
    ldr r0, [r9, #0x20]
    and r0, r0, #0xc0
    cmp r0, #0x80
    bne timer_bad
    ldr r0, [r9, #0x24]
    tst r0, #1
    beq timer_bad
'''


def epilogue():
    return f'''
timer_bad:
    mov r0, #4
    str r0, [r4, #{R_STATUS*4}]
finish:
    ldr r0, ={MAGIC}
    str r0, [r4]
    pop {{r4-r11, r12, pc}}
invalid:
    mov r0, #0
    pop {{r4-r11, r12, pc}}
'''


def io_driver(operation, buffer, offset, length, token, entry=IO_CODE):
    return assemble(prologue(token)+f'''
    ldr r0, [r9, #0x10]
    str r0, [r4, #{R_BEFORE*4}]
    mov r0, #{operation}
    ldr r1, ={buffer}
    ldr r2, ={offset}
    ldr r3, ={length//2}
    ldr r12, ={entry}
    blx r12
    str r0, [r4, #{R_STATUS*4}]
    str r1, [r4, #{R_COMPLETED*4}]
    ldr r0, [r9, #0x10]
    str r0, [r4, #{R_AFTER*4}]
    b finish
'''+epilogue())


def scan_driver(token):
    return assemble(prologue(token)+f'''
    ldr r6, ={VERIFY}
    mov r1, #0
    mov r2, #32
clear_usage:
    subs r2, r2, #1
    str r1, [r6, r2, lsl #2]
    bne clear_usage
    mov r8, #0
    ldr r0, [r9, #0x10]
    str r0, [r4, #{R_BEFORE*4}]
    ldr r5, ={BANK}
    mov r7, #250
bank_pattern:
    mov r0, r5
    bl pattern_parts
    add r5, r5, #0x4000
    subs r7, r7, #1
    bne bank_pattern
    ldr r0, ={LIVE_PTR}
    ldr r0, [r0]
    tst r0, #3
    bne scan_bad
    ldr r1, =0xC0000000
    cmp r0, r1
    blo scan_bad
    ldr r1, =0xC3FFBFFC
    cmp r0, r1
    bhi scan_bad
    add r0, r0, #4
    bl pattern_parts
    ldr r0, [r9, #0x10]
    str r0, [r4, #{R_AFTER*4}]
    str r8, [r4, #{R_COMPLETED*4}]
    b finish
scan_bad:
    mov r0, #15
    str r0, [r4, #{R_STATUS*4}]
    str r8, [r4, #{R_COMPLETED*4}]
    b finish
pattern_parts:
    add r11, r0, #0x800
    add r11, r11, #8
    mov r10, #16
part:
    .word 0xe1db00b0 ; ldrh r0, [r11]
    cmp r0, #1024
    bhs out_of_range
    mov r1, r0, lsr #3
    and r2, r0, #7
    mov r3, #1
    mov r3, r3, lsl r2
    ldrb r12, [r6, r1]
    orr r12, r12, r3
    strb r12, [r6, r1]
    b next_part
out_of_range:
    ldr r0, [r4, #{R_GOT*4}]
    add r0, r0, #1
    str r0, [r4, #{R_GOT*4}]
next_part:
    add r8, r8, #1
    add r11, r11, #0x330
    subs r10, r10, #1
    bne part
    bx lr
'''+epilogue())


def used_ids(bitset):
    if len(bitset)!=128: raise ValueError('usage bitmap has the wrong length')
    return {i for i in range(1024) if bitset[i//8] & (1 << (i%8))}


def card_driver(file_offset,length,token,write=False,clock_mhz=None,offset=0,entry=IO_CODE):
    clock=''
    if clock_mhz is not None:
        divider=5 if clock_mhz==12.5 else 2
        clock=f'''
    mov r11, #1
    bic r0, r10, #0x100
    str r0, [r6]
    mov r0, #{divider}
    str r0, [r6]
    orr r0, r0, #0x100
    str r0, [r6]
    ldr r1, [r6]
    cmp r0, r1
    bne clock_bad
'''
    transfer=f'''
    mov r0, #1
    ldr r1, ={VERIFY}
    ldr r2, ={offset}
    ldr r3, ={length//2}
    ldr r12, ={entry}
    blx r12
    str r0, [r4, #{R_STATUS*4}]
    str r0, [r4, #{R_IO*4}]
    str r1, [r4, #{R_COMPLETED*4}]
''' if write else ''
    return assemble(prologue(token)+f'''
    ldr r5, ={FIL}
    ldr r6, ={MMC_CLK}
    ldr r10, [r6]
    str r10, [r4, #{R_CLOCK*4}]
    mov r11, #0
    mov r0, r5
    ldr r1, ={PATH}
    mov r2, #1
    ldr r12, ={FS_OPEN}
    blx r12
    str r0, [r4, #{R_FILE*4}]
    cmp r0, #0
    bne open_bad
    mov r0, #1
    str r0, [r4, #{R_OPEN*4}]
    ldr r0, =0x105
    cmp r10, r0
    beq clock_valid
    ldr r0, =0x102
    cmp r10, r0
    bne clock_bad
clock_valid:
{clock}
    mov r0, r5
    ldr r1, ={file_offset}
    ldr r12, ={FS_SEEK}
    blx r12
    str r0, [r4, #{R_FILE*4}]
    str r0, [r4, #{R_SEEK*4}]
    cmp r0, #0
    bne file_bad
    ldr r0, [r9, #0x10]
    str r0, [r4, #{R_BEFORE*4}]
    mov r0, r5
    ldr r1, ={VERIFY}
    ldr r2, ={length}
    ldr r3, ={GOT}
    ldr r12, ={FS_READ}
    blx r12
    str r0, [r4, #{R_FILE*4}]
    str r0, [r4, #{R_READ*4}]
    cmp r0, #0
    bne file_bad
    ldr r1, ={GOT}
    ldr r1, [r1]
    str r1, [r4, #{R_GOT*4}]
    ldr r0, ={length}
    cmp r0, r1
    bne file_bad
{transfer}
    ldr r0, [r9, #0x10]
    str r0, [r4, #{R_AFTER*4}]
    b close
open_bad:
    mov r0, #10
    str r0, [r4, #{R_STATUS*4}]
    b finish
clock_bad:
    mov r0, #11
    str r0, [r4, #{R_STATUS*4}]
    b close
file_bad:
    mov r0, #12
    str r0, [r4, #{R_STATUS*4}]
close:
    mov r0, r5
    ldr r12, ={FS_CLOSE}
    blx r12
    str r0, [r4, #{R_CLOSE*4}]
    cmp r0, #0
    movne r0, #13
    strne r0, [r4, #{R_STATUS*4}]
    cmp r11, #0
    beq clock_restored
    ldr r0, [r6]
    bic r0, r0, #0x100
    str r0, [r6]
    bic r0, r10, #0x100
    str r0, [r6]
    str r10, [r6]
clock_restored:
    ldr r0, [r6]
    str r0, [r4, #{R_CLOCK_AFTER*4}]
    cmp r0, r10
    movne r0, #14
    strne r0, [r4, #{R_STATUS*4}]
    b finish
'''+epilogue())


class Driver:
    def __init__(self,link,entry):
        self.link,self.entry=link,entry
        self.busy_retries=0

    def call(self,blob,token):
        self.link.write_at(RESULT,bytes(64))
        self.link.write_at(STUB,blob)
        started=time.monotonic()
        try:
            self.link.execute(token)
        except BaseException as error:
            raise RuntimeError('EXEC completion unconfirmed; no retry or cleanup sent; power cycle the device') from error
        wall=time.monotonic()-started
        w=struct.unpack('<16I',self.link.read(RESULT,64))
        if w[0]!=MAGIC or w[1]!=token:
            raise RuntimeError('completion marker differs; no cleanup sent; power cycle the device')
        result=dict(status=w[R_STATUS],completed=w[R_COMPLETED],words=list(w))
        if w[R_STATUS]==0:
            ticks=old.elapsed(w[R_BEFORE],w[R_AFTER],w[R_PERIOD])
            valid=bool(ticks) and wall<1 and ticks<TIMER_HZ//2
            result.update(timing_valid=valid,ticks=ticks if valid else None,
                          milliseconds=ticks/TIMER_HZ*1000 if valid else None)
        return result

    def scan(self):
        token=secrets.randbits(31)|1
        result=self.call(scan_driver(token),token)
        if result['status'] or result['completed']!=251*16:
            raise RuntimeError('pattern usage scan incomplete; no DSP access attempted')
        return used_ids(self.link.read(VERIFY,128))

    def _retry_busy(self,make_blob,is_busy):
        for attempt in range(BUSY_ATTEMPTS):
            token=secrets.randbits(31)|1
            result=self.call(make_blob(token),token)
            if not is_busy(result) or attempt==BUSY_ATTEMPTS-1:
                result['busy_retries']=attempt
                return result
            self.busy_retries+=1
            time.sleep(BUSY_DELAY)

    def io(self,operation,buffer,offset,length):
        result=self._retry_busy(
            lambda token:io_driver(operation,buffer,offset,length,token,self.entry),
            lambda r:r['status']==2 and r['completed']==0)
        io_ok(result,length)
        return result

    def card(self,offset,length,write=False,clock_mhz=None,dsp_offset=0):
        def retryable(r):
            w=r['words']
            return (write and r['status']==2 and r['completed']==0 and w[R_IO]==2
                    and w[R_OPEN]==1 and w[R_GOT]==length
                    and all(w[i]==0 for i in (R_SEEK,R_READ,R_FILE,R_CLOSE))
                    and w[R_CLOCK]==w[R_CLOCK_AFTER])
        result=self._retry_busy(
            lambda token:card_driver(offset,length,token,write,clock_mhz,dsp_offset,self.entry),retryable)
        if result['status']:
            raise RuntimeError(f"card path failed: status {result['status']}, native status {result['words'][R_FILE]}; no further retry or cleanup sent")
        if write: io_ok(result,length)
        elif result['words'][R_GOT]!=length: raise RuntimeError('short card read')
        return result


def io_ok(result,length):
    if result['status'] or result['completed']!=length//2:
        raise RuntimeError(f"bounded DSP operation failed: status {result['status']}, completed {result['completed']} words; no further retry or cleanup sent; power cycle the device")


def card_pcm(read,slot,length):
    head=bytes(read(0,4096))
    if len(head)!=4096 or head[:16]!=b'e2s sample all\x1a\0':
        raise ValueError('sample file header differs')
    start=struct.unpack_from('<I',head,16+(slot-1)*4)[0]
    if start<4096: raise ValueError('slot has no sample in the card index')
    riff=bytes(read(start,12))
    if len(riff)!=12 or riff[:4]!=b'RIFF' or riff[8:]!=b'WAVE': raise ValueError('slot does not point to RIFF/WAVE')
    end=start+8+struct.unpack_from('<I',riff,4)[0]
    if end>0xffffffff or end<start+12: raise ValueError('invalid RIFF extent')
    at=start+12
    fmt=None
    data=None
    for _ in range(256):
        if at+8>end: break
        chunk=bytes(read(at,8))
        if len(chunk)!=8: raise ValueError('short chunk header')
        size=struct.unpack_from('<I',chunk,4)[0]
        if at+8+size>end: raise ValueError('chunk exceeds RIFF extent')
        if chunk[:4]==b'fmt ':
            raw=bytes(read(at+8,min(size,16)))
            if len(raw)!=16: raise ValueError('short format')
            fmt=struct.unpack('<HHIIHH',raw)
        if chunk[:4]==b'data': data=(at+8,size)
        at+=8+size+(size&1)
    if fmt is None or fmt[0]!=1 or fmt[1] not in (1,2) or fmt[5]!=16 or fmt[4]!=fmt[1]*2:
        raise ValueError('measurement requires PCM16; other formats need conversion before comparison')
    if data is None or data[1]<length: raise ValueError('sample PCM is shorter than requested')
    return data


def arguments(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--plan',action='store_true')
    parser.add_argument('--vsb',type=Path)
    parser.add_argument('--slot',type=int)
    parser.add_argument('--kib',type=int,default=1)
    parser.add_argument('--unused-confirmed',action='store_true')
    parser.add_argument('--stopped-confirmed',action='store_true')
    parser.add_argument('--playback-confirmed',action='store_true')
    parser.add_argument('--clock-mhz',type=float)
    parser.add_argument('--path',default='SD:KORG/blechtribe/Sample/e2sSample.all')
    parser.add_argument('--json',type=Path)
    a=parser.parse_args(argv)
    if not 1<=a.kib<=64 or a.slot is not None and not 501<=a.slot<=999:
        raise ValueError('--kib must be 1..64 and --slot 501..999')
    if a.clock_mhz not in (None,12.5,25): raise ValueError('only 12.5 or 25 MHz is supported; no High Speed mode')
    if not a.path.startswith('SD:') or '\0' in a.path or len(a.path.encode('ascii'))>=256:
        raise ValueError('expected an ASCII SD: file path shorter than 256 bytes')
    if a.execute and (a.plan or not a.vsb or a.slot is None or not a.unused_confirmed or a.stopped_confirmed==a.playback_confirmed):
        raise ValueError('execution needs --vsb --slot --unused-confirmed and exactly one playback/stopped confirmation')
    check_regions()
    return a


def identity_target(link,slot):
    """Require the same index through the import number and every mapping table."""
    index=slot-1
    name=link.read(old.NAMES+index*32,32)
    key=struct.unpack_from('<H',name,30)[0]-50
    if key!=index: raise ValueError('target needs an identity import number')
    chain=[]
    for base,stride,field in MAPPING_TABLES:
        address=base+key*stride+field
        raw=link.read(address,2)
        chain.append((address,raw))
        key=struct.unpack('<H',raw)[0]
        if key!=index: raise ValueError('target needs identity at every sample mapping step')
    meta=link.read(old.META+index*0x45C,0x45C)
    if struct.unpack_from('<H',meta,22)[0]!=index:
        raise ValueError('sample metadata index differs from its mapping')
    return chain


def resolve_index(snapshot,index):
    names,tables=snapshot
    key=struct.unpack_from('<H',names,index*32+30)[0]-50
    if key<0: return None
    keys=[key]
    for table,(_,stride,field) in zip(tables,MAPPING_TABLES):
        if not 0<=key<1000: raise ValueError('mapping key is outside the measured tables')
        key=struct.unpack_from('<H',table,key*stride+field)[0]
        keys.append(key)
    if not 0<=key<1000: raise ValueError('physical sample index is outside the measured table')
    return keys


def assert_unused(link,slot,used):
    names=link.read(old.NAMES,1000*32)
    tables=[link.read(base,1000*stride) for base,stride,_ in MAPPING_TABLES]
    snapshot=(names,tables)
    index=slot-1
    keys=resolve_index(snapshot,index)
    if keys is None or any(key!=index for key in keys):
        raise ValueError('target sample mapping no longer has identity at every step')
    for raw_id in sorted(used):
        candidates={i for i in (raw_id-2,raw_id-1,raw_id) if 0<=i<1000}
        if not candidates: raise ValueError(f'raw sample ID {raw_id} cannot be resolved conservatively')
        for visible_index in candidates:
            try: keys=resolve_index(snapshot,visible_index)
            except ValueError as error:
                raise ValueError(f'raw sample ID {raw_id} cannot be resolved conservatively') from error
            if keys is not None and keys[-1]==index:
                raise ValueError(f'target is referenced by raw sample ID {raw_id} through the sample mappings')


def target_span(meta,cursor,length):
    if len(meta)!=0x45c or meta[11]!=1:
        raise ValueError('target slot is not loaded')
    offset,size=struct.unpack_from('<II',meta)
    if offset&1 or not 0x365ec0<=offset<cursor<=0x1c65ec0 or offset+size>cursor:
        raise ValueError('target is outside the current DSP allocation or not halfword aligned')
    skip=(-offset)%32
    if size<skip+length:
        raise ValueError('target is too short for the aligned PCM span')
    span=bytearray(meta)
    struct.pack_into('<II',span,0,offset+skip,size-skip)
    return old.target(span,cursor,length),skip


def validate_device(link,firmware):
    import sample_swap_io
    sample_swap_io.validate_firmware(firmware)
    link.info()
    old.swap_off(link)
    spans=set(SPANS) | {(address,count) for address,count,_ in sample_swap_io.NATIVE_SPANS}
    for address,count in sorted(spans):
        start=address-0xC0000000+0x100
        if link.read(address,count)!=firmware[start:start+count]:
            raise ValueError(f'native routine differs at {address:#x}; nothing written')
    return sample_swap_io


def scan_usage(link,firmware):
    """Read bank and live raw oscillator IDs through one finite RAM-only EXEC."""
    validate_device(link,firmware)
    preserved=[(at,link.read(at,n)) for at,n in ((STUB,0x400),(VERIFY,128))]
    token=secrets.randbits(31)|1
    result=Driver(link,IO_CODE).call(scan_driver(token),token)
    complete=result['status']==0 and result['completed']==251*16
    used=used_ids(link.read(VERIFY,128)) if complete else None
    for at,data in reversed(preserved): link.write_at(at,data)
    if not complete: raise RuntimeError('pattern usage scan incomplete; CPU scratch restored; no DSP access attempted')
    return used


def run(link,firmware,a):
    sample_swap_io=validate_device(link,firmware)
    old.swap_off(link)
    length=a.kib*1024
    previous=link.read(MARKER,8)
    marker,fault=struct.unpack('<II',previous)
    if marker==MARK and fault:
        raise RuntimeError('previous DSP transport fault is latched; power cycle before retry; nothing written')
    chain=identity_target(link,a.slot)
    index=a.slot-1
    table_ranges=((old.META+index*0x45C,0x45C),(old.PLAYBACK+index*16,16),
                  (old.NAMES+index*32,32),(old.CURSOR,4))
    tables=[link.read(at,n) for at,n in table_ranges]
    dsp_offset,pcm_skip=target_span(tables[0],struct.unpack('<I',tables[3])[0],length)
    code,symbols=sample_swap_io.build_code(origin=IO_CODE,state=IO_STATE)
    if len(code)>0x2000: raise ValueError('bounded I/O exceeds its declared region')
    preserved=[(at,link.read(at,n)) for at,n in REGIONS]
    link.write_at(IO_CODE,code)
    if marker!=MARK: link.write_at(MARKER,struct.pack('<II',MARK,0))
    link.write_at(PATH,a.path.encode('ascii')+b'\0')
    driver=Driver(link,symbols['transfer'])
    used=driver.scan()
    try:
        if used & {a.slot-1,a.slot,a.slot+1}:
            raise ValueError('target or conservative neighbouring raw ID is referenced by a bank/live part')
        assert_unused(link,a.slot,used)
    except ValueError as error:
        for address,data in reversed(preserved): link.write_at(address,data)
        raise RuntimeError(str(error)+'; no DSP access attempted') from error
    driver.io(0,BACKUP,dsp_offset,length)
    backup=link.read(BACKUP,length)
    driver.io(0,VERIFY,dsp_offset,length)
    if link.read(VERIFY,length)!=backup: raise RuntimeError('two initial DSP reads differ; no writes attempted')
    def card_read(offset,n):
        driver.card(offset,n,clock_mhz=a.clock_mhz)
        return link.read(VERIFY,n)
    pcm_offset,pcm_length=card_pcm(card_read,a.slot,length+pcm_skip)
    pcm_offset+=pcm_skip
    if card_read(pcm_offset,length)!=backup:
        raise RuntimeError('card PCM differs from loaded DSP span; no DSP writes attempted')
    def restore_and_stop(reason):
        if link.read(IO_STATE,4)!=bytes(4):
            raise RuntimeError(reason+'; DSP fault latched; no restoration attempted; power cycle')
        driver.io(1,BACKUP,dsp_offset,length)
        driver.io(0,VERIFY,dsp_offset,length)
        if link.read(VERIFY,length)!=backup:
            raise RuntimeError(reason+'; bounded restoration did not verify; backup retained; power cycle')
        raise RuntimeError(reason+'; original DSP bytes restored and verified; CPU scratch retained')
    altered=bytes(v^1 for v in backup)
    link.write_at(VERIFY,altered)
    ram=driver.io(1,VERIFY,dsp_offset,length)
    driver.io(0,VERIFY,dsp_offset,length)
    if link.read(VERIFY,length)!=altered: restore_and_stop('changed RAM transfer differs')
    driver.io(1,BACKUP,dsp_offset,length)
    driver.io(0,VERIFY,dsp_offset,length)
    if link.read(VERIFY,length)!=backup: restore_and_stop('RAM test restoration differs')
    link.write_at(VERIFY,altered)
    driver.io(1,VERIFY,dsp_offset,length)
    driver.io(0,VERIFY,dsp_offset,length)
    if link.read(VERIFY,length)!=altered: restore_and_stop('card test precondition differs')
    card=driver.card(pcm_offset,length,True,a.clock_mhz,dsp_offset)
    driver.io(0,VERIFY,dsp_offset,length)
    if link.read(VERIFY,length)!=backup: restore_and_stop('card transfer restoration differs')
    for (address,count),before in zip(table_ranges,tables):
        if link.read(address,count)!=before: raise RuntimeError('sample metadata or allocation cursor changed')
    if any(link.read(at,2)!=before for at,before in chain): raise RuntimeError('sample mapping changed')
    # All DSP calls returned and the original PCM has been verified before CPU scratch is restored.
    for address,data in reversed(preserved): link.write_at(address,data)
    if not ram.get('timing_valid',True) or not card.get('timing_valid',True):
        raise RuntimeError('timing interval is ambiguous; no throughput reported; original DSP bytes and CPU scratch restored and verified')
    describe=lambda r: dict(milliseconds=r['milliseconds'],kib_per_second=length/1024*TIMER_HZ/r['ticks'],busy_retries=r.get('busy_retries',0))
    return dict(bytes=length,slot=a.slot,mode='playing' if a.playback_confirmed else 'stopped',
                clock_mhz=a.clock_mhz or 'unchanged',ram_to_dsp=describe(ram),card_to_dsp=describe(card),
                card_open_seek_excluded=True,card_read_after_verification=True,card_pcm_bytes=pcm_length,card_offset=pcm_offset,
                sample_pcm_skip=pcm_skip,dsp_offset=dsp_offset,
                host_busy_retries=getattr(driver,'busy_retries',0),
                card_status=card['words'][R_FILE],card_close_status=card['words'][R_CLOSE],
                clock_before=card['words'][R_CLOCK],clock_after=card['words'][R_CLOCK_AFTER],
                dsp_restored=True,tables_equal=True,cpu_scratch_restored=True,
                raw_usage_checked=True,raw_usage_count=len(used),conservative_ids_checked=[a.slot-1,a.slot,a.slot+1],
                audio_verified=False,dsp_limit_verified=False,native_fatfs_bounded=False)


def main(argv=None):
    a=arguments(argv)
    if not a.execute:
        print(json.dumps(dict(mode='offline plan',device='no device contact',bytes=a.kib*1024,slot=a.slot,
                              paths=['RAM -> bounded DSP','card read -> bounded DSP within one EXEC'],
                              clock_mhz=a.clock_mhz or 'unchanged',requires='loaded expendable unused PCM16 sample matching the card',
                              limitation='native FatFs calls can still block; unknown EXEC completion sends no cleanup'),indent=2))
        return
    firmware,build=old.own_firmware(a.vsb)
    from led_show import mido_ask
    ask=mido_ask()
    found=ask([0xF0,0x42,0x50,0,0,0xF7])
    if len(found)<8 or found[:4]!=[0xF0,0x42,0x50,1]: raise ValueError('no Electribe discovery reply')
    result=run(Link(ask,found[4]&15,found[6]),firmware,a)
    result['build']=build
    text=json.dumps(result,indent=2)
    print(text)
    if a.json: a.json.write_text(text+'\n')


if __name__=='__main__':
    try: main()
    except (ValueError,RuntimeError,TimeoutError,OSError) as error: raise SystemExit(str(error))
