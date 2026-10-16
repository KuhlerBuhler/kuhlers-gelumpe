"""Build the relocatable bare ARM script runtime from generated contract tables."""
from pathlib import Path
import struct
from .arm import assemble

RUNTIME_FIELDS = dict(head=0, tail=4, arena=8, size=12, used=16, overflow=20,
    fuel=24, maxTicks=28, blob=32, code=36, constants=40, strings=44, lines=48,
    codeSize=52, lineCount=56, vars=60, started=64, ops=68, cost=72, offset=76,
    callDepth=80, event=84, entry=88, handled=92)

def build(include, origin=0x100000, glue=None):
    constants, tables = include.split('.align 4', 1)
    layout = '\n'.join(f'.equ RT_{k.upper()}, {v}' for k, v in RUNTIME_FIELDS.items())
    layout += '''
.equ RT_STACK, SCRIPT_CONTROL_HEADER_SIZE
.equ RT_CALLS, RT_STACK+LIM_STACK*4
.equ RT_BOUNDARIES, RT_CALLS+LIM_CALL_DEPTH*4
.equ RT_ARGC, RT_BOUNDARIES+LIM_CODE
.equ RT_FNSTATE, RT_ARGC+LIM_CODE
.equ RT_NEED, RT_FNSTATE+LIM_CODE
.equ RT_DEEP, RT_NEED+LIM_CODE
.equ RT_DEPTH, RT_DEEP+LIM_CODE
.equ RT_WORK, RT_DEPTH+LIM_CODE
.equ RT_RING, RT_WORK+LIM_CODE*4
.equ RT_LED, RT_RING+SCRIPT_RING*SCRIPT_EVENT_RECORD_SIZE
.equ RT_DISPLAY, RT_LED+SCRIPT_LED_SIZE
.equ RT_KNOBS, RT_DISPLAY+SCRIPT_DISPLAY_BYTES
.equ RT_TOUCH, RT_KNOBS+SCRIPT_KNOBS*4
.equ RT_APPS, RT_TOUCH+4
.equ SCRIPT_RUNTIME_SIZE, RT_APPS+SCRIPT_APPS_STATE_SIZE
'''
    layout += '\n'+ '\n'.join(f'.equ RT_{name}, SCRIPT_CONTROL_{name}' for name in ['ARMED','READY','RING_HEAD','RING_TAIL','FRAME_START','FRAME_ACTIVE','CURSOR_ENTRY','CURSOR_EVENT','CURSOR_ARGS','CURSOR_RING_END','CURSOR_PHASE','CAPTURE_MASK','FRAMES','PAUSED'])+'\n'
    source = constants+'\n'+layout+'\n'+Path(__file__).with_suffix('.s').read_text()
    source += arithmetic_source()+errors_source()+'\n.align 4\n'+tables
    code = assemble(source, origin=origin)
    if glue:
        data = bytearray(code.bytes)
        table = code.symbols['script_api_table']-origin
        size = code.symbols['SCRIPT_API_ENTRY_SIZE']
        count = code.symbols['SCRIPT_API_ENTRIES']
        for key, address in glue.items():
            api_id = code.symbols.get(key) if isinstance(key,str) else key
            if not isinstance(api_id,int) or not 0 <= api_id < count or not data[table+api_id*size]:
                raise ValueError(f'unknown script API: {key}')
            if not isinstance(address,int) or not 0 <= address <= 0xffffffff or address % 4:
                raise ValueError(f'ARM glue address must be an aligned u32: {address}')
            struct.pack_into('<I',data,table+api_id*size+12,address)
        code.sections[0] = (origin,bytes(data))
    return code

def arithmetic_source():
    out = []
    instructions = {'add':'add r0, r0, r1','sub':'sub r0, r0, r1',
        'and':'and r0, r0, r1','or':'orr r0, r0, r1','xor':'eor r0, r0, r1',
        'shl':'and r1, r1, #31\n    mov r0, r0, lsl r1',
        'shr':'and r1, r1, #31\n    mov r0, r0, asr r1'}
    for name in ['add','sub','mul','div','mod','and','or','xor','shl','shr','eq','ne','lt','le','gt','ge']:
        out += [f'op_{name}:','    sub r9, r9, #1','    ldr r1, [r11, r9, lsl #2]',
                '    sub r2, r9, #1','    ldr r0, [r11, r2, lsl #2]']
        if name in instructions: out += ['    '+instructions[name]]
        elif name in ['eq','ne','lt','le','gt','ge']:
            out += ['    cmp r0, r1','    mov r0, #0',f'    mov{name} r0, #1']
        elif name == 'mul':
            out += ['    mov r3, #0', 'mul_loop:', '    tst r1, #1', '    addne r3, r3, r0',
                    '    mov r0, r0, lsl #1','    movs r1, r1, lsr #1','    bne mul_loop','    mov r0, r3']
        else:
            out += ['    cmp r1, #0','    beq e_div_zero','    bl signed_divide']
            if name == 'mod': out += ['    mov r0, r1']
            out += ['    sub r2, r9, #1']
        out += ['    str r0, [r11, r2, lsl #2]','    b run_next']
    return '\n'.join(out)+'\n'


def errors_source():
    out=[]
    names=['fuel','bad_opcode','bounds','div_zero','stack','bad_jump','time','call_depth',
           'bad_const','bad_string','bad_var','api_unknown','api_argc','api_event','api_arg',
           'truncated','magic','format_version','api_version','limits','bad_size','checksum',
           'bad_handler','stack_mismatch','recursion','bad_lines','pool_budget']
    for prefix, target in [('e','run_finish'),('l','load_return'),('v','verify_return'),('vf','vf_return')]:
        for name in names:
            out += [f'{prefix}_{name}:',f'    mov r0, #ERR_{name.upper()}',f'    b {target}']
            if prefix in ['v','vf']:
                out += [f'{prefix}_{name}_no_offset:', '    mvn r8, #0', f'    b {prefix}_{name}']
    return '\n'.join(out)+'\n'
