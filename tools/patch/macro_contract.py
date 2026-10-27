"""Native macro messages, musical phase and the GMAC interchange contract."""
import struct
import re
import zlib
from enum import IntEnum

MAGIC = b"GMAC"
VERSION = 1
HEADER = struct.Struct("<4sHHIIQII32s")
EVENT = struct.Struct("<Q5s3x")
CRC_OFFSET = 24
PHASE_ONE = 1 << 32
PHASE_MAX = (1 << 64) - 1
PHASE_DIVISOR = 6_000_000_000  # microseconds and hundredths of a BPM
BUILDS = ("hacktribe", "stock", "synth")
CODE, CODE_BYTES = 0xC019A400, 0x2000
BUFFER, BUFFER_BYTES = CODE + CODE_BYTES, 0x2000
STATE_ADDRESS, STATE_BYTES = BUFFER + BUFFER_BYTES, 0xC00
MEMORY_AREAS = ((CODE, CODE_BYTES, "code"), (BUFFER, BUFFER_BYTES, "events"),
                (STATE_ADDRESS, STATE_BYTES, "state"))
CAPACITY = BUFFER_BYTES // EVENT.size


class State(IntEnum):
    IDLE = 0
    ARMED = 1
    RECORDING = 2
    READY = 3
    PLAYING = 4
    SAVING = 5
    FAULT = 6


class Origin(IntEnum):
    PHYSICAL = 0
    MACRO = 1


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"invalid {label}")
    return value


def panel_message(raw):
    raw = bytes(raw)
    if len(raw) != 5:
        raise ValueError("panel message must have five bytes")
    kind, index, a, b, c = raw
    valid = ((kind == 0 and index <= 0x22 and index != 1 and a <= 1 and b == c == 0)
             or (kind == 1 and index <= 4 and a == c == 0)
             or (kind == 2 and index <= 10 and a == c == 0)
             or (kind == 4 and index < 16 and c <= 1)
             or (kind == 5 and index <= 3 and b <= 3))
    if not valid:
        raise ValueError("unsupported macro panel message")
    return raw


