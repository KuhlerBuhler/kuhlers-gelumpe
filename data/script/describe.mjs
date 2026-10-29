/**
 * One short German sentence for every API entry, event and event value of the script contract, for the
 * editor's completions, parameter hint and hover. Nothing here reaches a block; test/script-describe.test.mjs
 * fails when the contract has an entry without a text here.
 */
import { text } from "../../src/text.mjs";

export const API_DOCS = Object.freeze({
  "korg.led": text("api.korg.led"),
  "korg.millis": text("api.korg.millis"),
  "korg.display.clear": text("api.korg.display.clear"),
  "korg.display.text": text("api.korg.display.text"),
  "korg.display.number": text("api.korg.display.number"),
  "korg.display.pixel": text("api.korg.display.pixel"),
  "korg.display.rect": text("api.korg.display.rect"),
  "korg.display.clearRect": text("api.korg.display.clearRect"),
  "korg.display.bitmap": text("api.korg.display.bitmap"),
  "korg.display.textNumber": text("api.korg.display.textNumber"),
  "korg.display.take": text("api.korg.display.take"),
  "korg.display.release": text("api.korg.display.release"),
  "korg.store.get": text("api.korg.store.get"),
  "korg.store.set": text("api.korg.store.set"),
  "korg.store.save": text("api.korg.store.save"),
  "korg.read.transport": text("api.korg.read.transport"),
  "korg.read.tempo": text("api.korg.read.tempo"),
  "korg.read.pattern": text("api.korg.read.pattern"),
  "korg.read.part": text("api.korg.read.part"),
  "korg.read.step": text("api.korg.read.step"),
  "korg.read.mute": text("api.korg.read.mute"),
  "korg.read.knob": text("api.korg.read.knob"),
  "korg.read.chainMode": text("api.korg.read.chainMode"),
  "korg.read.patternValue": text("api.korg.read.patternValue"),
  "korg.remapKey": text("api.korg.remapKey"),
  "korg.play": text("api.korg.play"),
  "korg.stop": text("api.korg.stop"),
  "korg.pattern": text("api.korg.pattern"),
  "korg.tempo": text("api.korg.tempo"),
  "korg.part": text("api.korg.part"),
  "korg.mute": text("api.korg.mute"),
  "korg.seq.setStep": text("api.korg.seq.setStep"),
  "korg.seq.setGate": text("api.korg.seq.setGate"),
  "korg.seq.clearPart": text("api.korg.seq.clearPart"),
  "korg.backlight": text("api.korg.backlight"),
  "korg.ledHold": text("api.korg.ledHold"),
  "korg.menu.add": text("api.korg.menu.add"),
  "korg.app": text("api.korg.app"),
  "korg.file.frame": text("api.korg.file.frame"),
  "korg.get": text("api.korg.get"),
  "korg.set": text("api.korg.set"),
  "korg.after": text("api.korg.after"),
  "korg.every": text("api.korg.every"),
  "korg.afterSteps": text("api.korg.afterSteps"),
  "korg.cancel": text("api.korg.cancel"),
});

/** korg.onEvent is no API entry, the compiler reads it as a statement. */
export const ON_EVENT_DOC = Object.freeze({
  name: "korg.onEvent",
  signature: "korg.onEvent(\"ereignis\", handler)",
  text: text("api.onEvent"),
});

export const EVENT_DOCS = Object.freeze({
  start: { text: text("api.event.start"), args: {} },
  ready: { text: text("api.event.ready"), args: {} },
  frame: { text: text("api.event.frame"), args: {} },
  buttonPress: { text: text("api.event.buttonPress"), args: { key: text("api.event.buttonPress.key") } },
  buttonRelease: { text: text("api.event.buttonRelease"), args: { key: text("api.event.buttonRelease.key") } },
  knob: { text: text("api.event.knob"), args: { index: text("api.event.knob.index"), value: text("api.event.knob.value") } },
  encoder: { text: text("api.event.encoder"), args: { index: text("api.event.encoder.index"), delta: text("api.event.encoder.delta") } },
  pad: { text: text("api.event.pad"), args: { index: text("api.event.pad.index"), down: text("api.event.pad.down"), velocity: text("api.event.pad.velocity") } },
  touch: { text: text("api.event.touch"), args: { x: text("api.event.touch.x"), y: text("api.event.touch.y"), first: text("api.event.touch.first") } },
  step: { text: text("api.event.step"), args: { step: text("api.event.step.step") } },
  beat: { text: text("api.event.beat"), args: {} },
  play: { text: text("api.event.play"), args: {} },
  stop: { text: text("api.event.stop"), args: {} },
  rec: { text: text("api.event.rec"), args: {} },
  patternChange: { text: text("api.event.patternChange"), args: { index: text("api.event.patternChange.index") } },
  partChange: { text: text("api.event.partChange"), args: { part: text("api.event.partChange.part") } },
  mute: { text: text("api.event.mute"), args: { part: text("api.event.mute.part"), muted: text("api.event.mute.muted") } },
  tempo: { text: text("api.event.tempo"), args: { tenthsBpm: text("api.event.tempo.tenthsBpm") } },
  save: { text: text("api.event.save"), args: {} },
  menu: { text: text("api.event.menu"), args: { id: text("api.event.menu.id"), value: text("api.event.menu.value") } },
  open: { text: text("api.event.open"), args: {} },
  timer: { text: text("api.event.timer"), args: { callback: text("api.event.timer.callback") } },
  close: { text: text("api.event.close"), args: {} },
});

export const GROUP_DOCS = Object.freeze({
  GAMES: text("api.group.games"),
  TOOLS: text("api.group.tools"),
});

/** The two name families, for the completion entries that lead into them. */
export const NAME_FAMILY_DOCS = Object.freeze({
  key: text("api.names.key"),
  led: text("api.names.led"),
});
