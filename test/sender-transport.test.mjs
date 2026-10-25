import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Sender } from '../src/sender.mjs';
import { ackFor, search } from '../src/protocol.mjs';

const message = search();
const step = { msg: message, expect: { kind: 'ack' } };
const noReply = { msg: message, expect: { kind: 'none' } };
const reply = ackFor(0);
const flush = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  promise.catch(() => {});
  return { promise, resolve, reject };
}

function observe(promise) {
  const state = { settled: false };
  state.result = promise.then(value => { state.settled = true; return { value }; }, error => { state.settled = true; return { error }; });
  return state;
}

function setup(t, send) {
  t.mock.timers.enable({ apis: ['setTimeout', 'Date'] });
  return new Sender({ channel: 0, send, timeouts: { ack: 20, transport: 50, quiet: 10 } });
}

test('a synchronous port can answer inside send', async t => {
  const sender = setup(t, () => sender.receive(reply));
  assert.deepEqual(await sender.exchange(step), reply);
  assert.equal(sender.waiting, null);
});

test('an early device reply waits for successful asynchronous transport', async t => {
  const sent = deferred();
  const sender = setup(t, () => { sender.receive(reply); return sent.promise; });
  const exchange = observe(sender.exchange(step));
  await flush();
  assert.equal(exchange.settled, false);
  await assert.rejects(sender.exchange(step), error => error.kind === 'busy');
  sent.resolve();
  assert.deepEqual((await exchange.result).value, reply);
});

test('a device reply followed by transport rejection fails instead of confirming a write', async t => {
  const sent = deferred();
  const sender = setup(t, () => { sender.receive(reply); return sent.promise; });
  const exchange = observe(sender.exchange(step));
  sent.reject(new Error('native send failed'));
  const { error } = await exchange.result;
  assert.equal(error?.kind, 'send');
  assert.match(error.message, /native send failed/);
  assert.equal(sender.waiting, null);
  assert.equal(sender.unsynced, true);
});

test('a synchronous transport throw after a device reply still fails', async t => {
  const sender = setup(t, () => { sender.receive(reply); throw new Error('closed port'); });
  await assert.rejects(sender.exchange(step), error => error.kind === 'send');
});

test('the reply deadline starts after the transport completes', async t => {
  const sent = deferred();
  const sender = setup(t, () => sent.promise);
  const exchange = observe(sender.exchange(step));
  t.mock.timers.tick(30);
  await flush();
  assert.equal(exchange.settled, false);
  sent.resolve();
  await flush();
  t.mock.timers.tick(19);
  await flush();
  assert.equal(exchange.settled, false);
  sender.receive(reply);
  assert.deepEqual((await exchange.result).value, reply);
});

test('a missing reply still expires after a successful transport', async t => {
  const sender = setup(t, () => Promise.resolve());
  const exchange = observe(sender.exchange(step));
  await flush();
  t.mock.timers.tick(20);
  assert.equal((await exchange.result).error.kind, 'timeout');
  assert.equal(sender.unsynced, true);
});

for (const earlyReply of [false, true]) {
  test(`a stalled transport expires and blocks later exchanges${earlyReply ? ' even after a reply' : ''}`, async t => {
    let sends = 0;
    const sender = setup(t, () => {
      sends++;
      if (earlyReply) sender.receive(reply);
      return new Promise(() => {});
    });
    const exchange = observe(sender.exchange(step));
    t.mock.timers.tick(100);
    await flush();
    assert.equal(exchange.settled, true);
    assert.equal((await exchange.result).error?.kind, 'send-timeout');
    await assert.rejects(sender.exchange(step), error => error.kind === 'disconnected');
    assert.equal(sends, 1);
  });
}

test('steps without a reply await the transport and preserve order', async t => {
  const sent = deferred();
  let sends = 0;
  const sender = setup(t, () => { sends++; return sends === 1 ? sent.promise : undefined; });
  const run = observe(sender.run([noReply, noReply]));
  await flush();
  assert.equal(run.settled, false);
  assert.equal(sends, 1);
  sent.resolve();
  assert.equal((await run.result).value.ok, true);
  assert.equal(sends, 2);
});

test('a rejected no-reply send fails the run at its own step', async t => {
  const sent = deferred();
  const sender = setup(t, () => sent.promise);
  const run = sender.run([noReply, noReply]);
  sent.reject(new Error('no output'));
  const result = await run;
  assert.equal(result.ok, false);
  assert.equal(result.failedAt, 0);
  assert.equal(result.error.kind, 'send');
});

for (const expectReply of [true, false]) {
  test(`disconnect immediately rejects a pending ${expectReply ? 'reply' : 'no-reply'} transport`, async t => {
    const sent = deferred();
    const sender = setup(t, () => sent.promise);
    const exchange = observe(sender.exchange(expectReply ? step : noReply));
    sender.disconnect();
    const { error } = await exchange.result;
    assert.equal(error?.kind, 'disconnected');
    assert.equal(sender.waiting, null);
    sent.reject(new Error('late native rejection'));
    await flush();
    t.mock.timers.tick(1000);
    assert.equal(sender.unsynced, false);
  });
}

test('a disconnected old send cannot finish or reject a new session exchange', async t => {
  const oldSend = deferred();
  const old = setup(t, () => oldSend.promise);
  const first = observe(old.exchange(step));
  old.disconnect();
  assert.equal((await first.result).error.kind, 'disconnected');
  const newSend = deferred();
  const next = new Sender({ channel: 0, send: () => newSend.promise, timeouts: { ack: 20, transport: 50 } });
  const second = observe(next.exchange(step));
  oldSend.reject(new Error('late old failure'));
  old.receive(reply);
  await flush();
  assert.equal(second.settled, false);
  newSend.resolve();
  next.receive(reply);
  assert.deepEqual((await second.result).value, reply);
});

test('quiet recovery reserves the sender and disconnect cancels its pending step', async t => {
  let sends = 0;
  const sender = setup(t, () => { sends++; });
  sender.unsynced = true;
  const exchange = observe(sender.exchange(step));
  const concurrent = observe(sender.exchange(step));
  await flush();
  assert.equal(concurrent.settled, true);
  assert.equal((await concurrent.result).error.kind, 'busy');
  sender.disconnect();
  await flush();
  assert.equal(exchange.settled, true);
  assert.equal((await exchange.result).error.kind, 'disconnected');
  t.mock.timers.tick(100);
  await flush();
  assert.equal(sends, 0);
});
