/**
 * The device panel: connect over MIDI, show what the device said, and
 * why it may only be read when that is the case.
 */
import { el } from "./fields.mjs";
import { toast } from "./toast.mjs";
import { createMidiTransport } from "./midi.mjs";
import { DeviceSession, electribePorts, newCarry } from "../../src/session.mjs";
import { t } from "./i18n.mjs";

const pill = (tone, word) => {
  const p = el("span", { className: "cee-status", textContent: word });
  p.dataset.tone = tone;
  return p;
};

export function devicePanel(root, { onSession, emulator = () => null, probe, view = () => null }) {
  let session = null;
  const midi = createMidiTransport(window);
  let connection = 0;
  window.addEventListener("pagehide", () => { connection++; session?.lost(); midi.dispose().catch(() => {}); });
  // What went wrong survives a reconnect: one carry per port name.
  const carries = new Map();
  const status = el("div", { className: "cee-device-status ui-sr-only", role: "status" });
  const decide = el("div", { className: "cee-decide", id: "cee-decide", role: "alert", hidden: true });
  const facts = el("dl", { className: "cee-facts" });
  const choose = el("div", { className: "ui-field", hidden: true });
  const button = el("button", { type: "button", className: "btn cee-primary", id: "cee-connect", textContent: t("device.connect") });
  const emuButton = el("button", { type: "button", className: "btn", id: "cee-connect-emu", textContent: t("device.connectEmu"), hidden: true });
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
    fact(t("device.fact.channel"), String(d.channel + 1));
    fact(t("device.fact.version"), `${d.version[0]}.${d.version[1]}`);
    fact(t("device.fact.state"), d.versionKnown ? pill("ok", t("device.fact.known")) : pill("warn", t("device.fact.unknown")));
    fact(t("device.fact.ram"), d.ram === "blech" ? pill("ok", t("device.fact.ram.blech", { max: d.blech.maxBlock })) : d.ram === "hacktribe" ? pill("ok", t("device.fact.ram.hacktribe")) : pill("error", t("device.fact.ram.none")));
    if (d.sampler && !d.ram) {
      say("warn", t("device.state.limited"), t("device.say.noPatch"));
    } else if (!d.versionKnown) {
      say("warn", t("device.state.readOnly"), t("device.say.unknownVersion"));
    } else if (d.build === "stock") {
      say("ok", t("device.state.connected"), t("device.say.stock"));
    } else if (!d.ram) {
      say("warn", t("device.state.limited"), t("device.say.noRam"));
    } else {
      say("ok", t("device.state.connected"), t("device.say.ready"));
    }
  }

  function showDecision() {
    const p = session?.pending;
    if (!session?.blocked) { decide.hidden = true; decide.replaceChildren(); return; }
    const restore = el("button", { type: "button", className: "btn cee-primary", id: "cee-decide-restore", textContent: t("device.decide.restore"), disabled: !p });
    const keep = el("button", { type: "button", className: "btn", id: "cee-decide-keep", textContent: t("device.decide.keep") });
    const act = async choice => {
      restore.disabled = keep.disabled = true;
      try {
        const res = await session.resolve(choice);
        toast(res.ok ? (choice === "restore" ? t("device.decide.restored") : t("device.decide.kept")) : t("device.decide.failed", { error: res.error.message }), res.ok ? "ok" : "error");
      } catch (e) { toast(e.message, "error"); }
      restore.disabled = keep.disabled = false;
      if (!session.blocked) setTimeout(showDecision, 0);
    };
    restore.addEventListener("click", () => act("restore"));
    keep.addEventListener("click", () => act("keep"));
    decide.replaceChildren(
      el("h3", { textContent: t("device.decide.title") }),
      el("p", { className: "ui-break", textContent: session.blocked }),
      p?.now ? el("p", {}, [pill("warn", t("device.decide.readBack")), ` ${p.now.text}`]) : null,
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
      rehearseState.textContent = t("device.rehearse.off");
      toast(rehearseState.textContent, "info", { stay: true });
      return;
    }
    try {
      // Its own history: device undo takes back the probe's last edit, never one made on the emulator directly.
      // The terminal rehearses on the same session, so the two never take the port from each other.
      const tries = await probe();
      tries.history.length = 0;
      session.rehearseOn(tries);
      rehearseState.textContent = t("device.rehearse.on");
    } catch (e) {
      session.rehearseOn(null);
      rehearseState.textContent = t("device.rehearse.failed", { error: e.message });
      toast(rehearseState.textContent, "error");
    }
  }

  async function connectPort(port) {
    const attempt = ++connection;
    const previous = session;
    session = null;
    if (previous && previous.port !== emulator()) previous.lost();
    let candidate;
    try {
      if (previous && previous.port !== emulator()) {
        const closed = await midi.closePort(previous.port);
        if (closed?.state === "quarantined") throw new Error(t("midi.quarantinedShort"));
      }
      if (attempt !== connection) return;
      if (port === emulator()) {
        candidate = await probe();
      } else {
        await midi.openPort(port);
        if (attempt !== connection) { await midi.closePort(port); return; }
        if (!carries.has(port.name)) carries.set(port.name, newCarry());
        candidate = new DeviceSession({ port, carry: carries.get(port.name) });
        await candidate.connect();
      }
      if (attempt !== connection) { candidate.lost(); await midi.closePort(port); return; }
      session = candidate;
      showDevice(session.device);
      await attachRehearsal();
      if (attempt !== connection) return;
      showDecision();
      view()?.external(port !== emulator(), !!session.device?.ram);
      onSession(session);
    } catch (e) {
      candidate?.lost();
      const closed = port !== emulator() ? await midi.closePort(port, { refresh: false }).catch(() => null) : null;
      if (attempt !== connection) return;
      view()?.external(false);
      say("error", t("device.state.noAnswer"), closed?.state === "quarantined"
        ? t("device.noAnswer.quarantined", { error: e.message })
        : t("device.noAnswer", { error: e.message }));
      session = null;
      onSession(null);
    }
  }

  /** Ends the connection to a real device or to the emulator; always possible, also while a request is in flight. */
  async function disconnect() {
    connection++;
    const lost = session;
    if (!lost) return false;
    session = null;
    const real = lost.port !== emulator();
    let closed = null;
    if (real) {
      lost.lost();
      closed = await midi.closePort(lost.port, { refresh: false }).catch(() => null);
    }
    view()?.external(false);
    rehearseState.textContent = "";
    decide.hidden = true;
    decide.replaceChildren();
    facts.replaceChildren();
    seen = false;
    onSession(null);
    say("neutral", t("device.state.disconnected"), closed?.state === "quarantined"
      ? t("device.disconnected.quarantined")
      : real ? t("device.disconnected") : t("device.disconnected.emu"));
    return true;
  }

  async function connect() {
    if (!midi.supported) {
      say("error", t("device.state.impossible"), t("device.noMidi"));
      return;
    }
    let access;
    try {
      window.ui?.busy(button, true);
      access = await midi.requestAccess();
    } catch (e) {
      say("error", t("device.state.impossible"), midi.native
        ? t("device.midiFailed", { error: e.message ?? e })
        : t("device.midiDenied"));
      return;
    } finally {
      window.ui?.busy(button, false);
    }
    access.onstatechange = e => {
      if (session && e.port.state === "disconnected" && (e.port === session.port.out || e.port === session.port.in)) {
        const lost = session;
        connection++;
        lost.lost();
        midi.closePort(lost.port, { refresh: false }).catch(() => {});
        onSession(lost);
        view()?.external(false);
        say("error", t("device.state.disconnected"), t(e.quarantined ? "device.unplugged.quarantined" : "device.unplugged", { detail: e.message ? ` (${e.message})` : "" }));
      }
    };
    const ports = electribePorts(access);
    choose.hidden = true;
    choose.replaceChildren();
    if (!ports.length) {
      say("warn", t("device.state.notFound"), t("device.notFound"));
      return;
    }
    if (ports.length > 1) {
      const select = el("select", { className: "select", id: "cee-port" });
      select.append(el("option", { value: "", textContent: t("device.pick"), disabled: true, selected: true }));
      ports.forEach((p, i) => select.append(el("option", { value: String(i), textContent: p.name })));
      select.addEventListener("change", () => connectPort(ports[Number(select.value)]));
      choose.replaceChildren(el("label", { className: "ui-field-label", htmlFor: "cee-port", textContent: t("device.several") }), select);
      choose.hidden = false;
      return;
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
        ledNote.textContent = t("device.ledsFailed", { error: e.message });
        toast(ledNote.textContent, "error");
      }
    } finally { lighting = false; }
  }
  setInterval(showLeds, 250);

  /** Detection lists ports without opening them; browser permission is never requested here. */
  let seen = false;
  async function detect() {
    if (session || document.hidden || !midi.supported || (!midi.native && !navigator.permissions)) return;
    try {
      if (!midi.native && (await navigator.permissions.query({ name: "midi", sysex: true })).state !== "granted") return;
      const found = electribePorts(await midi.requestAccess()).length > 0;
      if (found === seen || session) return;
      seen = found;
      if (found) say("neutral", t("device.state.found"), t("device.found"));
      else clear();
    } catch {}
  }
  setInterval(detect, 4000);

  button.addEventListener("click", connect);
  emuButton.addEventListener("click", () => {
    const port = emulator();
    if (!port?.running) {
      say("warn", t("device.state.emuOff"), t("device.emuOff"));
      return;
    }
    port.ondisconnect = () => {
      if (session?.port !== port) return;
      session.lost();
      say("error", t("device.state.disconnected"), t("device.emuGone"));
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
    disconnect,
    showDecision,
    log(text, tone = "neutral") {
      log.prepend(el("li", { className: "ui-row" }, [pill(tone, t({ ok: "device.log.ok", warn: "device.log.warn", error: "common.error", neutral: "device.log.info" }[tone])), el("span", { textContent: ` ${text}` })]));
    },
  };
}
