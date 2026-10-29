/**
 * The Electribe as a small library for the terminal page (idea 36). Calls go
 * through a DeviceSession on the emulator, planner and gate; a session on the
 * real Electribe is refused. The real device only ever gets what a script
 * did here, replayed by the terminal after it passed (src/rehearsal.mjs).
 */
import { BUTTONS, ENCODERS, KNOBS, KNOB_MAX, PADS, TOUCH_BUTTON, TOUCHPAD_MAX } from "../data/panel.mjs";
import EXEC from "../data/exec.mjs";
import { u32le } from "./bytes.mjs";
import { tableEntry, ramToFile } from "./map/address.mjs";
import { field, readRaw } from "./map/index.mjs";
import { plan } from "./plan.mjs";
import { identify } from "./firmware.mjs";
import { ramTools } from "./ramsearch.mjs";
import { remoteInfo, command, stub, messageStub, panel, KEY, ENCODER, TEST } from "./remote.mjs";

export const SCREEN_W = 128;
export const SCREEN_H = 64;

/** A picture as display bytes (8 pages of 128 columns, bit 0 the top row), from any form HELP names. */
export function toDisplay(image) {
  if ((image instanceof Uint8Array || Array.isArray(image)) && image.length === SCREEN_W * SCREEN_H / 8 && typeof image[0] === "number") {
    return Uint8Array.from(image);
  }
  let lit;
  if (typeof image === "function") lit = image;
  else if (Array.isArray(image) && typeof image[0] === "string") {
    if (image.length > SCREEN_H) throw new RangeError(`a picture has ${SCREEN_H} rows, got ${image.length}`);
    lit = (x, y) => /[#X1]/.test(image[y]?.[x] ?? "");
  } else if ((image instanceof Uint8Array || Array.isArray(image)) && image.length === SCREEN_W * SCREEN_H) {
    lit = (x, y) => !!image[y * SCREEN_W + x];
  } else {
    throw new TypeError("screen.set nimmt 1024 Display-Bytes, 64 Textzeilen, 8192 Pixel oder eine Funktion (x, y) => an/aus");
  }
  const out = new Uint8Array(SCREEN_W * SCREEN_H / 8);
  for (let y = 0; y < SCREEN_H; y++) for (let x = 0; x < SCREEN_W; x++) if (lit(x, y)) out[(y >> 3) * SCREEN_W + x] |= 1 << (y & 7);
  return out;
}

/** Display bytes as 64 strings, `#` lit. */
export function toRows(bytes) {
  return Array.from({ length: SCREEN_H }, (_, y) =>
    Array.from({ length: SCREEN_W }, (_, x) => ((bytes[(y >> 3) * SCREEN_W + x] >> (y & 7)) & 1 ? "#" : ".")).join(""));
}

export const HELP = [
  "KORG.screen.set(bild)     Bild aufs Display: 64 Textzeilen mit # für an, 1024 Display-Bytes, 8192 Pixel oder (x, y) => an/aus",
  "KORG.screen.get()         das Display als 64 Textzeilen",
  "KORG.screen.state()       welcher Bildschirm, welche Seite, welcher Part",
  "KORG.press(name)          eine Taste drücken und loslassen, etwa \"menu\", \"exit\", \"play\"; mit dem BLECH-Satz auch am Gerät",
  "KORG.turn(n, rad)         das Hauptrad (oder einen Drehgeber, etwa \"cutoff\") um n Rasten drehen (negativ nach links), nur mit dem BLECH-Satz",
  "KORG.knob(name, wert)     einen Regler auf 0 bis 255 stellen, etwa \"level\"; ab BLECHTRIBE 1.3.8, auch am Gerät",
  "KORG.pad(n, {velocity, hold})  Pad 1 bis 16 anschlagen (hold: true lässt es gedrückt, velocity 0 lässt los); ab 1.3.8",
  "KORG.touch(x, y)          das Touchpad bei x, y (0 bis 1023) berühren und loslassen; ab 1.3.8",
  "KORG.hold(name, unten)    eine Taste nur drücken (true) oder nur loslassen (false), etwa für SHIFT; ab 1.3.8",
  "KORG.testMode(an)         Test-Modus: Display, Licht und LEDs aus, Auto Power Off angehalten (true), oder zurück (false); ab 1.3.8",
  "KORG.buttons              die Namen aller Tasten",
  "KORG.ram.read(adr, n)     n Byte aus dem RAM",
  "KORG.ram.snapshot({from, to})  einen RAM-Bereich festhalten; was die Gerätekarte und die Speicherkarte erklären, wird nicht gelesen ({mask: false} liest alles, {show: [\"image\"]} holt eine Gruppe zurück)",
  "KORG.ram.diff(a, b)       zwei Snapshots vergleichen: geänderte Läufe, jeder mit dem nächsten bekannten Bereich; .summary() ist die Kurzfassung",
  "KORG.ram.search(wert, {from, to})  eine 32-Bit-Zahl ({width: 1 oder 2}), Bytes oder Text im RAM suchen, Bekanntes ausgeblendet; {snapshot} sucht in einem Snapshot ohne zu lesen",
  "KORG.ram.where(adr)       was an einer Adresse bekannt ist",
  "KORG.exec(code, {at})     ARM-Code ausführen: Uint8Array, Array aus 32-Bit-Wörtern oder (adresse) => eines von beiden. Landet im Stub-Puffer ab 0xC1000000 (1 KiB), muss mit r0 = 1 zurückkehren; die Originalbytes kommen danach zurück. {guard: [[adr, n]]} prüft Firmware-Code, den der Stub aufruft",
  "KORG.fx.mfx(n), fx.ifx(n) Name eines Effekt-Platzes",
  "run(\"name\")             ein Plugin im Bereich Lauf starten, eigenes oder Beispiel (nur im Browser)",
  "korg.display.text(\"Hi\", 0, 0)  eine Zeile Plugin-Code sofort im Bereich Lauf ausführen (jede Zeile, die mit korg. beginnt)",
  "KORG.help()               diese Liste",
];

/**
 * Give a session the firmware file, unless it has one: the gate's dry run
 * and the code guards need the image. The caller passes the VSB loaded in the emulator.
 */
export async function ensureFirmware(session, bytes) {
  if (session.firmware) return session;
  if (!bytes) throw new Error("Erst im Bereich Emulator die SYSTEM.VSB wählen.");
  session.useFirmware(bytes, await identify(bytes), { units: session.units ?? null, profile: session.profile ?? null });
  return session;
}

/** Guards for an exec: the bytes the firmware file holds at each range, which the device must still have. */
function guardsOf(s, ranges) {
  return ranges.map(([addr, length]) => {
    const from = ramToFile(addr);
    if (!Number.isInteger(addr) || !Number.isInteger(length) || length < 1 || from < 0 || from + length > s.firmwareBytes.length) throw new RangeError(`guard 0x${Number(addr).toString(16)}: nicht in der Firmware-Datei`);
    return { addr, bytes: Uint8Array.from(s.firmwareBytes.subarray(from, from + length)) };
  });
}

/** Code as bytes: a Uint8Array is taken as it is, an Array or Uint32Array holds 32-bit words, little endian. */
export function toCode(code) {
  if (code instanceof Uint8Array) return Uint8Array.from(code);
  if (code instanceof Uint32Array || (Array.isArray(code) && code.every(n => Number.isInteger(n)))) {
    if (Array.from(code).some(n => n < 0 || n > 0xffffffff)) throw new RangeError("a word is 0 to 0xFFFFFFFF");
    return Uint8Array.from(Array.from(code).flatMap(n => u32le(n)));
  }
  throw new TypeError("exec nimmt eine Uint8Array, ein Array aus 32-Bit-Wörtern oder eine Funktion, die eines von beiden liefert");
}

/**
 * @param {{ session: () => object | null, emulator: { port: object, baseFirmware: Uint8Array | null, button: (index: number) => Promise<void> } }} where
 * @param {{ hooks?: { press?: (why: string) => void, read?: () => void }, print?: (text: string) => void }} [opts] hooks tell a rehearsal what a script did besides sending; `print` is where progress lines go
 */
export function makeKorg({ session, emulator }, { hooks = {}, print = null } = {}) {
  const live = () => {
    const s = session();
    if (!s || s.port !== emulator.port) throw new Error("Erst im Bereich Gerät „Mit Emulator verbinden“. Das Terminal arbeitet nur mit dem Emulator.");
    return s;
  };
  // Writes go through the gate's dry run, which needs the firmware image: the
  // VSB loaded in the emulator, unless the effect editor already gave one.
  const withFirmware = () => ensureFirmware(live(), emulator.baseFirmware);
  const readRam = async (addr, length) => {
    hooks.read?.();
    const s = live();
    if (!Number.isInteger(addr) || !Number.isInteger(length) || length < 1 || length > 0x4000) throw new RangeError("ram.read(adresse, anzahl), anzahl 1 bis 16384");
    return s.exclusive(async () => {
      const run = await s.sender.run(plan({ kind: "readRam", addr, length }, { channel: s.device.channel }));
      if (!run.ok) throw run.error;
      return run.results[0].value;
    });
  };
  const ram = ramTools({ read: readRam, print });
  const slotName = async (kind, n) => {
    const e = tableEntry(`table.${kind}`, n - 1);
    return readRaw(await readRam(e.ram, e.size), field("fx.name"));
  };
  const buttons = Object.fromEntries(BUTTONS.map(b => [b.id, b.index]));
  const encoders = Object.fromEntries(ENCODERS.map(e => [e.id, e.index]));
  const knobs = Object.fromEntries(KNOBS.map(k => [k.id, k.index]));
  const named = (table, name, what) => {
    const index = typeof name === "number" ? name : table[name];
    if (index === undefined) throw new Error(`Kein ${what} „${name}“. Namen: ${Object.keys(table).join(", ")}`);
    return index;
  };
  // With the BLECH runtime a key goes through KORG.exec, so it can be sent to the device too; without it the emulator's panel.
  // `message` (a panel message) needs a runtime that takes whole messages (1.3.8): remoteInfo().message.
  const remote = async (word, message = null) => {
    if (!emulator.baseFirmware) return false;
    const s = await withFirmware();
    const info = remoteInfo(s.firmwareBytes);
    if (info === null) return false;
    if (message && info.message === null) throw new Error("Diese Firmware nimmt nur Tasten und das Hauptrad an, Regler, Pads und Touchpad brauchen BLECHTRIBE 1.3.8.");
    const code = message ? messageStub(info.mailbox, info.message, message) : stub(info.mailbox, word);
    const res = await s.apply({ kind: "exec", code: toCode(code), at: EXEC.stubAt, guards: guardsOf(s, [[EXEC.icache.addr, EXEC.icache.length]]), invalidate: true }, { confirmed: true });
    if (!res.ok) throw new Error(res.error?.message ?? res.gate?.reasons?.map(r => r.message).join(" ") ?? "abgelehnt");
    return true;
  };
  const send = async message => {
    if (!(await remote(null, message))) throw new Error("Das geht nur mit einer Firmware mit dem BLECH-Satz (die Laufzeit nimmt den Befehl an).");
  };

  return {
    help: () => HELP.join("\n"),
    buttons: Object.keys(buttons),
    screen: {
      async set(image) {
        const res = await (await withFirmware()).apply({ kind: "screenWrite", bytes: toDisplay(image) }, { confirmed: true });
        if (!res.ok) throw new Error(res.error?.message ?? res.gate?.reasons?.map(r => r.message).join(" ") ?? "abgelehnt");
        return "Bild steht im Display, bis die Firmware neu zeichnet.";
      },
      async get() { hooks.read?.(); return toRows(await live().readDisplay()); },
      state() { hooks.read?.(); return live().screen(); },
    },
    async exec(code, { at = EXEC.stubAt, guard = [], invalidate = true } = {}) {
      const s = await withFirmware();
      const bytes = toCode(typeof code === "function" ? code(at) : code);
      // What the stub calls in the firmware must still be what the firmware file holds, or nothing runs.
      const ranges = [...(invalidate ? [[EXEC.icache.addr, EXEC.icache.length]] : []), ...guard];
      const guards = guardsOf(s, ranges);
      const res = await s.apply({ kind: "exec", code: bytes, at, guards, invalidate }, { confirmed: true });
      if (!res.ok) throw new Error(res.error?.message ?? res.gate?.reasons?.map(r => r.message).join(" ") ?? "abgelehnt");
      return "Code ausgeführt, die Originalbytes im Stub-Puffer sind zurückgeschrieben.";
    },
    async press(name) {
      const index = typeof name === "number" ? name : buttons[name];
      if (index === undefined) throw new Error(`Keine Taste „${name}“. Namen: ${Object.keys(buttons).join(", ")}`);
      live();
      if (await remote(command(KEY, index))) return `${name} gedrückt`;
      hooks.press?.("Tastendrücke ohne die Tasten der BLECH-Laufzeit");
      await emulator.button(index);
      return `${name} gedrückt`;
    },
    async turn(delta, encoder = 0) {
      const word = command(ENCODER, named(encoders, encoder, "Drehgeber"), delta);
      if (!(await remote(word))) throw new Error("Drehen geht nur mit einer Firmware mit dem BLECH-Satz (die Laufzeit nimmt den Befehl an).");
      return `um ${delta} gedreht`;
    },
    async knob(name, value) {
      if (!Number.isInteger(value) || value < 0 || value > KNOB_MAX) throw new RangeError(`Reglerwert 0 bis ${KNOB_MAX}`);
      await send(panel.knob(named(knobs, name, "Regler"), value));
      return `${name} auf ${value}`;
    },
    async pad(n, { velocity = 100, hold = false } = {}) {
      if (!Number.isInteger(n) || n < 1 || n > PADS.length) throw new RangeError(`Pad 1 bis ${PADS.length}`);
      if (!Number.isInteger(velocity) || velocity < 0 || velocity > 127) throw new RangeError("Anschlag 0 bis 127");
      await send(panel.pad(n - 1, velocity));
      if (velocity && !hold) await send(panel.pad(n - 1, 0));
      return velocity ? `Pad ${n} ${hold ? "gedrückt" : "angeschlagen"}` : `Pad ${n} losgelassen`;
    },
    async touch(x, y) {
      for (const v of [x, y]) if (!Number.isInteger(v) || v < 0 || v > TOUCHPAD_MAX) throw new RangeError(`Touchpad 0 bis ${TOUCHPAD_MAX}`);
      await send(panel.key(TOUCH_BUTTON, true));
      await send(panel.touch(x, y));
      await send(panel.key(TOUCH_BUTTON, false));
      return `Touchpad bei ${x}, ${y} berührt`;
    },
    async hold(name, down = true) {
      await send(panel.key(named(buttons, name, "Taste"), down));
      return `${name} ${down ? "gedrückt" : "losgelassen"}`;
    },
    async testMode(on = true) {
      const s = await withFirmware();
      if (remoteInfo(s.firmwareBytes)?.testMode == null) throw new Error("Den Test-Modus gibt es ab BLECHTRIBE 1.3.8.");
      await remote(command(TEST, 0, on ? 1 : 0));
      return on ? "Test-Modus an: das Gerät sieht aus wie aus" : "Test-Modus aus";
    },
    ram: { read: readRam, ...ram },
    fx: { mfx: n => slotName("mfx", n), ifx: n => slotName("ifx", n) },
  };
}
