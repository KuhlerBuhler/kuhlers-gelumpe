/**
 * What of the Electribe 2 a plugin reaches: one row per control or state, with the calls, paths and events that read it,
 * set it and report it. tools/plugin-coverage.mjs writes the table "Coverage" of docs/plugins.md, .en.md and .fr.md from
 * it; test/plugin-coverage.test.mjs fails when a call, an event or a leaf of the object tree is in no row, or when a doc
 * does not show the current table. A name ending in `.*` stands for every name below it. A row with three empty lists is a
 * part of the device no plugin reaches yet.
 */
const row = (area, de, en, fr, read = [], write = [], events = []) =>
  Object.freeze({ area, label: Object.freeze({ de, en, fr }), read: Object.freeze(read), write: Object.freeze(write), events: Object.freeze(events) });

export const AREAS = Object.freeze({
  panel: Object.freeze({ de: "Bedienfeld", en: "Panel", fr: "Façade" }),
  seq: Object.freeze({ de: "Sequencer, Pattern, Part, Step", en: "Sequencer, pattern, part, step", fr: "Séquenceur, pattern, partie, pas" }),
  fx: Object.freeze({ de: "Effekte", en: "Effects", fr: "Effets" }),
  sound: Object.freeze({ de: "Klang, MIDI, Samples", en: "Sound, MIDI, samples", fr: "Son, MIDI, échantillons" }),
  system: Object.freeze({ de: "System und Einstellungen", en: "System and settings", fr: "Système et réglages" }),
  plugin: Object.freeze({ de: "Dienste für Plugins", en: "Services for plugins", fr: "Services pour les plugins" }),
});

