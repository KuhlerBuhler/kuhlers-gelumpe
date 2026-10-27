# SPDX-License-Identifier: GPL-2.0-only
"""Measure original import inputs and a scoped ARM guard in emulator RAM only.

Original cases stay unchanged. The optional prototype uses a host-controlled token;
it is not an installed project owner or hardware cache-safety proof.
"""

import hashlib
import struct

import sampleset
import unicorn
from machine import UART1
from tools.patch.arm import assemble

NOTE_ON, NOTE_OFF = 0xC005AD44, 0xC005A20C
CONTROL_DISPATCH = 0xC0026418
MIDI_RECEIVER = 0xC009B6F8
PAD, PAD_BUSY_BRANCH, PAD_AFTER_BUSY = 0xC0044874, 0xC0044898, 0xC004489C
RUNNER = 0xC034057C
PATH = "SD:KORG/blechtribe/Projects/Input/e2sSample.all"
NOTE_BODY, NOTE_EXIT, NOTE_VECTOR = 0xC005AD4C, 0xC005AF40, 0xC068E42C
ALL_NOTES_OFF = 0xC005AA80
PART_NOTES_OFF = 0xC005A72C
GUARD_CODE, GUARD_END, GUARD_TOKEN = 0xC0186500, 0xC0186600, 0xC3CFFFF0


