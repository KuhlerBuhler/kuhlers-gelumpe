const ELECTRIBE = /electribe/i;

/** The browser transport and the desktop's native MIDI commands share the same port shape. */
export function createMidiTransport(scope = globalThis, { sendTimeout = bytes => 3000 + bytes * 0.4 } = {}) {
  const native = scope.__GELUMPE_APP?.nativeMidi === true;
  const active = new Set();
  const api = () => {
    const core = scope.__TAURI__?.core;
    if (!core?.invoke || !core.Channel) throw new Error("Die native MIDI-Schnittstelle ist nicht verfügbar.");
    return {
      Channel: core.Channel,
      async invoke(command, args) {
        try { return await core.invoke(command, args); }
        catch (reason) {
          if (reason instanceof Error) throw reason;
          const error = new Error(reason?.message ?? String(reason));
          if (reason?.code) error.code = reason.code;
          throw error;
        }
      },
    };
  };
  const closePort = async (port, { refresh = true } = {}) => {
    if (!native) {
      active.delete(port);
      if (port?.in) port.in.onmidimessage = null;
      await Promise.all([port?.in?.close?.(), port?.out?.close?.()]);
      return;
    }
    const entry = port?.out?._native;
    if (!entry) return;
    if (entry.closed) {
      if (entry.closingPending) return entry.closing;
      const result = await entry.closing;
      if (!refresh || result?.state !== "quarantined") return result;
      if (entry.closingPending) return entry.closing;
    }
    entry.closed = true;
    active.delete(port);
    port.in.onmidimessage = null;
    port.in.state = port.out.state = "disconnected";
    entry.closingPending = true;
    entry.closing = (entry.sessionId ? api().invoke("midi_close", { sessionId: entry.sessionId }) : Promise.resolve({ state: "closed" }))
      .finally(() => { entry.closingPending = false; });
    return entry.closing;
  };
  const disconnect = async (port, error) => {
    let result;
    try { result = await closePort(port); } catch {}
    const quarantined = result?.state === "quarantined";
    const message = error?.message ?? (typeof error === "string" ? error : "Die MIDI-Verbindung wurde getrennt.");
    port.out._native.access.onstatechange?.({
      port: port.out, code: error?.code, quarantined,
      message: quarantined ? `${message} Der MIDI-Port wird noch freigegeben. Warte kurz, bevor du neu verbindest.` : message,
    });
  };
  return {
    native,
    get supported() { return native || !!scope.navigator?.requestMIDIAccess; },
    async requestAccess() {
      if (!native) return scope.navigator.requestMIDIAccess({ sysex: true });
      const ports = await api().invoke("midi_list");
      const access = { inputs: new Map(), outputs: new Map(), onstatechange: null };
      for (const output of ports.outputs.filter(port => ELECTRIBE.test(port.name))) {
        const inputs = ports.inputs.filter(port => port.name === output.name);
        if (inputs.length > 1 || ports.outputs.filter(port => port.name === output.name).length > 1) {
          throw new Error(`Die MIDI-Ports für „${output.name}“ sind nicht eindeutig. Trenne weitere gleich benannte Geräte und verbinde neu.`);
        }
        if (!inputs.length) continue;
        const entry = { inputId: inputs[0].id, outputId: output.id, access, sessionId: null, closed: true };
        access.inputs.set(inputs[0].id, { id: inputs[0].id, name: output.name, state: "connected", onmidimessage: null });
        access.outputs.set(output.id, { id: output.id, name: output.name, state: "connected", _native: entry });
      }
      return access;
    },
    async openPort(port) {
      if (!native) {
        try { await Promise.all([port.in?.open?.(), port.out.open?.()]); }
        catch (error) { await closePort(port); throw error; }
        active.add(port);
        return port;
      }
      const entry = port.out._native;
      if (!entry || !entry.closed) throw new Error("Der MIDI-Port ist bereits geöffnet oder ungültig.");
      entry.sessionId = null;
      entry.closing = null;
      const { invoke, Channel } = api();
      const events = new Channel();
      const early = [];
      let opening = true;
      const current = event => !entry.closed && event.sessionId === entry.sessionId;
      const failActive = async (event, error) => {
        if (current(event)) await disconnect(port, error);
      };
      const consume = async event => {
        try {
          if (!current(event)) return;
          if (event.type === "message") {
            const bytes = await invoke("midi_read", { sessionId: event.sessionId, sequence: event.sequence });
            if (current(event)) port.in.onmidimessage?.({ data: Uint8Array.from(bytes) });
          } else if (event.type === "disconnected" || event.type === "error") {
            await disconnect(port, event);
          }
        } catch (error) { await failActive(event, error); }
        finally {
          if (event.type === "message") {
            try { await invoke("midi_ack", { sessionId: event.sessionId, sequence: event.sequence }); }
            catch (error) { await failActive(event, error); }
          }
        }
      };
      let delivery = Promise.resolve();
      const enqueue = event => {
        if (event.type !== "message") return consume(event);
        delivery = delivery.then(() => consume(event));
        return delivery;
      };
      events.onmessage = event => opening ? early.push(event) : enqueue(event);
      let opened;
      try { opened = await invoke("midi_open", { inputId: entry.inputId, outputId: entry.outputId, events }); }
      catch (error) { opening = false; early.forEach(enqueue); await delivery; throw error; }
      entry.sessionId = opened.sessionId;
      entry.closed = false;
      port.in.state = port.out.state = "connected";
      active.add(port);
      port.out.send = async bytes => {
        if (entry.closed) throw new Error("Die MIDI-Verbindung ist getrennt. Bitte neu verbinden.");
        let timer;
        try {
          await Promise.race([
            invoke("midi_send", { sessionId: entry.sessionId, bytes: Array.from(bytes) }),
            new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("Das Senden über MIDI dauert zu lange. Bitte neu verbinden.")), sendTimeout(bytes.length)); }),
          ]);
        } catch (error) {
          await disconnect(port, error);
          throw error;
        } finally { clearTimeout(timer); }
      };
      opening = false;
      early.forEach(enqueue);
      await delivery;
      if (entry.closed) throw new Error("Die MIDI-Verbindung wurde beim Öffnen getrennt.");
      return port;
    },
    closePort,
    async dispose() { await Promise.all([...active].map(port => closePort(port))); },
  };
}
