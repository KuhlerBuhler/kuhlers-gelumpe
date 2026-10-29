"""Firmware checks for native script hooks; scripts enter emulator RAM only."""
import argparse
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", "") or Path(__file__).resolve().parents[2])   # the app's frozen service unpacks its data files here
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from tools.patch import script_hooks
import fat32
from firmware import identify
from machine import load_flash
from sdcard import MemoryMedium, SDCard
from splash_cases import Dev

CARD_FILE = "/KORG/blechtribe/Plugin/e2sPlugin.all"


def baseline(vsb):
    output = bytearray(vsb)
    build = identify(vsb[0x100:]).build
    names = ['mfx-switch-synth', 'blech-sysex-synth'] if build == 'synth' else ['splash-editor', 'mfx-switch']
    if build == 'stock':
        names.append('blech-sysex-stock')
    for name in names:
        patch = json.loads((ROOT / "data" / "patches" / (name + ".json")).read_text())
        for change in patch["changes"]:
            at = change["file"]
            if "copy" in change:
                source = change["copy"]
                data = bytearray(vsb[source["file"]:source["file"] + source["length"]])
                if hashlib.sha256(data).hexdigest() != source["expect"]:
                    raise ValueError("unexpected source for " + name)
                for over in change.get("over", []):
                    replacement = bytes.fromhex(over["bytes"])
                    data[over["at"]:over["at"] + len(replacement)] = replacement
            else:
                data = bytes.fromhex(change["bytes"])
            if hashlib.sha256(vsb[at:at + len(data)]).hexdigest() != change["expect"]:
                raise ValueError("unexpected base for " + name)
            output[at:at + len(data)] = data
    return bytes(output)


def card_image(files):
    img = fat32.format_image(64 * 1024 * 1024)
    volume = fat32.Volume(img)
    for path, data in files.items():
        volume.write(path, data)
    volume.close()
    return img


def archive(blocks, crc_wrong=False):
    body = b"".join(blocks)
    crc = zlib.crc32(body) ^ (1 if crc_wrong else 0)
    return struct.pack("<4sHHII", b"GSAL", 1, len(blocks), 16 + len(body), crc) + body


def parse_store(data):
    """A store file (contract STORE) as generation and (name, mask, first value) records, or None when it does not check out."""
    if len(data) < 16:
        return None
    magic, version, count, generation, crc = struct.unpack_from("<IHHII", data, 0)
    size = 16 + count * 84
    if magic != 0x54535347 or version != 1 or len(data) < size or zlib.crc32(data[16:size]) != crc:
        return None
    records = []
    for i in range(count):
        at = 16 + i * 84
        mask, first = struct.unpack_from("<Ii", data, at + 16)
        records.append((data[at:at + 16].split(b"\0")[0].decode(), mask, first))
    return dict(generation=generation, records=records)


def store_file(generation, records):
    """A store file with (name, mask, first value) records, the other values 0."""
    body = b"".join(name.encode().ljust(16, b"\0") + struct.pack("<Ii", mask, first) + bytes(60) for name, mask, first in records)
    return struct.pack("<IHHII", 0x54535347, 1, len(records), generation, zlib.crc32(body)) + body


def store_files(image):
    """The valid store files on a card image, by file name."""
    volume = fat32.Volume(image)
    out = {}
    for name in ["store.a.bin", "store.b.bin"]:
        try:
            parsed = parse_store(volume.read("/KORG/blechtribe/Plugin/" + name))
        except fat32.FatError:
            continue
        if parsed:
            out[name] = parsed
    volume.close()
    return out


def leave_menu(dev):
    """EXIT until the firmware shows its main screen (a group goes up one level first)."""
    import menu_cases
    for _ in range(6):
        if dev.screen()["number"] == 1:
            return
        menu_cases.press(dev, "exit", wait=0.3)


def texts(dev):
    import menu_cases
    return menu_cases.texts_of(dev)


def with_card(payload, flash, files, held=0):
    import menu_cases
    menu_cases.for_build(payload)
    dev = Dev(payload[0x100:], flash, held)
    dev.m.insert_card(SDCard(MemoryMedium(card_image(files))))
    return dev


def write_word(dev, address, value):
    dev.m.uc.mem_write(address, struct.pack("<I", value & 0xffffffff))


def plugin_entry(dev, runtime, index=0):
    """The script entry of the index-th plugin of the card, 0 when there is none. The first entry of a runtime that
    was set up at start is Blechy, the app built into BLECH: his block lies in the image, below the pool."""
    entry = dev.u32(runtime)
    while entry not in (0, 0xffffffff):
        if dev.u32(entry + 4) >= script_hooks.POOL:
            if index == 0:
                return entry
            index -= 1
        entry = dev.u32(entry)
    return 0


def install(dev, built, programs, names, mask=0):
    runtime, pool = built.layout["runtime"], built.layout["pool"]
    dev.call(built.symbols["script_runtime_init"], runtime, pool, 131072)
    for name in names:
        data = bytes.fromhex(programs[name]["blob"])
        dev.m.uc.mem_write(script_hooks.INPUT, data)
        error = dev.call(built.symbols["script_load_block"], runtime, script_hooks.INPUT, len(data))
        if error:
            raise AssertionError("load " + name + ": " + str(error))
    entry = dev.u32(runtime)
    entries = {}
    for name in names:
        entries[name] = entry
        try:
            error = dev.call(built.symbols["script_run_event"], runtime, entry, 0, script_hooks.INPUT)
        except RuntimeError as failure:
            detail = dict(script=name, entry=hex(entry), head=hex(dev.u32(runtime)),
                          tail=hex(dev.u32(runtime + 4)), next=hex(dev.u32(entry)),
                          state=dev.u32(entry + 12), vars=hex(dev.u32(entry + 8)), asserts=dev.m.asserts,
                          poll_stop=dev.m.poll_stop, time_ns=dev.m.time_ns, deadline=dev.m.deadline)
            raise RuntimeError(str(detail)) from failure
        if error:
            raise AssertionError("start " + name + ": " + str(error))
        entry = dev.u32(entry)
    write_word(dev, runtime + built.symbols["SCRIPT_CONTROL_CAPTURE_MASK"], mask)
    write_word(dev, runtime + built.symbols["SCRIPT_CONTROL_ARMED"], 1)
    return entries


def variables(dev, entry, program):
    base = dev.u32(entry + 8)
    return {name: struct.unpack("<i", dev.read(base + item["slot"] * 4, 4))[0]
            for name, item in program["symbols"].items() if item["kind"] == "var"}


def footprint(dev):
    pattern = dev.u32(0xC033E6A4)
    return {
        "screen": dev.screen(),
        "pattern": hashlib.sha256(dev.read(pattern, 0x4000)).hexdigest(),
        "display": hashlib.sha256(dev.fb()).hexdigest(),
        "leds": sorted((key, value) for key, value in dev.m.leds.items() if key != 0x14),
        "asserts": dev.m.asserts,
    }