def _scenario(payload, device_factory, shared_part, mode=None):
    data = sampleset.build({500 + i: (f"Input-{i}", 40000) for i in range(4)})
    box = device_factory(payload, {PATH: data})
    machine, uc, arm = box.m, box.m.uc, box.m.A
    events, injections, pads, hooks, admissions, part_drains = [], [], [], [], [], []
    phase = "before-import"
    guarded, stop_first = mode is not None, mode in ("tracked", "parts")
    held_status, new_status = (0x90, 0x90) if shared_part else (0x91, 0x92)
    prototype, stop_event = None, None

    def vector_count():
        first, end = struct.unpack("<II", uc.mem_read(NOTE_VECTOR, 8))
        return (end - first) // 4

    def token(value):
        uc.mem_write(GUARD_TOKEN, struct.pack("<I", value))

    original_entry = bytes(uc.mem_read(NOTE_ON, 4))
    if guarded:
        prologue = assemble("push {r4-r11, lr}\nsub sp, sp, #20", origin=NOTE_ON).bytes
        if bytes(uc.mem_read(NOTE_ON, 8)) != prologue:
            raise ValueError("native note entry prologue does not match the researched ABI")
        if bytes(uc.mem_read(GUARD_CODE, GUARD_END - GUARD_CODE)) != b"\xFF" * (GUARD_END - GUARD_CODE):
            raise ValueError("research guard code candidate is not erased")
        assembled = assemble(f"""push {{r4-r11, lr}}
sub sp, sp, #20
ldr ip, ={GUARD_TOKEN:#x}
ldr ip, [ip]
cmp ip, #0
ldrne pc, ={NOTE_EXIT:#x}
ldr pc, ={NOTE_BODY:#x}
.pool
.align 4
part_drain:
push {{r4, lr}}
mov r4, #0
part_drain_loop:
mov r0, r4
bl {PART_NOTES_OFF:#x}
add r4, r4, #1
cmp r4, #16
bne part_drain_loop
pop {{r4, pc}}""", origin=GUARD_CODE)
        code = assembled.bytes
        if GUARD_CODE + len(code) > GUARD_END:
            raise ValueError("research guard exceeds its code candidate")
        token(0)
        uc.mem_write(GUARD_CODE, code)
        uc.mem_write(NOTE_ON, assemble(f"b {GUARD_CODE:#x}", origin=NOTE_ON).bytes)
        prototype = dict(mode=mode, code=hex(GUARD_CODE), token=hex(GUARD_TOKEN), bytes=len(code),
                         code_sha256=hashlib.sha256(code).hexdigest(),
                         native_prologue_sha256=hashlib.sha256(prologue).hexdigest(),
                         flags="Native first conditional AD98 follows CMP AD94; singleton getter also sets flags before testing.",
                         lifecycle="host token, own ARM code in emulator RAM only")

    def busy():
        runner = struct.unpack("<I", uc.mem_read(RUNNER, 4))[0]
        return uc.mem_read(runner + 0x10, 1)[0] if runner else 0

    def record(kind):
        return dict(kind=kind, phase=phase, device_ms=round(machine.time_ns / 1e6, 3),
                    busy=busy(), context=box.context())

    def note(cpu, address, size, user):
        if address == PART_NOTES_OFF:
            event = record("part-note-reset")
            event.update(part=cpu.reg_read(arm.UC_ARM_REG_R0))
            part_drains.append(event)
            return
        if address == NOTE_BODY:
            event = record("note-on-body")
            event.update(part=cpu.reg_read(arm.UC_ARM_REG_R0), source=cpu.reg_read(arm.UC_ARM_REG_R1),
                         note=cpu.reg_read(arm.UC_ARM_REG_R2), token=box.word(GUARD_TOKEN) if guarded else 0)
            admissions.append(event)
            return
        if address in (CONTROL_DISPATCH, MIDI_RECEIVER):
            raw = bytes(cpu.mem_read(cpu.reg_read(arm.UC_ARM_REG_R0), 3))
            event = record("control-dispatch" if address == CONTROL_DISPATCH else "midi-receiver")
            event.update(bytes=raw.hex(), status=raw[0], data1=raw[1], data2=raw[2])
            if len(events) < 256:
                events.append(event)
            return
        event = record("note-on" if address == NOTE_ON else "note-off")
        event.update(part=cpu.reg_read(arm.UC_ARM_REG_R0),
                     source=cpu.reg_read(arm.UC_ARM_REG_R1),
                     note=cpu.reg_read(arm.UC_ARM_REG_R2))
        if len(events) < 256:
            events.append(event)
        if guarded and address == NOTE_ON:
            event.update(token=box.word(GUARD_TOKEN), vector_before=vector_count())
            sp = cpu.reg_read(arm.UC_ARM_REG_SP)
            saved = [cpu.reg_read(arm.UC_ARM_REG_R4 + i) for i in range(8)]

            def returned():
                event.update(caller_sp_restored=cpu.reg_read(arm.UC_ARM_REG_SP) == sp,
                             callee_saved_preserved=[cpu.reg_read(arm.UC_ARM_REG_R4 + i)
                                                     for i in range(8)] == saved,
                             vector_after=vector_count())
            box.at_return(returned)

    def pad(cpu, address, size, user):
        if address == PAD:
            event = record("panel-pad")
            event.update(pad=cpu.reg_read(arm.UC_ARM_REG_R0),
                         pressed=cpu.reg_read(arm.UC_ARM_REG_R1),
                         velocity=cpu.reg_read(arm.UC_ARM_REG_R2),
                         source=cpu.reg_read(arm.UC_ARM_REG_R3),
                         dropped_busy=False, passed_busy=False)
            pads.append(event)
        elif pads:
            if address == PAD_BUSY_BRANCH:
                pads[-1]["dropped_busy"] = bool(cpu.reg_read(arm.UC_ARM_REG_R4))
            else:
                pads[-1]["passed_busy"] = True

    for address, callback in ((NOTE_ON, note), (NOTE_OFF, note), (NOTE_BODY, note),
                              (PART_NOTES_OFF, note), (CONTROL_DISPATCH, note),
                              (MIDI_RECEIVER, note), (PAD, pad),
                              (PAD_BUSY_BRANCH, pad), (PAD_AFTER_BUSY, pad)):
        hooks.append(uc.hook_add(unicorn.UC_HOOK_CODE, callback, begin=address, end=address))
    uc.ctl_flush_tb()

    def inject(label, midi=None, panel=None, button=None):
        event = record(label)
        if midi is not None:
            event.update(bytes=bytes(midi).hex(), accepted=machine.midi(bytes(midi)))
        elif panel is not None:
            event.update(bytes=bytes(panel).hex())
            machine.send(panel)
        else:
            key, down = button
            event.update(button=key, down=down)
            machine.press(key, down)
        injections.append(event)

    reads = 0

    def at_file_read(path, offset, amount):
        nonlocal reads
        if path != PATH:
            return
        reads += 1
        if reads == 1:
            inject("held-midi-note-off", midi=[held_status - 0x10, 60, 0])
            inject("new-midi-note-on", midi=[new_status, 62, 100])
            inject("held-panel-pad-release", panel=[4, 0, 0, 0, 0])
            inject("new-panel-pad-press", panel=[4, 1, 0, 100, 1])
            inject("write-press", button=(0x0E, True))
        elif reads == 3:
            inject("new-midi-note-off", midi=[new_status - 0x10, 62, 0])
            inject("new-panel-pad-release", panel=[4, 1, 0, 0, 0])
            inject("write-release", button=(0x0E, False))

    try:
        machine.press(0x13, True)
        box.dev.run(0.1)
        machine.press(0x13, False)
        box.dev.run(0.1)
        inject("hold-midi-before-import", midi=[held_status, 60, 100])
        inject("hold-panel-before-import", panel=[4, 0, 0, 100, 1])
        box.dev.run(0.2)
        baseline_uart = dict(wire_pending=len(machine.uart[UART1]["wire"]),
                             rx_pending=len(machine.uart[UART1]["rx"]))
        first, end = struct.unpack("<II", uc.mem_read(NOTE_VECTOR, 8))
        baseline_state = dict(vector_count=vector_count(),
                              vector_sha256=hashlib.sha256(bytes(uc.mem_read(first, end - first))).hexdigest(),
                              screen_sha256=hashlib.sha256(box.dev.fb()).hexdigest())
        if guarded and mode != "inactive":
            token(1)
        if stop_first:
            phase = "stop-held"
            stop_before = vector_count()
            stop_event = box.call_in_command(assembled.symbols["part_drain"] if mode == "parts" else ALL_NOTES_OFF)
            stop_after = vector_count()
        phase = "import"
        box.file_mutator = at_file_read
        event = box.import_samples(PATH, timeout=30)
        phase = "after-import"
        box.file_mutator = None
        box.dev.run(0.3)
        inject("cleanup-midi-60", midi=[held_status - 0x10, 60, 0])
        inject("cleanup-midi-62", midi=[new_status - 0x10, 62, 0])
        inject("cleanup-panel-0", panel=[4, 0, 0, 0, 0])
        inject("cleanup-panel-1", panel=[4, 1, 0, 0, 0])
        machine.press(0x0E, False)
        box.dev.run(0.2)
        if guarded:
            token(0)
        phase = "after-unlock"
        inject("normal-midi-after-unlock", midi=[0x93, 65, 100])
        inject("normal-panel-after-unlock", panel=[4, 2, 0, 100, 1])
        box.dev.run(0.2)
        inject("normal-midi-release-after-unlock", midi=[0x83, 65, 0])
        inject("normal-panel-release-after-unlock", panel=[4, 2, 0, 0, 0])
        box.dev.run(0.2)
        final_screen_sha256 = hashlib.sha256(box.dev.fb()).hexdigest()
    finally:
        box.file_mutator = None
        if guarded:
            token(0)
            uc.mem_write(NOTE_ON, original_entry)
        for hook in hooks:
            uc.hook_del(hook)
        uc.ctl_flush_tb()

    checks = []

    def check(name, passed, observed):
        checks.append(dict(name=name, ok=bool(passed), observed=observed))

    during = [e for e in injections if e["phase"] == "import"]
    on_busy = [e for e in events if e["kind"] == "note-on" and e["busy"]]
    off_busy = [e for e in events if e["kind"] == "note-off" and e["busy"]]
    control_busy = [e for e in events if e["kind"] == "control-dispatch" and e["busy"]]
    receiver = [e for e in events if e["kind"] == "midi-receiver"]
    busy_pads = [e for e in pads if e["busy"]]
    held = [e for e in events if e["kind"] == "note-on" and e["phase"] == "before-import"]
    first_feed_ms = min((e["device_ms"] for e in during), default=0)
    native_stop = [e for e in events if e["kind"] == "note-off" and e["phase"] == "import"
                   and e["device_ms"] < first_feed_ms]
    check("input-import-runs-on-command-task", event["status"] == 0 and event["context"]["task"] == 5, event)
    check("real-input-was-fed-while-native-command-busy", bool(during) and all(e["busy"] for e in during), during)
    check("native-pad-handler-observed-during-import", bool(busy_pads), busy_pads)
    check("native-busy-pad-press-is-dropped", any(e["pressed"] and e["dropped_busy"] for e in busy_pads), busy_pads)
    check("native-busy-pad-release-passes-busy-branch", any(not e["pressed"] and e["passed_busy"] for e in busy_pads), busy_pads)
    check("held-engine-note-observed-before-import", bool(held), held)
    check("held-midi-bytes-consumed-before-import", not any(baseline_uart.values())
          and any(e["kind"] == "hold-midi-before-import" and e["accepted"] for e in injections), baseline_uart)
    check("input-import-has-no-native-assert", not machine.asserts, machine.asserts)
    if guarded:
        attempts = [e for e in events if e["kind"] == "note-on" and e.get("token")]
        frames = [e for e in events if e["kind"] == "note-on"]
        check("guard-preserves-call-frames", bool(frames)
              and all(e.get("caller_sp_restored") and e.get("callee_saved_preserved") for e in frames), frames)
        check("guard-blocked-before-native-body", not any(e["token"] for e in admissions), admissions)
        check("guard-preserves-blocked-vector", all(e["vector_before"] == e.get("vector_after") for e in attempts), attempts)
        post = {(e["part"], e["source"]) for e in admissions if e["phase"] == "after-unlock"}
        check("guard-allows-both-normal-inputs-after-unlock", {(3, 0x20), (2, 0x40)} <= post, admissions)
        if stop_first:
            check("native-all-notes-off-clears-held-vector", stop_before > 0 and stop_after == 0
                  and stop_event["context"]["task"] == 5, dict(before=stop_before, after=stop_after, event=stop_event))
        if mode == "guard":
            check("guard-exercised-original-busy-retrigger", any(e["busy"] for e in attempts), attempts)
        if mode == "parts":
            check("native-part-drain-single-command", [e["part"] for e in part_drains] == list(range(16))
                  and all(e["busy"] and e["context"]["task"] == 5 for e in part_drains), part_drains)
            check("native-part-drain-clears-source-priority-retrigger", not attempts, attempts)
    return dict(shared_part=shared_part, fixture=dict(samples=4, frames_per_sample=40000, file_bytes=len(data)),
                checks=checks, events=events, pads=pads, injections=injections,
                guard_prototype=prototype, native_admissions=admissions,
                baseline_state=baseline_state, final_screen_sha256=final_screen_sha256, part_drains=part_drains,
                observations=dict(native_note_ons_while_busy=on_busy, native_note_offs_while_busy=off_busy,
                                  native_control_dispatch_while_busy=control_busy,
                                  native_midi_receiver=receiver,
                                  baseline_midi_uart=baseline_uart,
                                  native_note_off_before_manual_release=native_stop,
                                  native_commands=[dict(command=e["command"], context=e["context"])
                                                   for e in box.events]),
                exclusion_proven=False,
                remaining=["Original busy filtering is not a project-wide ownership lock.",
                           "Full BLECH pad replay, plugin/macro/file owners and WRITE dispatch need separate tests.",
                           "Engine entry observations do not prove DSP voice termination or audible silence.",
                           "WRITE button pressure is not a general proof about arbitrary second queued commands."],
                assumptions=["DIN and panel bytes use the emulator's real UART receive paths.",
                             "A host callback schedules input at original FatFs reads; only explicit prototype cases redirect NOTE_ON.",
                             "Factory samples, SD and DSP are synthetic or emulated; no real device is accessed."])


