/**
 * Device failures on demand, for tests only. Never part of the page.
 *
 * Wraps the ports of the Web MIDI stand-in so the n-th reply is swallowed,
 * a read-back comes back altered, or the port disappears mid-send.
 */
export function withFaults(port, { swallow = [], corruptRead = [], delay = {}, unplugAfter = null } = {}) {
  let replies = 0;
  let sent = 0;
  const input = port.in;
  const realSend = port.out.send.bind(port.out);
  const wrapped = { in: { onmidimessage: null }, out: { name: port.out.name }, name: port.name };
  input.onmidimessage = e => {
    replies++;
    if (swallow.includes(replies)) return;
    let data = e.data;
    // Read replies carry 0x54, pattern dumps 0x40; both can come back altered.
    if (corruptRead.includes(replies) && (data[6] === 0x54 || data[6] === 0x40)) {
      data = Uint8Array.from(data);
      data[data.length - 2] ^= 0x01;
    }
    const late = delay[replies];
    if (late) setTimeout(() => wrapped.in.onmidimessage?.({ data }), late);
    else wrapped.in.onmidimessage?.({ data });
  };
  wrapped.out.send = msg => {
    sent++;
    if (unplugAfter !== null && sent > unplugAfter) { wrapped.unplugged?.(); return; }
    realSend(msg);
  };
  return wrapped;
}