def firmware_cases(vsb, flash, request):
    import menu_cases
    menu_cases.for_build(vsb)
    stock = baseline(vsb)
    built = script_hooks.build(request["include"], build=identify(vsb[0x100:]).build)
    patched = built.apply(stock)
    programs = request["programs"]
    checks = []

    def check(name, ok, detail=None):
        checks.append(dict(id=name, ok=bool(ok), detail=detail))

    def boot(payload, held=0):
        dev = Dev(payload[0x100:], flash, held)
        dev.run(2)
        return dev

    reference, idle = boot(stock), boot(patched)
    check("boot-unscharf", footprint(reference) == footprint(idle))
    check("boot-nur-blechy", idle.u32(built.layout["runtime"] + 96) == 1 and plugin_entry(idle, built.layout["runtime"]) == 0 and idle.u32(idle.u32(built.layout["runtime"]) + 4) < script_hooks.POOL,
          "no card: the runtime holds Blechy alone, armed, with his block outside the pool")
    for msg in [[0, 9, 1, 0, 0], [0, 9, 0, 0, 0], [0, 13, 1, 0, 0], [0, 13, 0, 0, 0]]:
        for dev in [reference, idle]:
            dev.m.send(msg)
            dev.run(0.12)
    check("unscharf-bedienung", footprint(reference) == footprint(idle))

    killed_reference, killed = boot(stock, 0x2000), boot(patched, 0x2000)
    before = footprint(killed)
    entries = install(killed, built, programs, ["input"], mask=0x37)
    killed.run(0.12)
    killed_reference.m.run_until(killed.m.time_ns / 1e9)
    check("exit-haken", variables(killed, entries["input"], programs["input"])["frameCount"] == 0)
    check("exit-original", footprint(killed) == before == footprint(killed_reference))

    active = boot(patched)
    entries = install(active, built, programs, ["input"], mask=0x37)
    active.run(0.12)
    messages = [[0, 24, 1, 0, 0], [0, 24, 0, 0, 0], [1, 0, 0, 255, 0],
                [2, 7, 1, 244, 0], [4, 5, 0, 100, 1], [4, 5, 0, 0, 0], [5, 1, 144, 1, 144]]
    for message in messages:
        active.m.send(message)
        active.run(0.08)
    values = variables(active, entries["input"], programs["input"])
    expected = dict(readyCount=1, pressCount=1, releaseCount=1, lastKey=24,
                    encoderIndex=0, encoderDelta=-1, knobIndex=7, knobValue=500,
                    padIndex=5, padVelocity=100, padReleaseCount=1, touchX=400, touchY=400)
    check("panel-argumente", all(values[key] == value for key, value in expected.items()), values)
    count = values["frameCount"]
    active.run(1)
    frames = variables(active, entries["input"], programs["input"])["frameCount"] - count
    check("rahmen-25hz", frames == 25, frames)
    check("ui-ohne-assert", not active.m.asserts)
    # The panel's touchpad message is 05 xh xl yh yl: both values are 16 bits, high byte first, and reach the plugin unchanged.
    # The press (key 0x22) has no position of its own and no touch event; the first position after it is the touch's first.
    touch_vars = lambda: variables(active, entries["input"], programs["input"])
    seen = []
    for message in [[0, 34, 1, 0, 0], [5, 0x01, 0x23, 0x03, 0xFF], [5, 0x02, 0x00, 0x00, 0x05], [0, 34, 0, 0, 0],
                    [5, 0xFF, 0xFF, 0xFF, 0xFE], [5, 0x00, 0x00, 0x00, 0x00], [0, 34, 1, 0, 0], [5, 0x03, 0xFF, 0x03, 0xFF]]:
        active.m.send(message)
        active.run(0.08)
        values = touch_vars()
        seen.append((values["touchX"], values["touchY"], values["touchFirst"], values["touches"]))
    first_run = seen[0][3]
    check("touch-lage-aus-der-panel-nachricht", seen[1][:3] == (291, 1023, 1) and seen[2][:3] == (512, 5, 0) and seen[4][:3] == (65535, 65534, 1)
          and seen[5][:3] == (0, 0, 0) and seen[7][:3] == (1023, 1023, 1) and seen[0][3] == first_run and seen[1][3] == first_run + 1, seen)

    faulty = boot(patched)
    entries = install(faulty, built, programs, ["fault", "healthy"])
    faulty.m.send([0, 24, 1, 0, 0])
    faulty.run(0.15)
    runtime = built.layout["runtime"]
    check("fault-isoliert", faulty.u32(entries["fault"] + 12) == 3 and faulty.u32(entries["healthy"] + 12) == 2)
    check("fault-folgeskript", variables(faulty, entries["healthy"], programs["healthy"])["count"] == 1)
    check("fault-status", faulty.u32(entries["fault"] + 16) == request["errors"]["DIV_ZERO"]
          and faulty.u32(entries["fault"] + 24) > 0)
    faulty.m.send([0, 24, 0, 0, 0])
    faulty.run(0.04)
    faulty.press("menu", 0.15)
    check("fault-firmware-bedienbar", faulty.screen()["number"] != 1 and not faulty.m.asserts)
    faulty.press("exit", 0.15)
    check("fault-exit", faulty.screen()["number"] == 1 and not faulty.m.asserts)

    timed = boot(patched)
    timed_entries = install(timed, built, programs, ["loop", "healthy"])
    write_word(timed, built.layout["runtime"] + built.symbols["RT_FUEL"], 1000000)
    timed.m.send([0, 24, 1, 0, 0])
    timed.run(0.15)
    check("fault-rahmenbudget", timed.u32(timed_entries["loop"] + 16) == request["errors"]["TIME"])
    check("fault-budget-fortsetzung", timed.u32(timed_entries["healthy"] + 12) == 2
          and variables(timed, timed_entries["healthy"], programs["healthy"])["count"] == 1
          and not timed.m.asserts)

    led = boot(patched)
    led_entries = install(led, built, programs, ["led"], mask=0x37)
    before = len(led.m.panel_log)
    led.run(0.12)
    initial = [message for message in led.m.panel_log[before:]
               if message == bytes([0, 0, 0, 0, 0])]
    check("led-ready-nullwert", len(initial) == 1, len(initial))
    for level in [255, 0]:
        before = len(led.m.panel_log)
        led.m.send([0, 24, 1, 0, 0])
        led.run(0.12)
        delivered = [message for message in led.m.panel_log[before:]
                     if message == bytes([0, 0, level, 0, 0])]
        check("led-tap-" + str(level), len(delivered) == 1 and led.m.leds.get(0) == level,
              dict(messages=len(delivered), value=led.m.leds.get(0)))
        led.m.send([0, 24, 0, 0, 0])
        led.run(0.04)
    before = len(led.m.panel_log)
    frames = variables(led, led_entries["led"], programs["led"])["frames"]
    led.m.send([0, 9, 1, 0, 0])
    led.run(0.4)
    burst = [message for message in led.m.panel_log[before:]
             if message[0] == 0 and message[2:] == bytes([17, 0, 0])]
    check("led-88-pakete", len(burst) == 88 and {message[1] for message in burst} == set(range(88)),
          dict(messages=len(burst), indices=len({message[1] for message in burst})))
    check("led-rahmen-fortgesetzt", variables(led, led_entries["led"], programs["led"])["frames"] > frames
          and not led.m.asserts)

    card_cases(request, programs, built, patched, stock, flash, check)
    seq_cases(request, programs, built, patched, flash, check)
    menu_script_cases(programs, built, patched, flash, check)

    write_word(faulty, runtime + built.symbols["SCRIPT_CONTROL_ARMED"], 0)
    record = struct.pack("<4i", 3, 24, 0, 0)
    faulty.m.uc.mem_write(script_hooks.INPUT, record)
    for _ in range(65):
        faulty.call(built.symbols["script_ring_post"], runtime, script_hooks.INPUT)
    check("ring-ueberlauf-status", faulty.u32(runtime + 20) == 1)

    replies = []
    faulty.m.midi(request["search"])
    faulty.run(0.2)
    found = faulty.m.midi_out()
    search = next((message for message in found if message[:4] == bytes([0xf0, 0x42, 0x50, 1])), None)
    check("status-geraetesuche", search is not None)
    channel = search[4] & 15 if search is not None else 0
    for item in request["reads"]:
        message = list(item["message"])
        message[2] = 0x30 + channel
        faulty.m.midi(message)
        faulty.run(0.25)
        received = faulty.m.midi_out()
        replies.append(dict(name=item["name"], messages=[data.hex() for data in received]))
        check("status-din-" + item["name"], len(received) == 1)
    return dict(ok=all(check["ok"] for check in checks), checks=checks,
                search=search.hex() if search is not None else None, reads=replies, layout=built.layout)


def seq_cases(request, programs, built, patched, flash, check):
    """korg.seq: the steps a plugin writes land in the pattern in RAM byte for byte as in the browser model, the pads show them,
    the sequencer plays them, also a step written while it runs, and the pattern then counts as unsaved."""
    seq = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["seqwrite"]["blob"])])})
    seq.run(2)
    pattern = seq.u32(0xC033E6A4) + 4                       # the pattern object's pointer; the block starts 4 bytes in
    records = lambda: [seq.m.uc.mem_read(pattern + 0x800 + 0x30 + 12 * step, 12) for step in range(64)]

    def same(model):
        """Every on byte as the model has it, and every byte the model wrote for a step that is on."""
        bad = []
        for step, (record, (on, gate, velocity, trigger, note)) in enumerate(zip(records(), model)):
            want = [on] if not on else [on, gate, velocity, trigger, note + 1, 0, 0, 0]
            if list(record[:len(want)]) != want:
                bad.append((step, list(record[:8]), want))
        return bad

    check("seq-schreibt-wie-der-browser", seq.a(0xC06B2798) + 4 == pattern and not same(request["seq"]["ready"]), same(request["seq"]["ready"])[:4])
    lit = lambda: sorted(n for n in range(16) if seq.m.leds.get(0x2C + 2 * n, 0) > 0)
    seq.press(0x15, 0.4)                                     # SEQUENCER: the pads show the steps of bar 1
    before = lit()
    seq.press(0x03, 0.3)                                     # TAP: the plugin turns step 1 off and step 6 on
    after = lit()
    on = lambda model: [step for step in range(16) if model[step][0]]
    check("seq-tap-wie-der-browser", not same(request["seq"]["tap"]), same(request["seq"]["tap"])[:4])
    check("seq-pads-zeigen-die-steps", before == on(request["seq"]["ready"]) and after == on(request["seq"]["tap"]) and not seq.m.asserts,
          dict(before=before, after=after))
    dirty = seq.read(script_hooks.MENU_STATE - 1, 1)[0]
    plain = with_card(patched, flash, {})
    plain.run(2)
    check("seq-ungespeichert", dirty == 1 and plain.read(script_hooks.MENU_STATE - 1, 1)[0] == 0,
          dict(written=dirty, untouched=plain.read(script_hooks.MENU_STATE - 1, 1)[0]))
    seq.m.uc.mem_write(pattern + 37, bytes([0]))            # one bar: the pass comes round every 16 steps
    seq.press(0x15, 0.3)                                     # back out of SEQUENCER mode
    mark = len(seq.m.uart[0x01D0C000]["tx"])
    seq.m.press(2, True)
    seq.run(0.05)
    seq.m.press(2, False)
    seq.run(5.0)
    seq.m.press(1, True)
    seq.run(0.05)
    seq.m.press(1, False)
    seq.run(0.3)
    data, played, status, cur = bytes(seq.m.uart[0x01D0C000]["tx"][mark:]), [], None, []
    for x in data:
        if x >= 0xF8:
            continue
        if x & 0x80:
            status, cur = x, []
            continue
        cur.append(x)
        if status is not None and len(cur) == 2:
            if status & 0xF0 == 0x90 and status & 0x0F == 0 and cur[1] > 0:
                played.append(cur[0])
            cur = []
    first = [62, 64, 65, 66, 68, 70, 72, 74]
    check("seq-spielt-was-geschrieben-ist", played[:8] == first and not seq.m.asserts, played[:20])
    check("seq-schreibt-waehrend-es-laeuft", played[8:17] == [50] + first and not seq.m.asserts, played[:20])


def with_flags(block, flags):
    """A block with its header flags set to `flags` and the checksum made again."""
    out = bytearray(block)
    struct.pack_into("<H", out, 34, flags)
    struct.pack_into("<I", out, 12, zlib.crc32(bytes(out[16:struct.unpack_from("<I", out, 8)[0]])))
    return bytes(out)


