/**
 * The device panel: connect over Web MIDI, show what the device said, and
 * why it may only be read when that is the case.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { DeviceSession, electribePorts, newCarry } from "../../src/session.mjs";

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

export function devicePanel(root, { onSession, emulator = () => null, probe, view = () => null }) {
  let session = null;
  // What went wrong survives a reconnect: one carry per port name.
  const carries = new Map();
  const status = el("div", { className: "cee-device-status ui-sr-only", role: "status" });
  const decide = el("div", { className: "cee-decide", id: "cee-decide", role: "alert", hidden: true });
  const facts = el("dl", { className: "cee-facts" });
  const choose = el("div", { className: "ui-field", hidden: true });
  const button = el("button", { type: "button", className: "btn cee-primary", id: "cee-connect", textContent: "Mit Electribe verbinden" });
  const emuButton = el("button", { type: "button", className: "btn", id: "cee-connect-emu", textContent: "Mit Emulator verbinden", hidden: true });
  const rehearseState = el("p", { className: "ui-sr-only", id: "cee-rehearse-state", "aria-live": "polite" });
  const ledNote = el("p", { className: "ui-sr-only", id: "cee-led-note", "aria-live": "polite" });
  const log = el("ul", { className: "ui-list cee-log" });
  const say = (tone, word, text) => {
    status.hidden = false;
    // Only screen readers read the line; on the page it is the toast, nothing stands above the device.
    status.replaceChildren(pill(tone, word), el("span", { textContent: ` ${text}` }));
    toast(text, tone === "error" ? "error" : tone === "ok" ? "ok" : "info", { stay: tone === "warn" });
  };
  const clear = () => { status.hidden = true; status.replaceChildren(); };

  function fact(term, value) {
    facts.append(el("dt", { textContent: term }), el("dd", {}, value));
  }

  function showDevice(d) {
    facts.replaceChildren();
    fact("Globaler Kanal", String(d.channel + 1));
    fact("Gerätesuche, Byte 10 und 11", `${d.version[0]}.${d.version[1]}`);
    fact("Stand", d.versionKnown ? pill("ok", "bekannt") : pill("warn", "unbekannt, nur lesen"));
    fact("RAM über MIDI", d.ram === "blech" ? pill("ok", `BLECHTRIBE, Blöcke bis ${d.blech.maxBlock} Byte`) : d.ram === "hacktribe" ? pill("ok", "Hacktribe") : pill("error", "antwortet nicht"));
    if (d.sampler && !d.ram) {
      say("warn", "eingeschränkt", "Auf der Electribe ist weder BLECHTRIBE noch Hacktribe. Patterns und Einstellungen gehen. Für alles andere brauchst du BLECHTRIBE: links auf Firmware Patcher.");
    } else if (!d.versionKnown) {
      say("warn", "nur lesen", "Diese Firmware-Version kennt die App noch nicht genau. Deshalb ändert sie nichts am Gerät, du kannst nur lesen.");
    } else if (d.build === "stock") {
      say("ok", "verbunden", "Korgs Original mit BLECHTRIBE. Alles geht, nur die Effekt-Presets nicht.");
    } else if (!d.ram) {
      say("warn", "eingeschränkt", "Ohne BLECHTRIBE gehen nur Patterns und Einstellungen. Für alles andere: links auf Firmware Patcher.");
    } else {
      say("ok", "verbunden", "Bereit.");
    }
  }

  function showDecision() {
    const p = session?.pending;
    if (!session?.blocked) { decide.hidden = true; decide.replaceChildren(); return; }
    const restore = el("button", { type: "button", className: "btn cee-primary", id: "cee-decide-restore", textContent: "Sicherung zurückspielen", disabled: !p });
    const keep = el("button", { type: "button", className: "btn", id: "cee-decide-keep", textContent: "So lassen" });
    const act = async choice => {
      restore.disabled = keep.disabled = true;
      try {
        const res = await session.resolve(choice);
        toast(res.ok ? (choice === "restore" ? "Sicherung zurückgespielt." : "Entschieden: so gelassen.") : `Das hat nicht geklappt: ${res.error.message}`, res.ok ? "ok" : "error");
      } catch (e) { toast(e.message, "error"); }
      restore.disabled = keep.disabled = false;
      if (!session.blocked) setTimeout(showDecision, 0);
    };
    restore.addEventListener("click", () => act("restore"));
    keep.addEventListener("click", () => act("keep"));
    decide.replaceChildren(
      el("h3", { textContent: "Entscheidung nötig" }),
      el("p", { className: "ui-break", textContent: session.blocked }),
      p?.now ? el("p", {}, [pill("warn", "zurückgelesen"), ` ${p.now.text}`]) : null,
      el("div", { className: "actions" }, [restore, keep]),
    );
    decide.hidden = false;
  }

  /** For a real device: an emulator session that tries every edit first (plan 5.1, 5.2). */
  async function attachRehearsal() {
    if (!session) return;
    const emu = emulator();
    if (session.port === emu) { rehearseState.textContent = ""; return; }
    session.requireRehearsal = true;
    if (!emu?.running) {
      session.rehearseOn(null);
      rehearseState.textContent = "Probe im Emulator: Emulator läuft nicht. Starte ihn im Bereich Emulator, dann neu verbinden; bis dahin geht nichts ans Gerät.";
      toast(rehearseState.textContent, "info", { stay: true });
      return;
    }
    try {
      // Its own history: device undo takes back the probe's last edit, never one made on the emulator directly.
      // The terminal rehearses on the same session, so the two never take the port from each other.
      const tries = await probe();
      tries.history.length = 0;
      session.rehearseOn(tries);
      rehearseState.textContent = "Probe im Emulator: an. Jede Änderung läuft erst dort; nur wenn sie zurückgelesen stimmt und die Firmware weiterläuft, geht sie ans Gerät.";
    } catch (e) {
      session.rehearseOn(null);
      rehearseState.textContent = `Probe im Emulator: nicht möglich (${e.message}). Nichts geht ans Gerät.`;
      toast(rehearseState.textContent, "error");
    }
  }

  async function connectPort(port) {
    if (session && session.port !== emulator()) session.lost();
    try {
      if (port === emulator()) {
        session = await probe();
        showDevice(session.device);
      } else {
        if (!carries.has(port.name)) carries.set(port.name, newCarry());
        session = new DeviceSession({ port, carry: carries.get(port.name) });
        showDevice(await session.connect());
      }
      await attachRehearsal();
      showDecision();
      view()?.external(port !== emulator());
      onSession(session);
    } catch (e) {
      view()?.external(false);
      say("error", "keine Antwort", `Die Electribe antwortet nicht. Ist sie eingeschaltet und per USB angesteckt? Dann nochmal verbinden. (${e.message})`);
      session = null;
      onSession(null);
    }
  }

  async function connect() {
    if (!navigator.requestMIDIAccess) {
      // The desktop app runs in the system's WebKit (Apple's on the Mac, WebKitGTK on Linux): neither has Web MIDI.
      say("error", "nicht möglich", window.__GELUMPE_APP
        ? "Die App kann noch nicht mit der echten Electribe reden, ihr fehlt Web MIDI. Nimm dafür Chrome oder Edge am Rechner."
        : "Dieser Browser kann nicht mit der Electribe reden. Nimm die App oder Chrome oder Edge am Rechner. Safari geht nicht.");
      return;
    }
    let access;
    try {
      window.ui?.busy(button, true);
      access = await navigator.requestMIDIAccess({ sysex: true });
    } catch {
      say("error", "verweigert", "Der Zugriff auf MIDI wurde abgelehnt. Ohne ihn erreicht die App die Electribe nicht. Lade die Seite neu und klick bei der Frage auf Erlauben.");
      return;
    } finally {
      window.ui?.busy(button, false);
    }
    access.onstatechange = e => {
      if (session && e.port.state === "disconnected" && (e.port === session.port.out || e.port === session.port.in)) {
        session.lost();
        view()?.external(false);
        say("error", "getrennt", "Die Electribe wurde abgesteckt. Steck sie wieder an und verbinde neu. Was gerade übertragen wurde, ist vielleicht nicht ganz angekommen.");
      }
    };
    const ports = electribePorts(access);
    if (!ports.length) {
      say("warn", "nicht gefunden", "Keine Electribe gefunden. Steck sie per USB an und schalte sie ein.");
      return;
    }
    if (ports.length > 1) {
      const select = el("select", { className: "select", id: "cee-port" });
      ports.forEach((p, i) => select.append(el("option", { value: String(i), textContent: p.name })));
      select.addEventListener("change", () => connectPort(ports[Number(select.value)]));
      choose.replaceChildren(el("label", { className: "ui-field-label", htmlFor: "cee-port", textContent: "Mehrere Electribes gefunden, welche?" }), select);
      choose.hidden = false;
    }
    await connectPort(ports[0]);
  }

  /** Plan 5.3: the display image read from RAM (data/map/screen.mjs), drawn into the emulator's Electribe drawing while a real device is attached. */
  let mirroring = false;
  async function showDisplay() {
    const s = session;
    if (!s || s.port === emulator() || !s.device?.ram || s.busy || s.reserved || document.hidden || mirroring) return;
    mirroring = true;
    try { view()?.drawBytes(await s.readDisplay()); } catch {} finally { mirroring = false; }
  }
  setInterval(showDisplay, 1000);

  /** The LEDs from the firmware's own table in RAM (src/leds.mjs), four times a second. After three reads in a row that fail the page stops asking and says so. */
  let lighting = false, ledFails = 0, ledsOffFor = null;
  async function showLeds() {
    const s = session;
    if (ledsOffFor && s !== ledsOffFor) { ledsOffFor = null; ledNote.textContent = ""; }
    if (!s || s.port === emulator() || !s.device?.ram || s.busy || s.reserved || document.hidden || lighting || s === ledsOffFor) return;
    lighting = true;
    try {
      view()?.drawLeds(await s.readLeds());
      ledFails = 0;
    } catch (e) {
      if (++ledFails === 3) {
        ledsOffFor = s;
        ledNote.textContent = `LEDs: nicht lesbar, die Anzeige bleibt dunkel. ${e.message}`;
        toast(ledNote.textContent, "error");
      }
    } finally { lighting = false; }
  }
  setInterval(showLeds, 250);

  /** Whether an Electribe is plugged in, asked every few seconds; only once the browser has granted MIDI, so it never prompts. */
  let seen = false;
  async function detect() {
    if (session || document.hidden || !navigator.requestMIDIAccess || !navigator.permissions) return;
    try {
      if ((await navigator.permissions.query({ name: "midi", sysex: true })).state !== "granted") return;
      const found = electribePorts(await navigator.requestMIDIAccess({ sysex: true })).length > 0;
      if (found === seen || session) return;
      seen = found;
      if (found) say("neutral", "erkannt", "Eine Electribe ist angesteckt. Klick auf „Mit Electribe verbinden“.");
      else clear();
    } catch {}
  }
  setInterval(detect, 4000);

  button.addEventListener("click", connect);
  emuButton.addEventListener("click", () => {
    const port = emulator();
    if (!port?.running) {
      say("warn", "Emulator läuft nicht", "Starte zuerst links den Emulator, dann hier verbinden.");
      return;
    }
    port.ondisconnect = () => {
      if (session?.port !== port) return;
      session.lost();
      say("error", "getrennt", "Der Emulator läuft nicht mehr. Sobald er wieder läuft, verbindet sich das hier von selbst. Was gerade übertragen wurde, ist vielleicht nicht ganz angekommen.");
      // Once the emulator runs again, the same port connects again, unless another connection came in between.
      const lost = session;
      const back = setInterval(() => {
        if (session !== lost) clearInterval(back);
        else if (port.running) { clearInterval(back); connectPort(port); }
      }, 1000);
    };
    connectPort(port);
  });
  clear();
  root.replaceChildren(
    el("div", { className: "actions" }, [button, emuButton]),
    rehearseState,
    ledNote,
    choose,
    status,
    decide,
    el("div", { hidden: true }, [facts, log]),
  );

  return {
    get session() { return session; },
    /** The same as the button in this area: connect to the running emulator. */
    connectEmulator: () => emuButton.click(),
    showDecision,
    log(text, tone = "neutral") {
      log.prepend(el("li", { className: "ui-row" }, [pill(tone, { ok: "ok", warn: "Warnung", error: "Fehler", neutral: "Info" }[tone]), el("span", { textContent: ` ${text}` })]));
    },
  };
}
