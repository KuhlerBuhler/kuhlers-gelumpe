"""Resource ownership against the firmware scheduler, with generated probe calls."""
import struct

import swap_cases as c
import native_dsp_acquire as acquire
import native_dsp_scope as scope
import sample_swap_io as io

CODE, PEER, DATA = 0xC100B000, 0xC100C000, 0xC100D000


def contention(payload, *, action='release', native=False):
    from native_dsp_scope_cases import runtime_symbols
    box = c.Box(payload, None, {500: ('Own contention', 100)}, [500], cap=0x100)
    symbols = runtime_symbols(payload)
    if symbols is None:
        raise ValueError('installed ownership guard required')
    m, uc, regs = box.m, box.m.uc, box.m.A
    put = lambda at, value: uc.mem_write(at, struct.pack('<I', value))
    put(c.spec.STATE + c.spec.OFF['POSTED'], 0x7FFFFFFF)
    put(DATA, 0xFFFFFFFF)
    before = {name: box.state(name) for name in ('MODE', 'GEN', 'TSTATE')}
    if box.dev.call(scope.ACQUIRE, 1) != 0:
        raise ValueError('controlled resource lease unavailable')
    call = c.spec.arm.assemble(f'''
        push {{r4-r6, lr}}
        .word 0xE10F4000
        mov r0, #1
        mov r1, #1
        bl {symbols['native_resource_take']}
        mov r5, r0
        .word 0xE121F004
        cmp r5, #0
        bne done
        mov r0, #1
        bl {io.RELEASE}
    done:
        mov r0, r5
        pop {{r4-r6, pc}}
    ''', origin=CODE)
    if native:
        call = c.spec.arm.assemble(f"push {{r4, lr}}\nldr r0, ={io.DSP_MIN}\nldr r1, ={c.spec.STAGE}\nmov r2, #32\nmov r3, #2\nbl 0xC00141F8\npop {{r4, pc}}", origin=CODE)
    uc.mem_write(CODE, call.bytes)
    registers = [regs.UC_ARM_REG_R0 + i for i in range(13)] + [regs.UC_ARM_REG_SP, regs.UC_ARM_REG_LR,
                                                               regs.UC_ARM_REG_PC, regs.UC_ARM_REG_CPSR]
    delayed, peers, saved = [], [], {}
    stage = [0]
    clock = {}
    hooks = []
    def entered(machine, *_):
        clock.update(tick=box.u32(acquire.TICK), ns=m.time_ns)
    hooks.append(uc.hook_add(c.unicorn.UC_HOOK_CODE, entered, begin=CODE, end=CODE))
    def delay(machine, *_):
        link = machine.reg_read(regs.UC_ARM_REG_LR)
        if symbols['native_resource_take'] <= link < symbols['resource_current']:
            delayed.append((box.u32(acquire.CURRENT_TASK), machine.reg_read(regs.UC_ARM_REG_R0)))
    hooks.append(uc.hook_add(c.unicorn.UC_HOOK_CODE, delay, begin=acquire.DELAY, end=acquire.DELAY))

    for index, body in enumerate((f'mov r0, #1\nbl {scope.ACQUIRE}\nldr r1, ={DATA}\nstr r0, [r1]\nmov r0, #1\nbl {io.RELEASE}',
                                  f'mov r0, #1\nbl {io.RELEASE}')):
        at = PEER + index * 0x100
        code = c.spec.arm.assemble('push {r4, lr}\n' + body + '\npop {r4, lr}\npeer_return:\nnop', origin=at)
        uc.mem_write(at, code.bytes)
        def returned(machine, *_, index=index):
            values = saved.pop(index)
            for register, value in zip(registers, values):
                machine.reg_write(register, value)
        ret = code.symbols['peer_return']
        hooks.append(uc.hook_add(c.unicorn.UC_HOOK_CODE, returned, begin=ret, end=ret))

    def peer(machine, address, *_):
        if not delayed or action == 'timeout' or stage[0] == 2:
            return
        task = box.u32(acquire.CURRENT_TASK)
        if (task == delayed[0][0] or task in peers or box.u32(io.IRQ_DEPTH) or machine.reg_read(regs.UC_ARM_REG_CPSR) & 0x80
                or machine.reg_read(regs.UC_ARM_REG_CPSR) & 31 not in (0x13, 0x1F)):
            return
        if action == 'stale':
            put(c.spec.STATE + c.spec.OFF['GEN'], before['GEN'] + 1)
        index = 0 if action == 'queue' and stage[0] == 0 else 1
        saved[index] = [machine.reg_read(register) for register in registers]
        peers.append(task)
        machine.reg_write(regs.UC_ARM_REG_SP, (saved[index][13] - 0x400) & ~7)
        machine.reg_write(regs.UC_ARM_REG_PC, PEER + index * 0x100)
        stage[0] = 1 if index == 0 else 2
    hooks.append(uc.hook_add(c.unicorn.UC_HOOK_BLOCK, peer))
    accesses = []
    read, write = m.read, m.write
    def touched(address):
        if delayed and box.u32(acquire.CURRENT_TASK) == delayed[0][0] and address in (c.DSP_DATA, c.DSP_DATA + 2):
            accesses.append(address)
    def observed_read(address):
        touched(address)
        return read(address)
    def observed_write(address, value):
        touched(address)
        return write(address, value)
    m.read, m.write = observed_read, observed_write
    try:
        result = box.dev.call(CODE)
    finally:
        m.read, m.write = read, write
        for hook in hooks:
            uc.hook_del(hook)
        uc.ctl_flush_tb()
    elapsed = (m.time_ns - clock['ns']) / 1000000
    elapsed_ticks = (box.u32(acquire.TICK) - clock['tick']) & 0xFFFFFFFF
    after = {name: box.state(name) for name in before}
    held = action == 'timeout'
    expected = 4 if native and action in ('timeout', 'stale') else acquire.BUSY if held else acquire.STALE if action == 'stale' else acquire.OK
    expected_state = dict(before)
    if action == 'stale':
        expected_state['GEN'] += 1
    ok = (result == expected and bool(delayed) and all(ms == 1 for _, ms in delayed)
          and box.u32(io.SEMA) == int(not held) and box.u32(c.spec.NATIVE_SCOPE) == 0
          and after == expected_state and not m.asserts and not saved
          and (not native or not accesses)
          and len(delayed) < acquire.ATTEMPTS
          and (not held or (elapsed_ticks >= acquire.TIMEOUT_MS or len(delayed) == acquire.ATTEMPTS - 1)
               and elapsed_ticks < acquire.TIMEOUT_MS + 100)
          and (action != 'queue' or len(peers) == 2 and box.u32(DATA) == 0))
    if held:
        box.dev.call(io.RELEASE, 1)
    retry = box.dev.call(CODE)
    ok = ok and retry == acquire.OK and box.u32(io.SEMA) == 1
    return dict(id='native_resource_' + action + ('_sample' if native else ''), ok=bool(ok), status=result, yields=len(delayed),
                elapsed_emulator_ms=elapsed, elapsed_ticks=elapsed_ticks, waiting_task=delayed[0][0] if delayed else None,
                peer_tasks=peers, port_accesses=len(accesses), before=before, after=after, retry=retry, asserts=m.asserts)


def runtime_cases(payload):
    return ([contention(payload, action=action) for action in ('release', 'timeout', 'stale', 'queue')]
            + [contention(payload, action=action, native=True) for action in ('stale', 'timeout')])