def menu_script_cases(programs, built, patched, flash, check):
    """The BLECH menu's script pages: list, on and off, faults, and no input for scripts while the menu is open."""
    import menu_cases
    runtime = built.layout["runtime"]
    blocks = [bytes.fromhex(programs[name]["blob"]) for name in ["healthy", "fault"]]
    dev = with_card(patched, flash, {CARD_FILE: archive(blocks)})
    dev.run(2)
    state = lambda offset: dev.u32(menu_cases.STATE + offset)
    healthy = plugin_entry(dev, runtime)
    fault = dev.u32(healthy)
    check("menu-skripte-gezaehlt", state(40) == 2 and state(12) == 1, dict(scripts=state(40), ring=state(12)))
    count = lambda: variables(dev, healthy, programs["healthy"])["count"]
    dev.m.send([0, 24, 1, 0, 0])
    dev.run(0.15)
    dev.m.send([0, 24, 0, 0, 0])
    dev.run(0.1)
    # MANAGE PLUGINS: one page a plugin, its name and its state under it; EDIT goes through them and wraps
    menu_cases.goto_plugin(dev, 0)
    rows = [(texts(dev), menu_cases.counter(dev))]
    menu_cases.press(dev, "edit_next")
    rows.append((texts(dev), menu_cases.counter(dev)))
    menu_cases.press(dev, "edit_next")
    wrapped = texts(dev)
    check("menu-skriptseiten", rows[0] == (("healthy", "ON", ""), (0, 2)) and rows[1][0][0] == "fault" and rows[1][0][1].startswith("DIV_ZERO L")
          and rows[1][0][2] == "" and rows[1][1] == (1, 2) and wrapped == rows[0][0] and menu_cases.tab(dev) == "Plugins",
          dict(rows=rows, wrapped=wrapped))
    menu_cases.goto_top(dev, menu_cases.LIST_FEATURES)
    titles = []
    for _ in range(menu_cases.LIST_COUNT):
        titles.append(menu_cases.text(dev, menu_cases.S_TITLE))
        menu_cases.press(dev, "edit_next")
    check("menu-liste-ohne-about", titles == menu_cases.LIST_PAGES + [menu_cases.version_texts(patched)[0]] and "ABOUT" not in titles and menu_cases.text(dev, menu_cases.S_TITLE) == "FEATURES", titles)
    check("menu-blechy-keine-plugin-seite", dev.u32(menu_cases.STATE + 40) == 2 and plugin_entry(dev, runtime, 2) == 0, dict(count=dev.u32(menu_cases.STATE + 40)))
    menu_cases.goto_plugin(dev, 0)

    def tap():
        before = count()
        dev.m.send([0, 24, 1, 0, 0])
        dev.run(0.15)
        dev.m.send([0, 24, 0, 0, 0])
        dev.run(0.1)
        return count() - before

    # input while the menu is open does not reach the scripts, outside it does
    inside = tap()
    check("menu-eingaben-erreichen-skripte-nicht", inside == 0 and dev.screen()["number"] == built.profile.screen, dict(delta=inside))
    leave_menu(dev)
    outside = tap()
    check("menu-skripte-laufen-wieder", outside == 1, dict(delta=outside))
    menu_cases.goto_plugin(dev, 0)
    dev.turn(-1, wait=0.2)
    off = texts(dev)
    leave_menu(dev)
    paused = tap()
    check("menu-skript-aus", off == ("healthy", "OFF", "") and dev.u32(healthy + 12) == 1 and paused == 0, dict(off=off, state=dev.u32(healthy + 12), delta=paused))
    menu_cases.goto_plugin(dev, 0)
    dev.turn(1, wait=0.2)
    on = texts(dev)
    leave_menu(dev)
    resumed = tap()
    check("menu-skript-wieder-an", on == ("healthy", "ON", "") and dev.u32(healthy + 12) == 2 and resumed == 1 and not dev.m.asserts, dict(on=on, delta=resumed))
    # a faulted script cannot be switched on
    menu_cases.goto_plugin(dev, 1)
    dev.turn(1, wait=0.2)
    check("menu-fehlerskript-bleibt-aus", dev.u32(fault + 12) == 3 and texts(dev)[1].startswith("DIV_ZERO L") and not dev.m.asserts, texts(dev))

    # export all: the loaded blocks go back to e2sPlugin.all exactly as the browser packs them
    medium = dev.m.mmc.card.medium
    volume = fat32.Volume(medium.data)
    volume.write(CARD_FILE, b"junk", overwrite=True)
    volume.close()
    menu_cases.goto_du(dev, menu_cases.du_pages().index("EXPORT ALL PLUGINS"))
    page = texts(dev)
    menu_cases.press(dev, "write", wait=0.8)
    done = texts(dev)
    volume = fat32.Volume(medium.data)
    written = volume.read(CARD_FILE)
    volume.close()
    check("menu-export-seite", page == ("EXPORT ALL PLUGINS", "", menu_cases.PRESS) and done == ("EXPORT ALL PLUGINS", "2 exported", "")
          and menu_cases.tab(dev) == "Data Util", dict(page=page, done=done))
    check("menu-export-gleich-dem-browser-bauer", written == archive(blocks), dict(size=len(written), want=len(archive(blocks))))
 
    again = with_card(patched, flash, {CARD_FILE: written})
    again.run(2)
    check("menu-export-wird-wieder-geladen", [again.u32(runtime + built.symbols["SCRIPT_CONTROL_" + name]) for name in ["CARD_STATUS", "CARD_LOADED"]] == [1, 2] and not again.m.asserts)

    # a plugin switched off stays off over a restart (device 18.10.: off, EXPORT ALL, restart, on again): EXPORT ALL and WRITE on
    # its page keep the inverted checksum of its block in the settings; switched on it runs its start body then
    def restart(old):
        new = Dev(patched[0x100:], flash, 0)
        new.m.insert_card(SDCard(MemoryMedium(bytearray(old.m.mmc.card.medium.data))))
        new.run(2)
        return new

    def taps(box, entry):
        before = variables(box, entry, programs["healthy"])["count"]
        box.m.send([0, 24, 1, 0, 0])
        box.run(0.15)
        box.m.send([0, 24, 0, 0, 0])
        box.run(0.1)
        return variables(box, entry, programs["healthy"])["count"] - before

    menu_cases.goto_plugin(dev, 0)
    dev.turn(-1, wait=0.2)
    menu_cases.goto_du(dev, menu_cases.du_pages().index("EXPORT ALL PLUGINS"))
    menu_cases.press(dev, "write", wait=0.8)
    exported = texts(dev)
    leave_menu(dev)
    kept = restart(dev)
    entry = plugin_entry(kept, runtime)
    off_state, off_taps, off_cost = kept.u32(entry + 12), taps(kept, entry), kept.u32(entry + built.symbols["SCRIPT_ENTRY_MAX_COST"])
    menu_cases.goto_plugin(kept, 0)
    off_page = texts(kept)
    kept.turn(1, wait=0.2)
    leave_menu(kept)
    on_state, on_taps = kept.u32(entry + 12), taps(kept, entry)
    check("menu-plugin-bleibt-aus-nach-neustart", exported[1] == "2 exported" and off_state == 1 and off_taps == 0 and off_cost == 0 and off_page[:2] == ("healthy", "OFF")
          and on_state == 2 and on_taps == 1 and not kept.m.asserts,
          dict(exported=exported, off=(off_state, off_taps, off_cost, off_page), on=(on_state, on_taps), asserts=kept.m.asserts))
    menu_cases.goto_plugin(kept, 0)
    menu_cases.press(kept, "write", wait=0.8)
    saved = texts(kept)
    leave_menu(kept)
    back = restart(kept)
    entry = plugin_entry(back, runtime)
    check("menu-plugin-an-mit-write-gespeichert", back.u32(entry + 12) == 2 and taps(back, entry) == 1 and not back.m.asserts,
          dict(saved=saved, state=back.u32(entry + 12)))
    # the list keeps every other checksum when a save takes a marker out (device 28.10.: Lauflicht off, WRITE, EXPORT ALL,
    # restart, on again: the shift dropped entries behind the removed marker, also the one just added for Lauflicht)
    checksum = lambda block: struct.unpack_from("<I", block, 12)[0]
    trust = built.symbols["MENU_TRUST"]
    others = [0x11111111, 0x22222222]
    back.m.uc.mem_write(trust, b"".join(struct.pack("<I", value) for value in [~checksum(blocks[1]) & 0xffffffff] + others))
    back.m.uc.mem_write(menu_cases.STATE + 44, struct.pack("<I", 3))
    menu_cases.goto_plugin(back, 0)
    back.turn(-1, wait=0.2)
    menu_cases.press(back, "write", wait=0.8)
    listed = sorted(back.u32(trust + 4 * i) for i in range(back.u32(menu_cases.STATE + 44)))
    leave_menu(back)
    kept_off = restart(back)
    entry = plugin_entry(kept_off, runtime)
    check("menu-plugin-aus-liste-behaelt-die-anderen", listed == sorted(others + [~checksum(blocks[0]) & 0xffffffff])
          and kept_off.u32(entry + 12) == 1 and not kept_off.m.asserts,
          dict(listed=[hex(value) for value in listed], state=kept_off.u32(entry + 12)))

    # MANAGE PLUGINS: ENTER opens the list of the plugins, ENTER on one its pages (DESCRIPTION, its own, REMOVE), which wrap; REMOVE
    # asks once, then writes e2sPlugin.all without it and goes back to MANAGE PLUGINS; EXIT goes up one level each time
    gone = with_card(patched, flash, {CARD_FILE: archive(blocks)})
    gone.run(2)
    menu_cases.goto_group(gone, menu_cases.GROUP_PLUGINS, menu_cases.PLUGIN_MANAGE)
    edit = texts(gone)
    menu_cases.press(gone, "menu", wait=0.4)
    opened = (menu_cases.state(gone, menu_cases.S_LEVEL), menu_cases.counter(gone), texts(gone), menu_cases.tab(gone))
    menu_cases.press(gone, "menu", wait=0.4)
    inside = (menu_cases.state(gone, menu_cases.S_LEVEL), menu_cases.counter(gone), menu_cases.tab(gone))
    menu_cases.press(gone, "exit", wait=0.4)
    up = (menu_cases.state(gone, menu_cases.S_LEVEL), menu_cases.state(gone, menu_cases.S_PAGE), texts(gone))
    menu_cases.press(gone, "exit", wait=0.4)
    left = (menu_cases.state(gone, menu_cases.S_LEVEL), menu_cases.state(gone, menu_cases.S_PAGE), texts(gone))
    check("plugin-verwalten-oeffnet-und-exit", edit == ("MANAGE PLUGINS", "", menu_cases.PRESS) and opened == (menu_cases.LEVEL_PLUGIN, (0, 2), ("healthy", "ON", ""), "Plugins")
          and inside == (menu_cases.LEVEL_PSUB, (0, 2), "Plugins") and up == (menu_cases.LEVEL_PLUGIN, 0, ("healthy", "ON", ""))
          and left == (2, menu_cases.PLUGIN_MANAGE, edit) and not gone.m.asserts, dict(edit=edit, opened=opened, inside=inside, up=up, left=left))
    menu_cases.press(gone, "menu", wait=0.4)
    menu_cases.press(gone, "menu", wait=0.4)
    menu_cases.press(gone, "edit_prev", wait=0.4)
    last = (menu_cases.counter(gone), texts(gone))
    menu_cases.press(gone, "menu", wait=0.4)
    asks = texts(gone)
    menu_cases.press(gone, "menu", wait=0.8)
    done = (menu_cases.state(gone, menu_cases.S_LEVEL), menu_cases.state(gone, menu_cases.S_PAGE), texts(gone), gone.u32(menu_cases.STATE + 40))
    volume = fat32.Volume(gone.m.mmc.card.medium.data)
    left_on_card = volume.read(CARD_FILE)
    volume.close()
    menu_cases.press(gone, "menu", wait=0.4)
    remaining = texts(gone)
    check("plugin-entfernen", last == ((1, 2), ("REMOVE", "", menu_cases.PRESS)) and asks == ("REMOVE", "Enter = remove", "")
          and done == (2, menu_cases.PLUGIN_MANAGE, ("MANAGE PLUGINS", "removed", ""), 1) and left_on_card == archive(blocks[1:])
          and remaining[0] == "fault" and not gone.m.asserts,
          dict(last=last, asks=asks, done=done, card=len(left_on_card), remaining=remaining))
    after = restart(gone)
    check("plugin-geloescht-nach-neustart", [after.u32(runtime + built.symbols["SCRIPT_CONTROL_" + name]) for name in ["CARD_STATUS", "CARD_LOADED"]] == [1, 1]
          and after.u32(menu_cases.STATE + 40) == 1 and not after.m.asserts, dict(loaded=after.u32(menu_cases.STATE + 40)))
    menu_cases.goto_plugin(gone, 0, 1)
    menu_cases.press(gone, "menu", wait=0.4)
    menu_cases.press(gone, "menu", wait=0.8)
    volume = fat32.Volume(gone.m.mmc.card.medium.data)
    empty_file = volume.read(CARD_FILE)
    volume.close()
    nobody = restart(gone)
    check("letztes-plugin-entfernen", texts(gone) == ("MANAGE PLUGINS", "removed", "") and empty_file == archive([]) and nobody.u32(menu_cases.STATE + 40) == 0
          and not nobody.m.asserts, dict(texts=texts(gone), size=len(empty_file)))

    full_list_case(programs, built, patched, flash, check, restart)
    settings_v3_cases(programs, built, patched, flash, check, restart)
    foreign_cases(programs, built, patched, flash, check)
    import_cases(programs, built, patched, flash, check)
    menu_add_cases(programs, built, patched, flash, check)


