/**
 * The global settings, a 256-byte dump of its own (GLOBAL DATA DUMP).
 * Offsets are relative to the start of the dump. Every menu page is measured
 * in measure:2026-10-14/global-felder.
 */
const MEASURED = "measure:2026-10-14/global-felder";
const l = (de, en = de) => ({ de, en });

const g = (id, label, offset, convert, range, rest = {}) => ({
  id: `global.${id}`, label, area: "global", where: { offset }, type: "u8",
  transport: ["global-sysex"], convert, range, source: "measured", evidence: MEASURED, ...rest,
});

/** A run of bytes no page of the menu reaches. */
const unknown = (id, label, offset, length, note) => ({
  id: `global.${id}`, label, area: "global", where: { offset }, type: `bytes:${length}`,
  transport: ["global-sysex"], convert: null, range: null, source: "unknown", edit: "expert", note,
});

export default {
  block: "global",
  size: 256,
  label: l("Global"),
  fields: [
    g("magic", l("Kennung"), 0, null, null, { type: "bytes:4", edit: "readonly" }),
    unknown("unknown04", l("Bytes 4 bis 15, unbekannt", "Bytes 4 to 15, unknown"), 4, 12,
      "kein Menü-Eintrag ändert sie; ein Byte darin ist belegt, Bedeutung offen"),
    g("metronome", l("Metronom", "Metronome"), 16, "metronome", [0, 4], { note: "Seite 9 METRONOME" }),
    g("syncPolarity", l("Sync-Polarität", "Sync polarity"), 17, "syncPolarity", [0, 1],
      { note: "Seite 7 SYNC POLARITY, das Display zeigt Hi und Lo; welches steigend ist, ist nicht gemessen" }),
    g("syncResolution", l("Sync-Auflösung", "Sync resolution"), 18, "syncResolution", [0, 1], { note: "Seite 8 SYNC UNIT" }),
    g("patternChangeLock", l("Pattern-Wechsel-Sperre", "Pattern change lock"), 19, "onOff", [0, 1],
      { note: "Seite 18 PTN. CHANGE LOCK" }),
    g("audioInThru", l("Audio In Thru"), 20, "onOff", [0, 1], { note: "Seite 14 AUDIO IN THRU" }),
    unknown("unknown21", l("Bytes 21 bis 26, unbekannt", "Bytes 21 to 26, unknown"), 21, 6,
      "kein Menü-Eintrag ändert sie; ein Byte darin ist belegt, Bedeutung offen"),
    g("velocityCurve", l("Velocity-Kurve", "Velocity curve"), 27, "velocityCurve", [0, 3], { note: "Seite 2 VELOCITY CURVE" }),
    g("knobMode", l("Reglermodus", "Knob mode"), 28, "knobMode", [0, 2], { note: "Seite 11 KNOB MODE" }),
    g("triggerMode", l("Trigger-Modus", "Trigger mode"), 29, "triggerMode", [0, 2], { note: "Seite 1 TRIGGER MODE" }),
    g("lcdContrast", l("Display-Kontrast", "LCD contrast"), 30, "contrast", [18, 42],
      { note: "Seite 13 LCD CONTRAST; das Display zeigt das Byte minus 17, also 1 bis 25" }),
    g("chainMode", l("Chain-Modus", "Chain mode"), 31, "onOff", [0, 1], { note: "Seite 19 CHAIN MODE" }),
    g("batteryMode", l("Batterietyp", "Battery type"), 32, "batteryMode", [0, 1], { note: "Seite 15 BATTERY TYPE" }),
    g("autoPowerOff", l("Automatisch aus", "Auto power off"), 33, "autoPowerOff", [0, 1],
      { note: "Seite 16 AUTO POWER OFF, das Display zeigt Disable und 4 hours" }),
    unknown("unknown34", l("Bytes 34 und 35, unbekannt", "Bytes 34 and 35, unknown"), 34, 2, "kein Menü-Eintrag ändert sie"),
    g("tempoLock", l("Tempo-Sperre", "Tempo lock"), 36, "onOff", [0, 1], { note: "Seite 10 TEMPO LOCK" }),
    g("powerSave", l("Stromsparen", "Power save"), 37, "powerSave", [0, 2],
      { note: "Seite 17 POWER SAVE MODE, das Display zeigt Disable, Auto und Enable" }),
    g("touchScaleRange", l("Touch-Scale-Umfang", "Touch scale range"), 38, "octaves", [1, 4],
      { note: "Seite 12 TOUCH SCALE RANGE; das Byte zählt die Oktaven selbst, 0 ist am Gerät nicht einstellbar" }),
    unknown("unknown39", l("Byte 39, unbekannt", "Byte 39, unknown"), 39, 1, "kein Menü-Eintrag ändert es"),
    g("clockMode", l("Clock"), 40, "clockMode", [0, 4],
      { note: "Seite 3 CLOCK MODE; der Dump meldet den gespeicherten Stand, nicht zwingend den laufenden" }),
    g("channel", l("Globaler Kanal", "Global channel"), 41, "oneBased", [0, 15],
      { note: "Seite 4 GLOBAL MIDI CH., das Display zeigt 01 bis 16" }),
    g("sendFilter", l("Sendefilter", "Send filter"), 42, "midiFilter", [0, 2],
      { note: "Seite 6 MIDI SEND FILTER; im Emulator zusätzlich geprüft: Short hält die Controller vom MIDI-Ausgang zurück, Short + Program auch den Programmwechsel" }),
    g("receiveFilter", l("Empfangsfilter", "Receive filter"), 43, "midiFilter", [0, 2],
      { note: "Seite 5 MIDI RECEIVE FILTER; im Emulator zusätzlich geprüft: bei Short und Short + Program wird ein ankommender Controller verworfen. Die Notiz vom 16.9. nannte Byte 42 so, das widerspricht dieser Messung" }),
    unknown("unknown44", l("Bytes 44 bis 251, unbekannt", "Bytes 44 to 251, unknown"), 44, 208, "kein Menü-Eintrag ändert sie"),
    g("magicEnd", l("Endekennung", "End marker"), 252, null, null,
      { type: "bytes:4", edit: "readonly", note: "GLED, die Firmware prüft beim Laden nur diese vier Byte" }),
  ],
};