def probe(payload, device_factory):
    scenarios = [_scenario(payload, device_factory, shared) for shared in (False, True)]
    prototypes = [_scenario(payload, device_factory, True, mode) for mode in ("inactive", "guard", "tracked", "parts")]
    checks = []
    for scenario in scenarios:
        for check in scenario["checks"]:
            checks.append({**check, "name": ("same-part:" if scenario["shared_part"] else "distinct-parts:") + check["name"]})
    for i, scenario in enumerate(prototypes):
        checks.extend({**check, "name": f"prototype-{i}:" + check["name"]} for check in scenario["checks"])
    signature = lambda s: [(e["kind"], e["phase"], e["part"], e["source"], e["note"])
                           for e in s["events"] if e["kind"] in ("note-on", "note-off")]
    checks.append(dict(name="inactive-guard-matches-original-input-vector-and-render",
                       ok=signature(scenarios[1]) == signature(prototypes[0])
                       and scenarios[1]["baseline_state"] == prototypes[0]["baseline_state"]
                       and scenarios[1]["final_screen_sha256"] == prototypes[0]["final_screen_sha256"],
                       observed=dict(original=scenarios[1]["baseline_state"], inactive=prototypes[0]["baseline_state"])))
    return dict(checks=checks, scenarios=scenarios, guard_prototypes=prototypes, exclusion_proven=False,
                observations=dict(native_note_ons_while_busy=[e for s in scenarios
                                                             for e in s["observations"]["native_note_ons_while_busy"]]),
                remaining=scenarios[0]["remaining"], assumptions=scenarios[0]["assumptions"])