def renamed(block, name):
    """A block with another name in its header and the checksum made again."""
    out = bytearray(block)
    out[36:52] = name.encode().ljust(16, b"\0")
    struct.pack_into("<I", out, 12, zlib.crc32(bytes(out[16:struct.unpack_from("<I", out, 8)[0]])))
    return bytes(out)


def full_list_case(programs, built, patched, flash, check, restart):
    """The settings' checksum list as the red device had it on 28.10. with 13 plugins: two markers of older plugin builds, eleven
    allowed checksums, the marker of one plugin that is off three times; 16 entries, full up to 1.3.7. Since 1.3.8 the list
    holds 64: 48 more checksums of older builds fill it. Switching one more plugin off and WRITE still has to keep it off over
    a restart."""
    import menu_cases
    runtime = built.layout["runtime"]
    blocks = [renamed(bytes.fromhex(programs["healthy"]["blob"]), "plugin%02d" % i) for i in range(13)]
    checksum = lambda block: struct.unpack_from("<I", block, 12)[0]
    marker = lambda block: ~checksum(block) & 0xffffffff
    dev = with_card(patched, flash, {CARD_FILE: archive(blocks)})
    dev.run(2)
    menu_cases.goto_plugin(dev, 12)
    dev.turn(-1, wait=0.2)
    trust = built.symbols["MENU_TRUST"]
    listed = [0x30000000 + i for i in range(48)] + [0x11111111, 0x22222222] + [checksum(block) for block in blocks[1:12]] + [marker(blocks[12])] * 3
    dev.m.uc.mem_write(trust, b"".join(struct.pack("<I", value) for value in listed))
    dev.m.uc.mem_write(menu_cases.STATE + 44, struct.pack("<I", len(listed)))
    menu_cases.goto_plugin(dev, 0)
    dev.turn(-1, wait=0.2)
    menu_cases.press(dev, "write", wait=0.8)
    saved = texts(dev)
    after = [dev.u32(trust + 4 * i) for i in range(dev.u32(menu_cases.STATE + 44))]
    leave_menu(dev)
    again = restart(dev)
    states = [again.u32(plugin_entry(again, runtime, i) + 12) for i in (0, 12)]
    check("menu-plugin-aus-bei-voller-liste", saved[1] == "saved" and states == [1, 1] and marker(blocks[0]) in after
          and after.count(marker(blocks[12])) == 1 and all(checksum(block) in after for block in blocks[1:12]) and not again.m.asserts,
          dict(saved=saved, states=states, listed=[hex(value) for value in after]))


def settings_v3_cases(programs, built, patched, flash, check, restart):
    """Settings file version 3 (1.3.8): version 2 with up to 64 checksums. A version 2 file with 16 entries is read and written
    again as version 3, 40 plugins switched off stay off over WRITE and a restart, and a version 1 file is still read."""
    import menu_cases
    runtime = built.layout["runtime"]
    trust = built.symbols["MENU_TRUST"]
    listed = lambda dev: [dev.u32(trust + 4 * i) for i in range(dev.u32(menu_cases.STATE + 44))]
    healthy = bytes.fromhex(programs["healthy"]["blob"])

    def on_card(dev):
        """{path: (version, count, generation)} of the settings files on the card."""
        out = {}
        for path in menu_cases.SETTINGS_PATHS:
            try:
                raw = volume_read(dev.m.mmc.card.medium.data, path)
            except fat32.FatError:
                continue
            out[path] = (raw[4], *struct.unpack_from("<HI", raw, 6))
        return out

    old = [0x50000000 + i for i in range(16)]
    dev = with_card(patched, flash, {CARD_FILE: archive([healthy]), menu_cases.SETTINGS_PATHS[0]: menu_cases.settings_file_v2(5, 3, menu_cases.look_word(), trusted=old)})
    dev.run(2)
    read = listed(dev)
    menu_cases.goto_plugin(dev, 0)
    menu_cases.press(dev, "write", wait=0.8)
    saved = texts(dev)
    files = on_card(dev)
    written = menu_cases.read_settings_full(dev.m.mmc.card.medium.data).get("a")
    leave_menu(dev)
    again = restart(dev)
    check("menu-einstellungen-v2-wird-v3", read == old and saved[1] == "saved" and files.get(menu_cases.SETTINGS_PATHS[0]) == (3, 16, 6)
          and written == (6, 3, old) and listed(again) == old and again.u32(plugin_entry(again, runtime) + 12) == 2 and not again.m.asserts,
          dict(read=len(read), saved=saved, files=files, again=len(listed(again))))
    # 40 plugins, all off: 40 markers, more than the 16 a file held up to 1.3.7
    blocks = [renamed(healthy, "plugin%02d" % i) for i in range(40)]
    many = with_card(patched, flash, {CARD_FILE: archive(blocks)})
    many.run(3)
    entries = [plugin_entry(many, runtime, i) for i in range(40)]
    for entry in entries:
        write_word(many, entry + 12, 1)
    menu_cases.goto_plugin(many, 0)
    menu_cases.press(many, "write", wait=1.0)
    saved = texts(many)
    files = on_card(many)
    leave_menu(many)
    back = restart(many)
    states = [back.u32(plugin_entry(back, runtime, i) + 12) for i in range(40)]
    markers = sorted(~struct.unpack_from("<I", block, 12)[0] & 0xffffffff for block in blocks)
    check("menu-40-plugins-aus-nach-neustart", all(entries) and saved[1] == "saved" and files.get(menu_cases.SETTINGS_PATHS[1], (0, 0))[:2] == (3, 40)
          and states == [1] * 40 and sorted(listed(back)) == markers and not back.m.asserts,
          dict(entries=sum(1 for entry in entries if entry), saved=saved, files=files, states=states, listed=len(listed(back))))
    # a version 1 file (BLECH before 1.2) is still read: its checksums, its generation and its flags
    first = [0x60000000 + i for i in range(5)]
    v1 = with_card(patched, flash, {CARD_FILE: archive([healthy]), menu_cases.SETTINGS_PATHS[1]: menu_cases.settings_file(4, 3, trusted=first)})
    v1.run(2)
    check("menu-einstellungen-v1-gelesen", listed(v1) == first and v1.u32(menu_cases.STATE + 32) == 4 and v1.u32(menu_cases.STATE + 16) == 1
          and v1.u32(plugin_entry(v1, runtime) + 12) == 2 and not v1.m.asserts,
          dict(listed=[hex(value) for value in listed(v1)], generation=v1.u32(menu_cases.STATE + 32)))


def request_errors(programs):
    return {"API_ARG": 15}


def menu_add_cases(programs, built, patched, flash, check):
    """korg.menu.add: the pages a script adds show in the menu, turning one sends the script its menu event."""
    import menu_cases
    runtime = built.layout["runtime"]
    dev = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["menuadd"]["blob"])])})
    dev.run(2)
    entry = plugin_entry(dev, runtime)
    state = lambda offset: dev.u32(menu_cases.STATE + offset)
    texts = lambda: (menu_cases.text(dev, menu_cases.S_TITLE), menu_cases.text(dev, menu_cases.S_VALUE), menu_cases.text(dev, menu_cases.S_LINE3))
    check("menu-add-seiten-angelegt", state(60) == 2 and state(40) == 1 and dev.u32(entry + 12) == 2 and not dev.m.asserts, dict(items=state(60), plugins=state(40)))
    menu_cases.goto_plugin(dev, 0, 1)
    first = texts()
    menu_cases.press(dev, "edit_next")
    second = texts()
    check("menu-add-seitentexte", first == ("Speed", "5", "") and second == ("Offset", "-7", ""), dict(first=first, second=second))
    menu_cases.press(dev, "edit_prev")
    dev.turn(1, wait=0.3)
    up = texts()
    dev.turn(40, wait=0.3)
    top = texts()
    menu_cases.press(dev, "edit_next")
    dev.turn(-1, wait=0.3)
    down = texts()
    dev.turn(-127, wait=0.3)
    low = texts()
    values = variables(dev, entry, programs["menuadd"])
    check("menu-add-werte-und-grenzen", up[1] == "6" and top[1] == "10" and down[1] == "-8" and low[1] == "-50", dict(up=up, top=top, down=down, low=low))
    check("menu-add-ereignisse-erreichen-das-skript", values["speed"] == 10 and values["offset"] == -50 and values["after"] == 4, values)
    values = variables(dev, entry, programs["menuadd"])
    check("menu-add-keine-doppelten-seiten", state(60) == 2 and values["again"] == 0, dict(items=state(60), again=values["again"]))
    many = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["menumany"]["blob"])])})
    many.run(2)
    many_entry = plugin_entry(many, runtime)
    many_values = variables(many, many_entry, programs["menumany"])
    check("menu-add-zwoelf-seiten", many.u32(menu_cases.STATE + 60) == 12 and many_values["p11"] == 11 and many_values["p12"] == -1 and many_values["p13"] == -1 and many.u32(many_entry + 12) == 2
          and not many.m.asserts, dict(items=many.u32(menu_cases.STATE + 60), p12=many_values["p12"]))
    back = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["menuback"]["blob"])])})
    back.run(2)
    back_entry = plugin_entry(back, runtime)
    check("menu-add-bereich-verkehrt", back.u32(back_entry + 12) == 3 and back.u32(back_entry + 16) == request_errors(programs)["API_ARG"] and back.u32(menu_cases.STATE + 60) == 0,
          dict(state=back.u32(back_entry + 12), fault=back.u32(back_entry + 16)))


def blech_file(block, description=None, source=b"hello"):
    """A .blech file: the block, the description trailer (GDSC) when given, the source trailer (GSRC)."""
    out = block
    if description is not None:
        out += b"GDSC" + struct.pack("<I", len(description)) + description
    return out + b"GSRC" + struct.pack("<I", len(source)) + source


