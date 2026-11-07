# 91. Part-Mute nur solange gedrückt

Wunsch aus der Community (Oktober 2026), nach dem Vorbild des Korg ESX: Mutes ändern sich nur, solange PART MUTE gehalten
wird. PART MUTE gehalten, schaltet ein Pad seinen Part stumm oder wieder an (rastend, nicht nur solange das Pad gehalten
wird), und die Pad-LEDs zeigen die Mutes. Ohne gehaltenes PART MUTE spielen die Pads wie im Modus TRIGGER und zeigen, was
TRIGGER zeigt.
Stand 2026-11-06: **als Plugin im Katalog gebaut (Momentary Mute), im Simulator und im Emulator auf Hacktribe, rot und
blau geprüft, am Gerät nicht.** Marker: **gemessen**, **hergeleitet**, **ungeprüft**.

## Was die Firmware tut

Ohne Plugin, im Emulator auf Hacktribe gemessen (Pad-Modus im LED-Manager bei +0xB58: 0 PART MUTE, 3 TRIGGER, 4
SEQUENCER, 5 KEYBOARD):

- PART MUTE schaltet den Pad-Modus schon beim **Druck** auf PART MUTE, nicht erst beim Loslassen. (gemessen)
- Nach dem Loslassen bleibt der Modus PART MUTE (er rastet), bis eine andere Modus-Taste kommt. (gemessen)
- Im Modus PART MUTE schaltet ein Pad den Mute seines Parts um, auch mit gehaltenem PART MUTE; ein zweiter Druck schaltet
  zurück. Im Modus TRIGGER wählt ein Pad seinen Part und ändert keinen Mute. (gemessen)
- SHIFT + PART MUTE lässt den Pad-Modus stehen und holt die gemuteten Parts zurück. (gemessen)
- Eine Modus-Taste bei gehaltenem PART MUTE schaltet in ihren Modus, das Loslassen von PART MUTE ändert daran nichts.
  (gemessen)

Der Modus PART MUTE der Firmware ist also schon das Mute-Editieren, das der Wunsch für gehaltenes PART MUTE beschreibt,
nur rastet er. Es fehlt allein der Rückweg nach TRIGGER beim Loslassen.

## Entscheidung: die Firmware schaltet, das Plugin drückt beim Loslassen TRIGGER

Das Plugin lässt PART MUTE und die Pads bei der Firmware und drückt beim Loslassen von PART MUTE mit `korg.pressKey` die
Taste TRIGGER. Gehalten ist die Firmware im Modus PART MUTE (Pads muten, LEDs zeigen die Mutes), losgelassen im Modus
TRIGGER (Pads spielen, LEDs zeigen TRIGGER). Kein `korg.padHold`, kein `korg.keyHold`, kein `korg.mute`, keine
nachgebauten Trigger und keine eigenen LEDs. (Urteil)

Verworfen:

- PART MUTE mit `korg.keyHold` halten, die Firmware in TRIGGER lassen und die Pads bei gehaltenem PART MUTE mit
  `korg.padHold` nehmen und mit `korg.mute` schalten: die Pad-LEDs zeigen dann weiter TRIGGER, für die Mutes müsste das
  Plugin mit `korg.ledHold` alle Panel-LEDs übernehmen. Mehr Code für dasselbe, das die Firmware schon kann. (Urteil)
- Die erste Fassung (ein Pad im Modus PART MUTE mutet nur, solange es gehalten wird) beruhte auf einem falschen Bild vom
  ESX und ist ersetzt.

## Gebaut

- Katalog-Plugin **Momentary Mute** (`data/script/presets.mjs`, Hintergrund, keine App, API 15 für `korg.pressKey`).
- Beim Loslassen von PART MUTE drückt es TRIGGER, außer SHIFT war beim Druck von PART MUTE gehalten (SHIFT + PART MUTE
  bleibt bei der Firmware) oder bei gehaltenem PART MUTE kam eine andere Modus-Taste (deren Modus bleibt).
- Die Seite MOMENT MUTE im Menü BLECH: 1 an (Vorgabe), 0 aus, dann bleibt PART MUTE ein rastender Modus wie ohne Plugin.
- Tests: `test/script-moment-mute.test.mjs` (Simulator: TRIGGER beim Loslassen, nichts bei anderen Tasten, SHIFT, Modus-Taste
  bei gehaltenem PART MUTE, Menü aus und an) und `tools/emu/plugin_catalog15_cases.py` (Emulator, Hacktribe, rot, blau:
  Modus 0 beim Halten, Pads schalten Mutes um und die bleiben, nach dem Loslassen Modus 3 und ein Pad wählt seinen Part,
  SEQUENCER bei gehaltenem PART MUTE und SHIFT + PART MUTE bleiben in SEQUENCER). (gemessen)

## Offen

- Am Gerät nicht geprüft. (**ungeprüft**)
- Gegen einen echten ESX nicht verglichen; das Ziel folgt der Beschreibung aus der Community. (**ungeprüft**)
- Losgelassen leuchtet die Taste TRIGGER, nicht PART MUTE, weil die Firmware im Modus TRIGGER ist. (hergeleitet)
- Wer vorher in SEQUENCER oder KEYBOARD war, landet nach PART MUTE in TRIGGER. (hergeleitet aus der Entscheidung)
- Steht die Firmware beim Start des Plugins schon im Modus PART MUTE, rastet sie dort bis zum nächsten Druck auf PART MUTE
  oder eine Modus-Taste; das Plugin kennt den Pad-Modus nicht. (hergeleitet)
- Bei offener App sieht die Firmware PART MUTE nicht, `korg.pressKey` erreicht sie aber: das Loslassen schaltet dann den
  Pad-Modus auf TRIGGER, ohne dass vorher PART MUTE ankam. (hergeleitet)
- Ein Pad, das bei gehaltenem PART MUTE gedrückt und erst nach dem Loslassen losgelassen wird, schaltet seinen Mute beim
  Druck um; sein Loslassen kommt im Modus TRIGGER an. Im Emulator ohne Fehler, hörbar nicht geprüft. (gemessen, Klang
  **ungeprüft**)
- Mit PATTERN CONFIRM gehören die Pads beim Ansehen eines anderen Patterns dessen Mutes; das bleibt Sache der Firmware.
  (**ungeprüft**)