export const COVERAGE = Object.freeze([
  row("panel", "Tasten (REC bis IFX ON)", "Keys (REC to IFX ON)", "Touches (REC à IFX ON)", [],
    ["korg.pressKey", "korg.keyDown", "korg.keyUp", "korg.remapKey", "korg.keyHold", "korg.keyMask", "korg.passKeys"], ["buttonPress", "buttonRelease"]),
  row("panel", "Regler", "Knobs", "Potentiomètres", ["korg.read.knob"], ["korg.knob", "korg.knobHold"], ["knob"]),
  row("panel", "Encoder", "Encoders", "Encodeurs", [], ["korg.encoder"], ["encoder"]),
  row("panel", "Pads", "Pads", "Pads", [], ["korg.padDown", "korg.padUp", "korg.padHold"], ["pad"]),
  row("panel", "Touchpad", "Touchpad", "Touchpad", [], ["korg.touch", "korg.touchLockX"], ["touch"]),
  row("panel", "Touchpad-Modus (Gate Arp, Touch Scale, Master FX, MFX 2)", "Touchpad mode (Gate Arp, Touch Scale, Master FX, MFX 2)",
    "Mode du touchpad (Gate Arp, Touch Scale, Master FX, MFX 2)", ["korg.touchpad.mode"], ["korg.touchpad.mode"], ["touchpadMode"]),
  row("panel", "Pad-Modus (TRIGGER, SEQUENCER, KEYBOARD und die anderen)", "Pad mode (TRIGGER, SEQUENCER, KEYBOARD and the others)",
    "Mode des pads (TRIGGER, SEQUENCER, KEYBOARD et les autres)", ["korg.pads.mode"], [], ["padMode"]),
  row("panel", "Takt auf den Pads (1 bis 4)", "Bar on the pads (1 to 4)", "Mesure sur les pads (1 à 4)", ["korg.pads.bar"]),
  row("panel", "LEDs", "LEDs", "LED", [], ["korg.led", "korg.ledHold"]),
  row("panel", "Display (eigenes Bild, Fenster der Firmware)", "Display (own picture, the firmware's windows)", "Écran (image propre, fenêtres du firmware)",
    ["korg.read.popups"], ["korg.display.*", "korg.file.frame"], ["open", "close"]),
  row("panel", "Displaylicht", "Display light", "Rétroéclairage", [], ["korg.backlight"]),
  row("panel", "Welcher Bildschirm oder welches Menü offen ist", "Which screen or menu is open", "Écran ou menu ouvert", ["korg.screen"], [], ["screen"]),
  row("seq", "Transport (PLAY, STOP, REC)", "Transport (PLAY, STOP, REC)", "Transport (PLAY, STOP, REC)", ["korg.read.transport"],
    ["korg.play", "korg.stop"], ["play", "stop", "rec"]),
  row("seq", "Tempo", "Tempo", "Tempo", ["korg.read.tempo"], ["korg.tempo"], ["tempo"]),
  row("seq", "Gewähltes, angezeigtes und nächstes Pattern", "Selected, viewed and next pattern", "Pattern choisi, affiché et suivant",
    ["korg.read.pattern", "korg.read.viewedPattern", "korg.read.nextPattern"], ["korg.pattern"], ["patternChange"]),
  row("seq", "Gewählter Part, Mute", "Selected part, mute", "Partie choisie, mute", ["korg.read.part", "korg.read.mute"], ["korg.part", "korg.mute"],
    ["partChange", "mute"]),
  row("seq", "Step-Zähler", "Step counter", "Compteur de pas", ["korg.read.step"], [], ["step", "beat"]),
  row("seq", "Werte des Patterns (Tempo bis MFX-Pad, Chain, Sync Group)", "Values of the pattern (tempo to MFX pad, chain, sync group)",
    "Valeurs du pattern (tempo au pad MFX, chaîne, sync group)", ["korg.read.patternValue", "korg.read.chainMode"], ["korg.seq.setPatternValue"]),
  row("seq", "Werte eines Parts (Sample bis Groove, mit Motion Seq an oder aus)", "Values of a part (sample to groove, with motion seq on or off)",
    "Valeurs d'une partie (échantillon à groove, avec motion seq on ou off)", ["korg.read.patternValue"], ["korg.seq.setPartValue"]),
  row("seq", "Steps (an, Gate, Velocity, Noten)", "Steps (on, gate, velocity, notes)", "Pas (on, gate, vélocité, notes)",
    ["korg.seq.getOn", "korg.seq.getGate", "korg.seq.getNote", "korg.seq.getVelocity", "korg.read.patternBytes"],
    ["korg.seq.setStep", "korg.seq.setGate", "korg.seq.clearPart", "korg.seq.writeSteps"]),
  row("seq", "Pattern speichern (WRITE)", "Saving the pattern (WRITE)", "Enregistrer le pattern (WRITE)", [], [], ["write"]),
  row("seq", "Name des Patterns", "Name of the pattern", "Nom du pattern", ["korg.read.patternName"]),
  row("seq", "Motion-Spuren und ihre Wiedergabe", "Motion lanes and their playback", "Pistes de motion et leur lecture",
    ["korg.motion.lane", "korg.motion.destination", "korg.motion.value", "korg.motion.output"],
    ["korg.motion.setValue", "korg.motion.clearLane", "korg.motion.clearPart", "korg.motion.clearMfx"]),
  row("seq", "Motion des gewählten Parts an oder aus (TAP mit dem Patch tap-motion)", "Motion of the selected part on or off (TAP with the patch tap-motion)",
    "Motion de la partie choisie on ou off (TAP avec le patch tap-motion)", ["korg.motion.enabled"], ["korg.motion.enabled"]),
  row("fx", "MFX: Typ, Pad, HOLD, MFX SEND", "MFX: type, pad, HOLD, MFX SEND", "MFX : type, pad, HOLD, MFX SEND", ["korg.read.patternValue"],
    ["korg.seq.setPatternValue", "korg.seq.setPartValue"]),
  row("fx", "MFX-2-Typ des Patterns", "MFX 2 type of the pattern", "Type MFX 2 du pattern", ["korg.read.patternValue"], ["korg.seq.setPatternValue"]),
  row("fx", "IFX: an, Typ, Edit", "IFX: on, type, edit", "IFX : on, type, edit", ["korg.read.patternValue"], ["korg.seq.setPartValue"]),
  row("sound", "Ausgangspegel, Spektrum, Wellenform", "Output level, spectrum, waveform", "Niveau de sortie, spectre, forme d'onde"),
  row("sound", "Eigene MIDI-Nachrichten senden, MIDI empfangen", "Sending own MIDI messages, receiving MIDI", "Envoyer ses propres messages MIDI, recevoir du MIDI"),
  row("sound", "Name und Daten eines Samples", "Name and data of a sample", "Nom et données d'un échantillon"),
  row("system", "Gerät, Version, Anzahl Effekte und Sample-Slots", "Device, version, number of effects and sample slots",
    "Appareil, version, nombre d'effets et de slots d'échantillon", ["korg.system.device", "korg.system.version", "korg.system.limits.*"]),
  row("system", "Reparaturen, Test-Modus, Auto Power Off", "Repairs, test mode, Auto Power Off", "Réparations, mode test, arrêt automatique",
    ["korg.system.repairs", "korg.system.testMode"], ["korg.system.keepAwake"]),
  row("system", "GLOBAL PARAMETERS", "GLOBAL PARAMETERS", "GLOBAL PARAMETERS", ["korg.global.*"], ["korg.global.*"]),
  row("system", "Menü BLECH (CUSTOMIZATION, FEATURES)", "Menu BLECH (CUSTOMIZATION, FEATURES)", "Menu BLECH (CUSTOMIZATION, FEATURES)",
    ["korg.menu.blech.*"], ["korg.menu.blech.*"]),
  row("system", "Netzteil oder Batterie, Ladestand", "Adapter or battery, charge", "Adaptateur ou batterie, charge"),
  row("plugin", "Eigene Einträge im Menü BLECH", "Own entries in the menu BLECH", "Entrées propres dans le menu BLECH", [], ["korg.menu.add"], ["menu"]),
  row("plugin", "Apps", "Apps", "Apps", [], ["korg.app"], ["open", "close"]),
  row("plugin", "Gespeicherte Werte", "Stored values", "Valeurs enregistrées", ["korg.store.get"], ["korg.store.set", "korg.store.save"], ["save"]),
  row("plugin", "Zeit und Timer", "Time and timers", "Temps et minuteurs", ["korg.millis"], ["korg.after", "korg.every", "korg.afterSteps", "korg.cancel"],
    ["ready", "frame"]),
]);

/**
 * Names that are in no row on purpose: korg.get and korg.set are the calls the compiler makes for a path of the object tree,
 * `start` is the body of the plugin and `timer` the event the runtime sends to the function of a timer.
 */
export const COVERAGE_OUTSIDE = Object.freeze(["korg.get", "korg.set", "start", "timer"]);