def import_cases(programs, built, patched, flash, check):
    """MANAGE PLUGINS lists every *.blech of the plugin folder and the loaded plugins in one list (loaded ones first, then the files not
    loaded, a plugin of both once): one page a plugin, its name and its state (OFF for one not loaded, the dial up loads and starts
    it); ENTER opens its pages, DESCRIPTION first, which shows the description from the file (the dial scrolls it)."""
    import menu_cases
    runtime = built.layout["runtime"]
    sym = built.symbols
    folder = "/KORG/blechtribe/Plugin/"
    healthy_block = bytes.fromhex(programs["healthy"]["blob"])
    foreign_block = with_flags(bytes.fromhex(programs["input"]["blob"]), 0)
    broken = bytearray(bytes.fromhex(programs["led"]["blob"]))
    broken[-1] ^= 1
    name = lambda block: block[36:52].split(b"\0")[0].decode()
    lines = [f"line {i}" for i in range(8)]
    description = "".join(f"{line}\n" for line in lines).encode()
    files = {folder + "a.blech": blech_file(healthy_block, description), folder + "b.BLECH": blech_file(foreign_block),
             folder + "notes.txt": b"text", folder + "short.blech": b"x" * 10, folder + "zero.blech": bytes(200), folder + "c.blech": blech_file(bytes(broken)),
             folder + "sub/inner.blech": healthy_block, folder + "._a.blech": b"\0\x05\x16\x07" + bytes(60), folder + "._b.BLECH": b"\0\x05\x16\x07" + bytes(60),
             folder + "store.a.bin": store_file(1, [("elsewhere", 1, 77)])}
    dev = with_card(patched, flash, files)
    dev.run(2)
    state = lambda offset: dev.u32(menu_cases.STATE + offset)
    byte = lambda offset: dev.read(menu_cases.STATE + offset, 1)[0]
    texts = lambda: (menu_cases.text(dev, menu_cases.S_TITLE), menu_cases.text(dev, menu_cases.S_VALUE), menu_cases.text(dev, menu_cases.S_LINE3))
    picture = lambda: dev.read(runtime + sym["RT_DISPLAY"], 1024)
    shown = lambda: dev.read(sym["SCRIPT_DISPLAY_RAM"], 1024)
    image = lambda: bytes(dev.read(sym["HOOK_INPUT"], 16 + 84))
    menu_cases.goto_group(dev, menu_cases.GROUP_PLUGINS, menu_cases.PLUGIN_MANAGE)
    asking = texts()
    menu_cases.press(dev, "menu", wait=0.5)
    opened = (state(menu_cases.S_LEVEL), menu_cases.counter(dev), menu_cases.tab(dev))
    names = [texts()]
    for _ in range(2):
        menu_cases.press(dev, "edit_next", wait=0.3)
        names.append(texts())
    menu_cases.press(dev, "edit_next", wait=0.3)
    wrapped = texts()
    check("liste-aus-den-dateien", asking == ("MANAGE PLUGINS", "", menu_cases.PRESS) and opened == (menu_cases.LEVEL_PLUGIN, (0, 3), "Plugins") and state(48) == 3
          and names == [(name(healthy_block), "OFF", ""), (name(foreign_block), "OFF", ""), (name(broken), "OFF", "")] and wrapped == names[0]
          and state(56) == 0, dict(asking=asking, opened=opened, names=names, wrapped=wrapped, count=state(48)))
    check("liste-versteckte-dateien-fehlen", state(48) == 3, dict(count=state(48), why="short, zero, notes and the ._ files are no plugins"))
    check("liste-vor-dem-laden-nichts", plugin_entry(dev, runtime) == 0 and state(40) == 0 and dev.u32(runtime + 96) == 1, dict(plugin=hex(plugin_entry(dev, runtime)), plugins=state(40)))
    not_loaded = (texts(), menu_cases.counter(dev))
    before_image = image()
    menu_cases.press(dev, "menu", wait=0.5)
    opened = texts()
    check("beschreibung-seite", not_loaded == ((name(healthy_block), "OFF", ""), (0, 3)) and menu_cases.counter(dev) == (0, 1) and state(56) == 2 and byte(0xF8) == 8
          and byte(0xF9) == 1 and opened == ("", "", "") and shown() == picture() and sum(bin(b).count("1") for b in picture()) > 200 and not dev.m.asserts,
          dict(not_loaded=not_loaded, listed=state(56), lines=byte(0xF8), on=byte(0xF9), texts=opened, same=shown() == picture()))
    top = picture()
    dev.turn(1, wait=0.2)
    dev.turn(1, wait=0.2)
    scrolled = (state(0xF4), shown() == picture() and picture() != top)
    dev.turn(5, wait=0.2)
    end = state(0xF4)
    dev.turn(-9, wait=0.2)
    check("beschreibung-scrollt", scrolled == (2, True) and end == 3 and state(0xF4) == 0, dict(scrolled=scrolled, end=end, back=state(0xF4)))
    menu_cases.press(dev, "menu", wait=0.4)
    check("beschreibung-enter-tut-nichts", state(40) == 0 and byte(0xF9) == 1 and not dev.m.asserts, dict(plugins=state(40), on=byte(0xF9)))
    menu_cases.press(dev, "exit", wait=0.4)
    shown_off = byte(0xF9)
    dev.turn(1, wait=0.8)
    head = plugin_entry(dev, runtime)
    check("dial-oben-laedt-und-startet", shown_off == 0 and head not in (0, 0xffffffff) and dev.u32(head + 12) == 2 and state(40) == 1 and state(36) == 0 and byte(0xFB) == 0
          and texts() == (name(healthy_block), "ON", "") and menu_cases.counter(dev) == (0, 3) and dev.u32(runtime + 96) == 1 and not dev.m.asserts,
          dict(state=dev.u32(head + 12) if head not in (0, 0xffffffff) else None, status=hex(state(36)), texts=texts(), counter=menu_cases.counter(dev)))
    kept = store_file(1, [("elsewhere", 1, 77)])
    check("laden-speicherbild-bleibt", image() == kept, dict(why="the file went through the buffer of the store image, which is read back from the card",
                                                          before=before_image[:24].hex(), after=image()[:24].hex()))
    dev.turn(-1, wait=0.4)
    off = (dev.u32(head + 12), texts())
    dev.turn(1, wait=0.4)
    check("stand-aus-und-an", off == (1, (name(healthy_block), "OFF", "")) and dev.u32(head + 12) == 2 and state(40) == 1 and not dev.m.asserts, dict(off=off, on=dev.u32(head + 12)))
    menu_cases.press(dev, "menu", wait=0.5)
    loaded_desc = (state(56), byte(0xF8), byte(0xF9), menu_cases.counter(dev))
    menu_cases.press(dev, "exit", wait=0.4)
    menu_cases.press(dev, "edit_next", wait=0.4)
    second = texts()
    dev.turn(1, wait=0.8)
    foreign = dev.u32(head)
    check("fremd-wartet-nach-dem-laden", loaded_desc == (2, 8, 1, (0, 2)) and second == (name(foreign_block), "OFF", "")
          and foreign not in (0, 0xffffffff) and dev.u32(foreign + 12) == 1 and state(40) == 2 and texts() == (name(foreign_block), "WRITE=ALLOW", "") and byte(0xFB) == 1,
          dict(loaded_desc=loaded_desc, second=second, state=dev.u32(foreign + 12) if foreign not in (0, 0xffffffff) else None, texts=texts(), psel=byte(0xFB)))
    menu_cases.press(dev, "write", wait=0.8)
    check("fremd-erlaubt-in-der-liste", dev.u32(foreign + 12) == 2 and state(44) == 1 and texts() == (name(foreign_block), "saved", ""),
          dict(state=dev.u32(foreign + 12), trusted=state(44), texts=texts()))
    menu_cases.press(dev, "edit_next", wait=0.4)
    third = texts()
    dev.turn(1, wait=0.8)
    rejected = (state(36), state(40), texts())
    check("abgelehnt", third == (name(broken), "OFF", "") and rejected[0] == 0x34 and rejected[1] == 2 and rejected[2][:2] == (name(broken), "rejected") and byte(0xFB) == 2
          and not dev.m.asserts, dict(third=third, rejected=rejected))
    menu_cases.press(dev, "menu", wait=0.5)
    menu_cases.press(dev, "exit", wait=0.5)
    up = (state(menu_cases.S_LEVEL), state(menu_cases.S_PAGE), byte(0xF9), texts())
    menu_cases.press(dev, "exit", wait=0.5)
    left = (state(menu_cases.S_LEVEL), state(menu_cases.S_PAGE), byte(0xF9), texts())
    check("beschreibung-verlassen-zeichnet-neu", up == (menu_cases.LEVEL_PLUGIN, 2, 0, (name(broken), "OFF", ""))
          and left == (2, menu_cases.PLUGIN_MANAGE, 0, ("MANAGE PLUGINS", "", menu_cases.PRESS)), dict(up=up, left=left))
    # the list again: the loaded ones first, the file that is not loaded last, nothing twice
    menu_cases.press(dev, "menu", wait=0.5)
    rows = {}
    for _ in range(3):
        rows[state(menu_cases.S_PAGE)] = texts()[0]
        menu_cases.press(dev, "edit_next", wait=0.2)
    order = [rows.get(page) for page in range(3)]
    check("liste-geladene-zuerst-nichts-doppelt", state(48) == 3 and order == [name(healthy_block), name(foreign_block), name(broken)], dict(order=order))
    # the imported scripts answer input, outside the menu
    leave_menu(dev)
    check("laden-verlassen", byte(0xF9) == 0 and dev.screen()["number"] == 1, dict(on=byte(0xF9), screen=dev.screen()["number"]))
    healthy = plugin_entry(dev, runtime)
    before = variables(dev, healthy, programs["healthy"])["count"]
    dev.m.send([0, 24, 1, 0, 0])
    dev.run(0.2)
    dev.m.send([0, 24, 0, 0, 0])
    dev.run(0.1)
    check("geladenes-laeuft", variables(dev, healthy, programs["healthy"])["count"] == before + 1, dict(before=before))

    # a plugin that is only in e2sPlugin.all (no file) is in the list once, without a description; one with a file takes its description from it
    both = with_card(patched, flash, {CARD_FILE: archive([healthy_block, foreign_block]), folder + "a.blech": blech_file(healthy_block, description)})
    both.run(2)
    shown_both = lambda: both.read(sym["SCRIPT_DISPLAY_RAM"], 1024)
    both_texts = lambda: (menu_cases.text(both, menu_cases.S_TITLE), menu_cases.text(both, menu_cases.S_VALUE), menu_cases.text(both, menu_cases.S_LINE3))
    menu_cases.goto_group(both, menu_cases.GROUP_PLUGINS, menu_cases.PLUGIN_MANAGE)
    menu_cases.press(both, "menu", wait=0.5)
    total = (both.u32(menu_cases.STATE + 48), both.u32(menu_cases.STATE + 40), menu_cases.state(both, menu_cases.S_PSEL))
    menu_cases.press(both, "menu", wait=0.5)
    with_file = (both.read(menu_cases.STATE + 0xF8, 1)[0], both.read(menu_cases.STATE + 0xF9, 1)[0])
    menu_cases.press(both, "exit", wait=0.4)
    menu_cases.press(both, "edit_next", wait=0.4)
    second = both_texts()
    menu_cases.press(both, "menu", wait=0.5)
    without_file = (both.read(menu_cases.STATE + 0xF8, 1)[0], both.read(menu_cases.STATE + 0xF9, 1)[0])
    both.turn(1, wait=0.3)
    check("liste-plugin-ohne-datei", total[:2] == (1, 2) and with_file == (8, 1) and second[0] == name(foreign_block) and without_file == (0, 1)
          and sum(bin(b).count("1") for b in shown_both()) > 100 and not both.m.asserts, dict(total=total, with_file=with_file, second=second, without_file=without_file))

    # a removed plugin is in the list again as one not loaded, and loads again
    again = with_card(patched, flash, {CARD_FILE: archive([healthy_block]), folder + "a.blech": blech_file(healthy_block, description)})
    again.run(2)
    menu_cases.goto_group(again, menu_cases.GROUP_PLUGINS, menu_cases.PLUGIN_MANAGE)
    menu_cases.press(again, "menu", wait=0.5)
    menu_cases.press(again, "menu", wait=0.5)
    menu_cases.press(again, "edit_prev", wait=0.4)
    menu_cases.press(again, "menu", wait=0.4)
    menu_cases.press(again, "menu", wait=0.8)
    menu_cases.press(again, "menu", wait=0.5)
    listed = (again.u32(menu_cases.STATE + 48), again.u32(menu_cases.STATE + 40), menu_cases.texts_of(again))
    again.turn(1, wait=0.8)
    head = plugin_entry(again, runtime, 1)
    check("entferntes-plugin-laedt-wieder", listed == (1, 0, (name(healthy_block), "OFF", ""))
          and head not in (0, 0xffffffff) and again.u32(head + 12) == 2 and again.u32(menu_cases.STATE + 40) == 1 and menu_cases.texts_of(again) == (name(healthy_block), "ON", "")
          and not again.m.asserts, dict(listed=listed, texts=menu_cases.texts_of(again)))

    # nothing at all, scripts switched off in the settings
    nothing = with_card(patched, flash, {folder + "notes.txt": b"text"})
    nothing.run(2)
    menu_cases.goto_group(nothing, menu_cases.GROUP_PLUGINS, menu_cases.PLUGIN_MANAGE)
    page = menu_cases.texts_of(nothing)
    menu_cases.press(nothing, "menu", wait=0.5)
    check("liste-ohne-dateien", page == ("MANAGE PLUGINS", "", menu_cases.PRESS) and menu_cases.texts_of(nothing) == ("MANAGE PLUGINS", "No Plugin", "")
          and menu_cases.state(nothing, menu_cases.S_LEVEL) == 2, dict(page=page, listed=menu_cases.texts_of(nothing)))
    off = with_card(patched, flash, {folder + "a.blech": healthy_block, "/KORG/blechtribe/settings.a.bin": menu_cases.settings_file(2, 2)})
    off.run(2)
    menu_cases.goto_group(off, menu_cases.GROUP_PLUGINS, menu_cases.PLUGIN_MANAGE)
    menu_cases.press(off, "menu", wait=0.5)
    off.turn(1, wait=0.6)
    check("laden-bei-ausgeschalteten-skripten", off.u32(menu_cases.STATE + 36) == 0x32 and plugin_entry(off, runtime) == 0 and off.u32(runtime + 96) == 1 and not off.m.asserts,
          dict(status=hex(off.u32(menu_cases.STATE + 36))))