def tempo_from_period(period_ps):
    integer(period_ps, 86_805_555, 1_302_083_334, "clock period")
    divisor = period_ps * 2304
    return (6_000_000_000_000_000 + divisor // 2) // divisor


def advance(phase, remainder, elapsed_us, tempo_hundredths):
    integer(phase, 0, PHASE_MAX, "phase")
    integer(remainder, 0, PHASE_DIVISOR - 1, "phase remainder")
    integer(elapsed_us, 0, 0xFFFFFFFF, "elapsed microseconds")
    integer(tempo_hundredths, 2000, 30000, "tempo")
    delta, remainder = divmod(elapsed_us * tempo_hundredths * PHASE_ONE + remainder, PHASE_DIVISOR)
    return integer(phase + delta, 0, PHASE_MAX, "phase"), remainder


def encode(name, events, end_phase, *, capacity, generation=0):
    integer(capacity, 1, CAPACITY, "capacity")
    integer(len(events), 1, capacity, "event count")
    integer(end_phase, 0, PHASE_MAX, "end phase")
    integer(generation, 0, 0xFFFFFFFF, "generation")
    try:
        title = name.encode("ascii")
    except (AttributeError, UnicodeEncodeError) as error:
        raise ValueError("invalid macro name") from error
    if not 1 <= len(title) <= 31 or any(c < 32 or c > 126 for c in title):
        raise ValueError("invalid macro name")
    payload, previous = bytearray(), 0
    for phase, message in events:
        integer(phase, previous, end_phase, "event phase")
        if not payload and phase != 0:
            raise ValueError("first event must start at zero")
        payload.extend(EVENT.pack(phase, panel_message(message)))
        previous = phase
    raw = bytearray(HEADER.pack(MAGIC, VERSION, HEADER.size, len(events), len(payload),
                                end_phase, 0, generation, title.ljust(32, b"\0"))) + payload
    struct.pack_into("<I", raw, CRC_OFFSET, zlib.crc32(raw))
    return bytes(raw)


def decode(raw, *, capacity):
    integer(capacity, 1, CAPACITY, "capacity")
    if len(raw) < HEADER.size or len(raw) > HEADER.size + capacity * EVENT.size:
        raise ValueError("invalid macro file size")
    magic, version, size, count, length, end, crc, generation, title = HEADER.unpack_from(raw)
    if (magic != MAGIC or version != VERSION or size != HEADER.size
            or not 1 <= count <= capacity or length != count * EVENT.size
            or len(raw) != HEADER.size + length):
        raise ValueError("invalid macro header")
    check = bytearray(raw)
    struct.pack_into("<I", check, CRC_OFFSET, 0)
    if zlib.crc32(check) != crc:
        raise ValueError("macro checksum mismatch")
    name, separator, padding = title.partition(b"\0")
    if not separator or any(padding):
        raise ValueError("invalid macro name padding")
    events = []
    for at in range(HEADER.size, len(raw), EVENT.size):
        if any(raw[at + 13:at + 16]):
            raise ValueError("nonzero event padding")
        phase, message = EVENT.unpack_from(raw, at)
        events.append((phase, message))
    try:
        text = name.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("invalid macro name") from error
    encode(text, events, end, capacity=capacity, generation=generation)
    return text, events, end, generation


def assembler_constants():
    values = dict(MACRO_VERSION=VERSION, MACRO_HEADER_BYTES=HEADER.size,
                  MACRO_EVENT_BYTES=EVENT.size, MACRO_CRC_OFFSET=CRC_OFFSET,
                  MACRO_CODE=CODE, MACRO_CODE_BYTES=CODE_BYTES, MACRO_BUFFER=BUFFER,
                  MACRO_BUFFER_BYTES=BUFFER_BYTES, MACRO_STATE=STATE_ADDRESS,
                  MACRO_STATE_BYTES=STATE_BYTES, MACRO_CAPACITY=CAPACITY,
                  MACRO_HEAD_COUNT=8, MACRO_HEAD_PAYLOAD=12, MACRO_HEAD_END_PHASE=16,
                  MACRO_HEAD_GENERATION=28, MACRO_HEAD_NAME=32, MACRO_EVENT_MESSAGE=8)
    values.update({f"MACRO_{s.name}": s.value for s in State})
    values.update({f"MACRO_ORIGIN_{s.name}": s.value for s in Origin})
    return "\n".join(f".equ {name}, {value}" for name, value in values.items()) + "\n"


def recorder_errors(event):
    errors = []
    rows = event.get("cases", [])
    names = ("baseline", "encoder", "knob", "mode", "menu", "part", "pattern", "mute")
    if not isinstance(rows, list) or len(rows) != len(names) or any(not isinstance(r, dict) for r in rows):
        return ["eight recorder comparison cases required"]
    if sorted(str(r.get("case")) for r in rows) != sorted(names):
        return ["recorder comparison case set differs"]
    by_name = {r["case"]: r for r in rows}
    for row in rows:
        if row.get("asserts") != [] or row.get("contains_start_pattern") is not True:
            errors.append(f"{row['case']}: missing snapshot or firmware assertion")
    fields = dict(encoder="osc", knob="level", mode="pad_mode", menu="screen", part="selected_part",
                  pattern="selected_pattern", mute="mute4")
    for name, field in fields.items():
        row = by_name[name]
        before, after = row.get("before", {}), row.get("after", {})
        if (not isinstance(before, dict) or not isinstance(after, dict) or before.get("screen") != 1
                or type(before.get(field)) is not int or type(after.get(field)) is not int
                or before[field] == after[field]):
            errors.append(f"{name}: input had no measured effect")
        if name in ("encoder", "knob", "mute"):
            base_size, size, changes = by_name["baseline"].get("file_bytes"), row.get("file_bytes"), row.get("changed_bytes")
            if (type(base_size) is not int or type(size) is not int or size <= base_size
                    or type(changes) is not int or changes <= 0):
                errors.append(f"{name}: no additional recorder data")
    playback = event.get("playback", {})
    if not isinstance(playback, dict) or playback.get("asserts") != []:
        errors.append("recorder playback assertion evidence missing")
    else:
        values = [playback.get(s, {}).get("osc") for s in ("before", "initial", "final")
                  if isinstance(playback.get(s), dict)]
        if values != [20, 0, 20]:
            errors.append("initial load and final restore not reproduced")
    return errors


def research_errors(report, *, sources=None, ownership=None):
    """Missing evidence never grants permission for the native integration."""
    errors = []
    if not isinstance(report, dict):
        return ["research report must be an object"]
    if report.get("schema") != 1:
        errors.append("unsupported research schema")
    rows = report.get("builds", [])
    if not isinstance(rows, list):
        return errors + ["builds must be a list"]
    names = [r.get("build") for r in rows if isinstance(r, dict)]
    if any(not isinstance(n, str) for n in names) or sorted(n for n in names if isinstance(n, str)) != sorted(BUILDS):
        errors.append("exactly one result for each firmware build required")
    for row in rows:
        if not isinstance(row, dict):
            errors.append("invalid build result")
            continue
        build = row.get("build", "unknown")
        if not isinstance(build, str):
            errors.append("invalid build name")
            continue
        def require(condition, label):
            if not condition:
                errors.append(f"{build}: {label}")
        require(isinstance(row.get("firmware_sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", row["firmware_sha256"]) is not None,
                "firmware identity missing")
        def section(name):
            value = row.get(name)
            return value if isinstance(value, dict) else {}
        h = section("harness")
        def number(value, low, high):
            return type(value) in (int, float) and low <= value <= high
        require(h.get("slice") == 2000 and number(h.get("timer_irq_count"), 990, 1010)
                and number(h.get("timer_window_ms"), 999, 1001), "timer calibration missing")
        inp = section("input")
        require(inp.get("ordered") is True and inp.get("task") == "CsTask"
                and inp.get("origin_separated") is True, "input/origin evidence missing")
        replay = section("replay")
        require(replay.get("task") == "CsTask" and replay.get("irq_enabled") is True
                and replay.get("unsafe_calls", 1) == 0, "safe replay task evidence missing")
        samples = replay.get("extra_latency_ms", [])
        require(isinstance(samples, list) and len(samples) >= 16
                and all(type(x) in (float, int) and 0 <= x <= 2 for x in samples),
                "2 ms replay latency evidence missing or exceeded")
        due = replay.get("due_lateness_ms", [])
        require(isinstance(due, list) and isinstance(samples, list) and len(due) == len(samples)
                and len(due) >= 16 and all(number(x, -.01, 3) for x in due),
                "missing or early replay deadline observations")
        transitions = replay.get("transport_transitions", [])
        require(isinstance(transitions, list)
                and any(isinstance(t, dict) and t.get("key") == 2 and t.get("before") == 0 and t.get("after") == 1 for t in transitions)
                and any(isinstance(t, dict) and t.get("key") == 1 and t.get("before") == 1 and t.get("after") == 0 for t in transitions)
                and number(replay.get("replay_ui_calls"), 1, 1000), "synthetic PLAY/STOP UI evidence missing")
        require(replay.get("registers_preserved") is True
                and type(replay.get("stack_bytes")) is int and 0 < replay["stack_bytes"] <= 1024,
                "register/stack evidence missing")
        stacks = replay.get("observed_stack_bytes", {})
        require(isinstance(stacks, dict) and all(type(stacks.get(k)) is int and 0 < stacks[k] <= 1024
                                               for k in ("cs", "periodic")), "callee stack observation missing")
        tasks = replay.get("wrapper_tasks", {})
        require(isinstance(tasks, dict) and tasks.get("cs") == ["CsTask"]
                and tasks.get("periodic") == ["PeriodicTask"], "wake task context missing")
        require(replay.get("burst_ordered") is True and replay.get("max_messages_per_wake") == 8
                and type(replay.get("burst_max_extra_latency_ms")) in (int, float)
                and 0 <= replay["burst_max_extra_latency_ms"] <= 2, "bounded burst evidence missing or exceeded")
        tempo = section("tempo")
        require(tempo.get("internal") is True and tempo.get("stopped") is True
                and tempo.get("external") is True and tempo.get("asserts") == [],
                "effective tempo/clock evidence missing")
        memory = section("memory")
        require(memory.get("no_overlap") is True and memory.get("erased") is True
                and type(memory.get("capacity")) is int and memory["capacity"] > 0
                and type(memory.get("buffer_bytes")) is int
                and memory["buffer_bytes"] >= memory["capacity"] * EVENT.size
                and number(memory.get("code_bytes"), 1, CODE_BYTES), "declared code/buffer capacity evidence missing")
        expected_areas = [dict(at=f"{a:#010x}", length=n, what=name) for a, n, name in MEMORY_AREAS]
        require(memory.get("areas") == expected_areas and memory.get("capacity") == CAPACITY
                and memory.get("buffer_bytes") == BUFFER_BYTES and memory.get("code_bytes") == CODE_BYTES,
                "memory budget differs from the shared contract")
        if build == "hacktribe":
            event = section("event_recorder")
            playback = event.get("playback", {})
            require(event.get("valid") is True and isinstance(playback, dict) and playback.get("asserts") == [],
                    "Event Recorder comparison missing or asserted")
            errors.extend(f"{build}: {e}" for e in recorder_errors(event))
        if sources is not None:
            provenance = section("section_sources")
            for name in ("input", "tempo", "memory", *(("event",) if build == "hacktribe" else ())):
                origin = provenance.get(name)
                require(isinstance(origin, dict) and all(origin.get(key) == value for key, value in sources.items()),
                        f"stale or missing {name} source evidence")
        if ownership is not None:
            require(memory.get("ownership_sha256") == ownership.get(build), "patch memory ownership changed")
        require(row.get("asserts") == [], "firmware assertion evidence missing")
    return errors