def foreign_cases(programs, built, patched, flash, check):
    """A block the editor did not probe waits for the user's yes, once."""
    import menu_cases
    runtime = built.layout["runtime"]
    healthy_block = bytes.fromhex(programs["healthy"]["blob"])
    foreign_block = with_flags(bytes.fromhex(programs["input"]["blob"]), 0)
    dev = with_card(patched, flash, {CARD_FILE: archive([healthy_block, foreign_block])})
    dev.run(2)
    healthy = plugin_entry(dev, runtime)
    foreign = dev.u32(healthy)
    check("fremd-wartet", dev.u32(healthy + 12) == 2 and dev.u32(foreign + 12) == 1 and not dev.m.asserts, dict(healthy=dev.u32(healthy + 12), foreign=dev.u32(foreign + 12)))
    foreign_name = foreign_block[36:52].split(b"\0")[0].decode()
    menu_cases.goto_plugin(dev, 1)
    asking = texts(dev)
    dev.turn(1, wait=0.2)
    still = dev.u32(foreign + 12)
    check("fremd-fragt", asking == (foreign_name, "WRITE=ALLOW", "") and still == 1, dict(asking=asking, state=still))
    menu_cases.press(dev, "write", wait=0.8)
    allowed = texts(dev)
    medium = dev.m.mmc.card.medium
    files = menu_cases.read_settings_full(medium.data)
    check("fremd-erlaubt", dev.u32(foreign + 12) == 2 and allowed == (foreign_name, "saved", "")
          and files == {"b": (1, 3, [struct.unpack_from("<I", foreign_block, 12)[0]])} and not dev.m.asserts,
          dict(state=dev.u32(foreign + 12), texts=allowed, files=files))
    dev.m.send([0, 24, 1, 0, 0])
    dev.run(0.2)
    check("fremd-bekommt-ready-nach-ja", dev.u32(foreign + 12) == 2 and variables(dev, foreign, programs["input"])["readyCount"] == 1, dict(vars=variables(dev, foreign, programs["input"])))
    leave_menu(dev)
    dev.m.send([0, 24, 1, 0, 0])
    dev.run(0.3)
    check("fremd-lauft-nach-ja-ereignisse", variables(dev, foreign, programs["input"])["pressCount"] == 1, dict(vars=variables(dev, foreign, programs["input"])))
    # the next start does not ask again
    again = with_card(patched, flash, {CARD_FILE: archive([healthy_block, foreign_block]), **{path: volume_read(medium.data, path) for path in ["/KORG/blechtribe/settings.b.bin"]}})
    again.run(2)
    head = plugin_entry(again, runtime)
    check("fremd-fragt-nicht-wieder", again.u32(head + 12) == 2 and again.u32(again.u32(head) + 12) == 2, dict(healthy=again.u32(head + 12), foreign=again.u32(again.u32(head) + 12)))
    # the list holds 64 checksums (16 up to 1.3.7): a 65th allowed block pushes the oldest out
    most = built.symbols["MENU_MAX_TRUST"]
    full = with_card(patched, flash, {CARD_FILE: archive([foreign_block])})
    full.run(2)
    entry = plugin_entry(full, runtime)
    base = built.symbols["MENU_TRUST"]
    full.m.uc.mem_write(base, b"".join(struct.pack("<I", 100 + i) for i in range(most)))
    full.m.uc.mem_write(menu_cases.STATE + 44, struct.pack("<I", most))
    full.call(built.symbols["menu_confirm"], entry)
    listed = [full.u32(base + 4 * i) for i in range(most)]
    check("fremd-liste-voll-schiebt", most == 64 and full.u32(menu_cases.STATE + 44) == most and listed[:most - 1] == [101 + i for i in range(most - 1)]
          and listed[most - 1] == struct.unpack_from("<I", foreign_block, 12)[0], dict(listed=listed[-3:]))


def volume_read(image, path):
    volume = fat32.Volume(bytes(image))
    try:
        return volume.read(path)
    finally:
        volume.close()


def open_app(dev, group, page=0):
    """The way a user opens an app: its page in the BLECH menu, then ENTER (the MENU key). The firmware is on its main screen afterwards."""
    import menu_cases
    menu_cases.goto_group(dev, group, page)
    menu_cases.press(dev, "menu", wait=0.4)


def tap(dev, key=3, hold=0.12):
    dev.m.send([0, key, 1, 0, 0])
    dev.run(hold)
    dev.m.send([0, key, 0, 0, 0])
    dev.run(0.12)


def app_cases(programs, built, patched, flash, check, reference, displays):
    """Apps: loading changes nothing on the display, an app opens from the BLECH menu and only then draws, EXIT always leaves."""
    import menu_cases
    import unicorn
    runtime = built.layout["runtime"]
    block = lambda name: bytes.fromhex(programs[name]["blob"])
    shows = lambda dev, name: dev.fb() == displays[name]
    main_display = footprint(reference)["display"]
    control = lambda dev, name: dev.u32(runtime + built.symbols["SCRIPT_CONTROL_" + name])

    apps = with_card(patched, flash, {CARD_FILE: archive([block(name) for name in ["klicker", "snake", "drawer", "healthy"]])})
    apps.run(2)
    check("app-laden-laesst-das-display-in-ruhe", control(apps, "CARD_LOADED") == 4 and footprint(apps)["display"] == main_display
          and apps.screen()["number"] == 1 and not apps.m.asserts, dict(loaded=control(apps, "CARD_LOADED")))
    apps.run(1)
    check("app-ohne-oeffnen-zeichnet-nichts", footprint(apps)["display"] == main_display and not apps.m.asserts, "the plugin that draws every frame and is no app")

    pages = {}
    for group, label in [(menu_cases.GROUP_GAMES, "games"), (menu_cases.GROUP_TOOLS, "tools")]:
        menu_cases.goto_group(apps, group, 0)
        pages[label] = (menu_cases.texts_of(apps), menu_cases.tab(apps), menu_cases.counter(apps), menu_cases.page_overlap(apps))
    menu_cases.goto_top(apps, menu_cases.LIST_FEATURES)
    top = []
    for _ in range(6):
        top.append(menu_cases.text(apps, menu_cases.S_TITLE))
        menu_cases.press(apps, "edit_next")
    check("app-gruppen-im-menue", pages["games"] == (("Snake", "", menu_cases.PRESS), "Games", (0, 1), None) and pages["tools"] == (("Klicker", "", menu_cases.PRESS), "Tools", (0, 1), None)
          and top == ["FEATURES", "PLUGINS", "CUSTOMIZATION", "GAMES", "TOOLS", menu_cases.version_texts(patched)[0]], dict(pages=pages, top=top))

    open_app(apps, menu_cases.GROUP_TOOLS)
    check("app-oeffnet-aus-dem-menue", apps.screen()["number"] == 1 and shows(apps, "klickerReady") and control(apps, "READY") == 1 and not apps.m.asserts,
          dict(screen=apps.screen()))
    before = len(apps.m.panel_log)
    tap(apps)
    lit = [m for m in apps.m.panel_log[before:] if m == bytes([0, 20, 255, 0, 0])]
    check("app-zaehlt-und-zeigt", shows(apps, "klickerOne") and len(lit) >= 1, dict(packets=len(lit)))
    apps.press("menu", 0.3)
    check("app-tasten-gehoeren-der-offenen-app", apps.screen()["number"] == 1 and shows(apps, "klickerOne"), dict(screen=apps.screen()))
    apps.press("exit", 0.5)
    check("app-exit-zurueck-auf-den-hauptbildschirm", apps.screen()["number"] == 1 and footprint(apps)["display"] == main_display and not apps.m.asserts,
          dict(screen=apps.screen()))
    before = len(apps.m.panel_log)
    tap(apps)
    dark = [m for m in apps.m.panel_log[before:] if m == bytes([0, 20, 0, 0, 0])]
    check("app-zaehlt-auch-geschlossen", len(dark) >= 1 and footprint(apps)["display"] == main_display, dict(packets=len(dark)))
    open_app(apps, menu_cases.GROUP_TOOLS)
    check("app-oeffnet-wieder-mit-dem-stand", shows(apps, "klickerTwo"), "the count of the closed time is shown")
    apps.press("exit", 0.5)

    # Snake from the menu: the display is the browser model's after 150 frames with the same inputs
    snake = with_card(patched, flash, {CARD_FILE: archive([block("snake")])})
    snake.run(2)
    opened = []
    snake.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: opened.append(control(snake, "FRAMES")), begin=built.symbols["script_app_open"], end=built.symbols["script_app_open"])
    snake.m.uc.ctl_flush_tb()
    part_of = lambda dev: dev.u32(0xC06B2428)     # the firmware's selected part
    part_before = part_of(snake)
    open_app(snake, menu_cases.GROUP_GAMES)
    frames_of = lambda dev: control(dev, "FRAMES")
    first = opened[0] + 1       # the frame that handles open and runs the first `frame`: the browser model's frame 0
    schedule = {first - 1 + at: key for at, key in {20: 15, 60: 11, 100: 15, 130: 11}.items()}
    sent = set()
    while frames_of(snake) < first + 149 and snake.m.time_ns < 60e9 and not snake.m.asserts:
        snake.run(0.002)
        now = frames_of(snake)
        if now in schedule and now not in sent:
            sent.add(now)
            key = schedule[now]
            snake.m.send([0, key, 1, 0, 0])
            snake.m.send([0, key, 0, 0, 0])
    snake.run(0.006)
    drawn = snake.read(0xC031B310, 1024)
    check("snake-aus-dem-menue-in-der-firmware", frames_of(snake) == first + 149 and drawn == displays["snake150"] and not snake.m.asserts,
          dict(frames=frames_of(snake) - first, asserts=snake.m.asserts, equal=drawn == displays["snake150"]))
    part_in_app = part_of(snake)
    check("snake-part-tasten-aendern-die-part-nicht", part_in_app == part_before and drawn == displays["snake150"], dict(before=part_before, in_app=part_in_app, turned=drawn == displays["snake150"]))
    snake.press("exit", 0.5)
    check("snake-exit", snake.screen()["number"] == 1 and footprint(snake)["display"] == main_display and not snake.m.asserts, dict(screen=snake.screen()))
    for _ in range(3):
        snake.press(0x0F, 0.4)
    after_inc = part_of(snake)
    snake.press(0x0B, 0.4)
    after_dec = part_of(snake)
    snake.press(0x0B, 0.4)
    snake.press(0x0F, 0.4)
    check("part-tasten-nach-exit-wieder-der-firmware", after_inc == (part_before + 3) % 8 and after_dec == (after_inc - 1) % 8 and part_of(snake) == after_dec and not snake.m.asserts,
          dict(before=part_before, three_right=after_inc, one_left=after_dec, end=part_of(snake)))
    open_app(snake, menu_cases.GROUP_GAMES)
    check("snake-faengt-bei-open-neu-an", snake.read(0xC031B310, 1024) != displays["snake150"] and not snake.m.asserts, "a new game, not the old one")

    # the transport keys reach the firmware while an app is open (and the app sees them too), every other key stays with the app
    trans = with_card(patched, flash, {CARD_FILE: archive([block("transport")])})
    trans.run(2)
    entry = plugin_entry(trans, runtime)
    seen = lambda: variables(trans, entry, programs["transport"])
    playing = lambda: trans.u32(0xC06BC318)
    open_app(trans, menu_cases.GROUP_TOOLS)
    before = playing()
    trans.press(0x02, 1.0)
    started = playing()
    trans.press(0x01, 0.6)
    stopped = playing()
    trans.press(0x00, 0.4)
    trans.press(0x01, 0.4)
    trans.press(0x03, 0.3)
    got = seen()
    check("app-offen-play-stop-erreichen-die-firmware", (before, started, stopped) == (0, 1, 0) and trans.screen()["number"] == 1 and not trans.m.asserts,
          dict(transport=(before, started, stopped), screen=trans.screen()))
    check("app-offen-sieht-play-stop-auch", got["plays"] == 1 and got["stops"] == 2 and got["recs"] == 1 and got["others"] == 1, got)
    # the app is still open (the keys did not close it) and the other keys still do not reach the firmware: MENU stays with the app
    trans.press("menu", 0.3)
    check("app-offen-andere-tasten-bleiben-bei-der-app", trans.screen()["number"] == 1 and seen()["others"] == 2 and not trans.m.asserts, seen())

    # an app that faults shows its fault on its own screen; a plugin that is no app shows it in the menu only
    broken = with_card(patched, flash, {CARD_FILE: archive([block("appfault"), block("fault")])})
    broken.run(2)
    open_app(broken, menu_cases.GROUP_GAMES)
    broken.run(0.2)
    check("app-fehler-auf-dem-eigenen-bildschirm", shows(broken, "appFault") and not broken.m.asserts, dict(screen=broken.screen()))
    broken.press("exit", 0.5)
    tap(broken, 24)
    check("fehler-ohne-app-zeichnet-nichts", footprint(broken)["display"] == main_display and not broken.m.asserts, "the fault of a plugin that is no app")
    menu_cases.goto_plugin(broken, 1)
    fault_page = menu_cases.texts_of(broken)
    check("fehler-seite-im-menue", fault_page[0] == "fault" and fault_page[1].startswith("DIV_ZERO L") and fault_page[2] == "" and menu_cases.page_overlap(broken) is None, dict(page=fault_page))

    # EXIT cannot be swallowed, by a plugin that catches every key or one that holds the display
    trap = with_card(patched, flash, {CARD_FILE: archive([block("trap"), block("taker")])})
    trap.run(2)
    entry = plugin_entry(trap, runtime)
    open_app(trap, menu_cases.GROUP_GAMES)
    check("exit-oeffnet-die-falle-nicht-zu", trap.screen()["number"] == 1 and trap.read(0xC031B310, 1024) != reference.fb(), "the trap draws its picture")
    trap.press("exit", 0.5)
    trap_vars = variables(trap, entry, programs["trap"])
    check("exit-schliesst-trotz-fallen-app", trap.screen()["number"] == 1 and footprint(trap)["display"] == main_display and trap_vars["exits"] == 0 and trap_vars["closes"] == 1,
          trap_vars)
    tap(trap, 3, 0.2)
    taker_entry = trap.u32(entry)
    check("take-zeigt-das-bild", trap.screen()["number"] == 1 and trap.read(0xC031B310, 1024) == displays["taken"] and variables(trap, taker_entry, programs["taker"])["granted"] == 1,
          variables(trap, taker_entry, programs["taker"]))
    trap.press("exit", 0.5)
    check("exit-beendet-take", footprint(trap)["display"] == main_display and variables(trap, taker_entry, programs["taker"])["closes"] == 1 and variables(trap, taker_entry, programs["taker"])["exits"] == 0 and not trap.m.asserts,
          variables(trap, taker_entry, programs["taker"]))
    check("laden-allein-zeichnet-nie", footprint(trap)["display"] == main_display, "the plugin that can take the display did not, before its key")

    # bitmap and textNumber: the display is the browser model's, pixel for pixel
    drawing = with_card(patched, flash, {CARD_FILE: archive([block("bitmaps")])})
    drawing.run(2)
    tap(drawing, 3, 0.2)
    drawn = drawing.read(0xC031B310, 1024)
    check("bitmap-und-text-mit-zahl-wie-im-browser", drawn == displays["bitmaps"] and drawn != main_display and variables(drawing, plugin_entry(drawing, runtime), programs["bitmaps"])["granted"] == 1
          and not drawing.m.asserts, dict(equal=drawn == displays["bitmaps"], asserts=drawing.m.asserts))


def card_cases(request, programs, built, patched, stock, flash, check):
    runtime = built.layout["runtime"]
    status = lambda dev: [dev.u32(runtime + built.symbols["SCRIPT_CONTROL_" + name]) for name in ["CARD_STATUS", "CARD_LOADED", "CARD_REJECTED"]]
    blocks = {name: bytes.fromhex(programs[name]["blob"]) for name in ["healthy", "led", "fault"]}
    js_file = bytes.fromhex(request["archive"])

    reference = with_card(stock, flash, {})
    reference.run(2)
    empty = with_card(patched, flash, {})
    empty.run(2)
    check("karte-leer-status", status(empty) == [2, 0, 0], status(empty))
    check("karte-leer-nur-blechy-scharf", empty.u32(runtime + built.symbols["SCRIPT_CONTROL_ARMED"]) == 1 and plugin_entry(empty, runtime) == 0 and empty.u32(runtime) not in (0, 0xffffffff),
          "no plugin file: no plugin, but Blechy, the app built into BLECH, is loaded and armed")
    check("karte-leer-wie-original", footprint(empty) == footprint(reference))

    spans = []
    loaded = with_card(patched, flash, {CARD_FILE: js_file})
    hits = []
    import unicorn
    card_hook = next(address for address, _, name in built.profile.sites if name == 'script_card_hook')
    loaded.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: hits.append((a, loaded.m.time_ns)), begin=card_hook, end=card_hook)
    loaded.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: spans.append(loaded.m.time_ns), begin=card_hook+4, end=card_hook+4)
    loaded.m.uc.ctl_flush_tb()
    loaded.run(2)
    check("karte-geladen-status", status(loaded) == [1, 2, 0], status(loaded))
    check("karte-geladen-scharf", loaded.u32(runtime + built.symbols["SCRIPT_CONTROL_ARMED"]) == 1)
    check("karte-lader-dauer", bool(hits) and bool(spans) and spans[0] > hits[0][1],
          dict(ms=round((spans[0] - hits[0][1]) / 1e6, 2) if hits and spans else None, hits=len(hits)))
    check("karte-start-lauf", loaded.u32(plugin_entry(loaded, runtime) + 12) == 2 and not loaded.m.asserts)
    packets = [message for message in loaded.m.panel_log if message == bytes([0, 0, 0, 0, 0])]
    check("karte-ready-led", len(packets) >= 1, len(packets))
    for level in [255, 0]:
        before = len(loaded.m.panel_log)
        loaded.m.send([0, 24, 1, 0, 0])
        loaded.run(0.12)
        delivered = [message for message in loaded.m.panel_log[before:] if message == bytes([0, 0, level, 0, 0])]
        check("karte-taste-" + str(level), len(delivered) == 1 and loaded.m.leds.get(0) == level, len(delivered))
        loaded.m.send([0, 24, 0, 0, 0])
        loaded.run(0.04)
    loaded.press("menu", 0.15)
    check("karte-firmware-bedienbar", loaded.screen()["number"] != 1 and not loaded.m.asserts)

    mixed = with_card(patched, flash, {CARD_FILE: archive([blocks["fault"][:60] + bytes([blocks["fault"][60] ^ 1]) + blocks["fault"][61:], blocks["healthy"]])})
    mixed.run(2)
    check("karte-block-defekt", status(mixed) == [1, 1, 1] and mixed.u32(runtime + built.symbols["SCRIPT_CONTROL_ARMED"]) == 1, status(mixed))

    for name, data, want in [("pruefsumme", archive([blocks["healthy"]], crc_wrong=True), 4),
                              ("kennung", b"XXXX" + js_file[4:], 3),
                              ("abgeschnitten", js_file[:len(js_file) // 2], 5)]:
        broken = with_card(patched, flash, {CARD_FILE: data})
        broken.run(2)
        check("karte-datei-" + name, status(broken)[0] == want
              and broken.u32(runtime + built.symbols["SCRIPT_CONTROL_ARMED"]) == 1 and plugin_entry(broken, runtime) == 0
              and footprint(broken) == footprint(reference), status(broken))

    displays = {name: bytes.fromhex(value) for name, value in request["displays"].items()}
    shows = lambda dev, name: dev.fb() == displays[name]
    app_cases(programs, built, patched, flash, check, reference, displays)

    hw = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["readhw"]["blob"])])})
    hw.run(2)
    entry = plugin_entry(hw, runtime)
    read = lambda: variables(hw, entry, programs["readhw"])
    first = read()
    t1 = hw.m.time_ns
    check("hw-lesen-ruhezustand", (first["transport"], first["tempo"], first["pattern"], first["part"], first["step"]) == (0, reference.u32(0xC0691518), 0, 0, 0)
          and first["mute"] in (0, 1) and first["knob"] == 0, first)
    hw.m.send([2, 3, 1, 244, 0])
    hw.m.press(2, True)
    hw.run(0.05)
    hw.m.press(2, False)
    hw.run(1.2)
    played = read()
    check("hw-lesen-play", played["transport"] == 1 and played["step"] > 5, played)
    check("hw-lesen-regler", played["knob"] == 500, played["knob"])
    elapsed = (hw.m.time_ns - t1) / 1e6
    check("hw-uhr", abs((played["ms"] - first["ms"]) - elapsed) < 120 and played["ms"] > first["ms"],
          dict(device_ms=played["ms"] - first["ms"], emulator_ms=round(elapsed)))

    act = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["actions"]["blob"])])})
    act.run(2)
    word = lambda address: act.u32(address)
    pad = lambda index: (act.m.send([4, index, 0, 100, 1]), act.run(0.15), act.m.send([4, index, 0, 0, 0]), act.run(0.1))
    mute_byte = lambda part: bytes(act.m.uc.mem_read(act.a(0xC06B2F9D) + 0x330 * part, 1))[0]
    pad(0)
    check("hw-handeln-tempo", word(0xC0691518) == 1200, word(0xC0691518))
    pad(1)
    act.run(0.5)
    check("hw-handeln-pattern", word(0xC06B2420) == 5, word(0xC06B2420))
    pad(2)
    check("hw-handeln-part", word(0xC06B2428) == 3, word(0xC06B2428))
    act.call(built.symbols['script_mute_glue'], 2, 1)
    act.run(0.1)
    before_mute = mute_byte(2)
    pad(3)
    check("hw-handeln-mute", before_mute == 1 and mute_byte(2) == 0 and not act.m.asserts, (before_mute, mute_byte(2)))
    pad(4)
    act.run(0.3)
    playing = word(0xC06BC318)
    pad(5)
    act.run(0.3)
    check("hw-handeln-play-stop", playing == 1 and word(0xC06BC318) == 0 and not act.m.asserts, (playing, word(0xC06BC318)))

    seq = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["seqevents"]["blob"]), bytes.fromhex(programs["actions"]["blob"])])})
    seq.run(2)
    seq.call(built.symbols['script_tempo_glue'], 1600)
    seq.run(0.1)
    seq_entry = plugin_entry(seq, runtime)
    counts = lambda: variables(seq, seq_entry, programs["seqevents"])
    seq_pad = lambda index: (seq.m.send([4, index, 0, 100, 1]), seq.run(0.15), seq.m.send([4, index, 0, 0, 0]), seq.run(0.1))
    quiet = counts()
    check("ereignis-ruhe", all(quiet[name] == 0 for name in ["plays", "stops", "recs", "steps", "beats", "saves"]), quiet)
    seq.m.press(2, True)
    seq.run(0.05)
    seq.m.press(2, False)
    seq.run(2.0)
    playing = counts()
    check("ereignis-play-schritte", playing["plays"] == 1 and 17 <= playing["steps"] <= 25 and playing["beats"] >= playing["steps"] // 4 - 1
          and playing["beats"] <= playing["steps"] // 4 + 1, playing)
    seq.m.press(1, True)
    seq.run(0.05)
    seq.m.press(1, False)
    seq.run(0.5)
    stopped = counts()
    check("ereignis-stop", stopped["stops"] == 1 and stopped["steps"] <= playing["steps"] + 2, stopped)
    for index in (1, 0, 2, 3):
        if index == 3:
            seq.call(built.symbols['script_mute_glue'], 2, 1)
            seq.run(0.1)
        seq_pad(index)
        seq.run(0.4)
    seq.run(0.5)
    echoed = counts()
    check("ereignis-tempo-pattern-part-mute", (echoed["tempoSeen"], echoed["patternSeen"], echoed["partSeen"], echoed["muteSeen"]) == (1200, 5, 3, 20),
          dict(tempo=echoed["tempoSeen"], pattern=echoed["patternSeen"], part=echoed["partSeen"], mute=echoed["muteSeen"]))
    first_word = seq.u32(0xC004C1B4)
    check("ereignis-save-haken-eingehaengt", first_word >> 24 == 0xEA, hex(first_word))

    lights = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["lights"]["blob"])])})
    import unicorn
    gpio_calls = []
    lights.m.uc.hook_add(unicorn.UC_HOOK_CODE, lambda u, a, s, d: gpio_calls.append(tuple(u.reg_read(r) for r in (unicorn.arm_const.UC_ARM_REG_R0, unicorn.arm_const.UC_ARM_REG_R1, unicorn.arm_const.UC_ARM_REG_R2, unicorn.arm_const.UC_ARM_REG_R3))),
                         begin=lights.a(0xC0016BB4), end=lights.a(0xC0016BB4))
    lights.m.uc.ctl_flush_tb()
    lights.run(2)
    pad_l = lambda index: (lights.m.send([4, index, 0, 100, 1]), lights.run(0.15), lights.m.send([4, index, 0, 0, 0]), lights.run(0.1))
    gpio_calls.clear()
    pad_l(6)
    wanted = [(0x01E26000, 1, 3, 0x08), (0x01E26000, 0, 3, 0x10), (0x01E26000, 0, 3, 0x20)]
    check("hw-backlight", any(gpio_calls[i:i + 3] == wanted for i in range(len(gpio_calls))), dict(calls=len(gpio_calls), last=gpio_calls[-3:]))
    manager = lights.u32(0xC0345A1C)
    hold = lambda: lights.read(manager + 0xB98, 1)[0]
    check("hw-led-halten-flag", hold() == 0)
    pad_l(7)
    check("hw-led-halten-flag", hold() == 1, hold())
    lights.m.press(2, True)
    lights.run(0.1)
    lights.m.press(2, False)
    lights.run(0.6)
    play_led_held = lights.m.leds.get(0x09, 0)
    check("hw-led-halten-sperrt-firmware-leds", lights.u32(0xC06BC318) == 1 and play_led_held == 0, dict(transport=lights.u32(0xC06BC318), led=play_led_held))
    pad_l(8)
    lights.run(0.5)
    check("hw-led-halten-loesen", hold() == 0 and lights.m.leds.get(0x09, 0) > 0 and not lights.m.asserts, dict(hold=hold(), led=lights.m.leds.get(0x09, 0)))

    saving = with_card(patched, flash, {CARD_FILE: archive([bytes.fromhex(programs["klickerstore"]["blob"])])})
    writes_of = lambda dev: dev.u32(runtime + built.symbols["SCRIPT_CONTROL_STORE_WRITES"])
    saving.run(5)
    check("speicher-ohne-save-keine-datei", not store_files(saving.m.mmc.card.medium.data) and writes_of(saving) == 0)
    writes = writes_of = lambda dev: dev.u32(runtime + built.symbols["SCRIPT_CONTROL_STORE_WRITES"])
    for _ in range(3):
        saving.m.send([0, 3, 1, 0, 0])
        saving.run(0.1)
        saving.m.send([0, 3, 0, 0, 0])
        saving.run(0.1)
    check("speicher-pause-zwischen-schreibvorgaengen", writes(saving) == 1, writes(saving))
    saving.run(3)
    stored = store_files(saving.m.mmc.card.medium.data)
    newest = max(stored.values(), key=lambda item: item["generation"], default=None)
    check("speicher-schreibt-datei", writes(saving) == 2 and newest is not None and newest["generation"] == 2
          and newest["records"] == [("klickerstore", 1, 3)], dict(writes=writes(saving), files=sorted(stored)))
    image = bytearray(saving.m.mmc.card.medium.data)
    again = Dev(patched[0x100:], flash, 0)
    again.m.insert_card(SDCard(MemoryMedium(bytearray(image))))
    again.run(2)
    import menu_cases
    open_app(again, menu_cases.GROUP_TOOLS)
    check("speicher-neustart-zaehler", shows(again, "klickerThree") and not again.m.asserts)
    broken = bytearray(image)
    volume = fat32.Volume(broken)
    for name in ["store.a.bin", "store.b.bin"]:
        try:
            data = bytearray(volume.read("/KORG/blechtribe/Plugin/" + name))
        except fat32.FatError:
            continue
        if parse_store(bytes(data))["generation"] == 2:
            data[20] ^= 1
            volume.write("/KORG/blechtribe/Plugin/" + name, bytes(data), overwrite=True)
    volume.close()
    fallback = Dev(patched[0x100:], flash, 0)
    fallback.m.insert_card(SDCard(MemoryMedium(bytearray(broken))))
    fallback.run(2)
    open_app(fallback, menu_cases.GROUP_TOOLS)
    check("speicher-defekte-datei-faellt-zurueck", status(fallback)[0] == 1 and not shows(fallback, "klickerThree") and not fallback.m.asserts)

    killed = with_card(patched, flash, {CARD_FILE: js_file}, held=0x2000)
    killed.run(2)
    killed_status = 0xffffffff if built.profile.build == 'synth' else 7
    check("karte-exit", status(killed)[0] == killed_status and killed.u32(runtime + built.symbols["SCRIPT_CONTROL_ARMED"]) == 0xffffffff
          and killed.m.mmc.card.sectors_read < loaded.m.mmc.card.sectors_read,
          dict(status=status(killed), read=killed.m.mmc.card.sectors_read, loaded=loaded.m.mmc.card.sectors_read))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--flash", nargs="*", default=[], type=Path)
    args = parser.parse_args()
    request = json.load(sys.stdin)
    flash = load_flash(args.flash) if args.flash else None
    result = firmware_cases(args.base.read_bytes(), flash, request)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
