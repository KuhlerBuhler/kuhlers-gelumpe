/**
 * One short German sentence for every API entry, event and event value of the script contract, for the
 * editor's completions, parameter hint and hover. Nothing here reaches a block; test/script-describe.test.mjs
 * fails when the contract has an entry without a text here.
 */

export const API_DOCS = Object.freeze({
  "korg.led": "Setzt die Helligkeit einer LED, 0 ist aus, 255 ist voll. Die Nummer schreibt man am besten als Namen, zum Beispiel korg.led.TAP.",
  "korg.millis": "Gibt die Millisekunden seit dem ersten Aufruf zurück.",
  "korg.display.clear": "Löscht das Display. Zeichnen darf nur die offene App, oder ein Plugin, das das Display mit korg.display.take genommen hat.",
  "korg.display.text": "Schreibt einen Text mit der linken oberen Ecke bei x und y, höchstens 31 Zeichen.",
  "korg.display.number": "Schreibt eine Zahl dezimal mit der linken oberen Ecke bei x und y.",
  "korg.display.pixel": "Setzt oder löscht einen Pixel: on 1 setzt ihn, on 0 löscht ihn.",
  "korg.display.rect": "Zeichnet ein gefülltes Rechteck, links oben bei x und y.",
  "korg.display.clearRect": "Löscht ein Rechteck, links oben bei x und y.",
  "korg.display.bitmap": "Zeichnet ein Bild aus einem Feld, links oben bei x und y. Ein Platz hält die 8 Pixel einer Spalte, das niedrigste Bit oben; width Plätze sind ein Streifen. Nur gesetzte Pixel.",
  "korg.display.textNumber": "Schreibt einen Text und gleich dahinter eine Zahl dezimal, mit der linken oberen Ecke bei x und y. Der Text darf höchstens 31 Zeichen haben.",
  "korg.display.take": "Nimmt das Display für ein Plugin, das keine App ist. Gibt 1 zurück, wenn es geklappt hat, sonst 0. EXIT gibt es wieder frei.",
  "korg.display.release": "Gibt das mit korg.display.take genommene Display zurück an die Firmware.",
  "korg.store.get": "Liest den gespeicherten Wert aus einem der 16 Plätze dieses Plugins, oder fallback, wenn dort nie einer gespeichert wurde.",
  "korg.store.set": "Setzt den Wert eines Platzes im RAM. Auf die Karte kommt er erst mit korg.store.save.",
  "korg.store.save": "Merkt das Speichern der gesetzten Werte auf der Karte vor.",
  "korg.read.transport": "Gibt den Zustand des Transports zurück: 0 Stop, 1 Play, 2 Pause, 3 REC bereit, 4 Aufnahme.",
  "korg.read.tempo": "Gibt das Tempo in Zehntel BPM zurück, 1600 heißt 160,0.",
  "korg.read.pattern": "Gibt die Nummer des gewählten Patterns zurück, 0 bis 249.",
  "korg.read.part": "Gibt den gewählten Part zurück, 0 bis 15, oder 16 für alle.",
  "korg.read.step": "Gibt den Schrittzähler des Parts zurück, 0 bis 63.",
  "korg.read.mute": "Gibt 1 zurück, wenn der Part stumm geschaltet ist, sonst 0.",
  "korg.read.knob": "Gibt den letzten Rohwert des Reglers zurück, den die Laufzeit gesehen hat, bis dahin 0.",
  "korg.play": "Drückt PLAY, wie die Taste am Gerät.",
  "korg.stop": "Drückt STOP, wie die Taste am Gerät.",
  "korg.pattern": "Wählt ein Pattern.",
  "korg.tempo": "Setzt das Tempo in Zehntel BPM, 1200 heißt 120,0.",
  "korg.part": "Wählt einen Part.",
  "korg.mute": "Schaltet einen Part stumm (muted 1) oder lässt ihn spielen (muted 0).",
  "korg.backlight": "Schaltet die drei Farben des Display-Lichts ein (1) oder aus (0).",
  "korg.ledHold": "1 hält die Firmware davon ab, die Panel-LEDs neu zu schreiben, 0 gibt sie zurück.",
  "korg.menu.add": "Legt eine Seite im Menü BLECH an und gibt ihre Nummer zurück, -1 wenn alle Plätze belegt sind. Dreht der Nutzer daran, kommt das Ereignis menu.",
  "korg.app": "Meldet das Plugin als App im Menü BLECH an und gibt ihre Nummer zurück. Steht einmal ganz oben im Code, name hat höchstens 15 Zeichen.",
});

/** korg.onEvent is no API entry, the compiler reads it as a statement. */
export const ON_EVENT_DOC = Object.freeze({
  name: "korg.onEvent",
  signature: "korg.onEvent(\"ereignis\", handler)",
  text: "Meldet einen Handler für ein Ereignis an. Steht nur ganz oben im Code, ein Handler je Ereignis. Der Handler darf weniger Werte nehmen, als das Ereignis liefert.",
});

export const EVENT_DOCS = Object.freeze({
  start: { text: "Der Rumpf des Plugins selbst: die Anweisungen ganz oben, einmal beim Start. Kein Handler.", args: {} },
  ready: { text: "Einmal, im ersten Rahmen nach dem Start.", args: {} },
  frame: { text: "25 Mal je Sekunde. Eine App bekommt es nur, solange sie offen ist.", args: {} },
  buttonPress: { text: "Eine Taste wurde gedrückt.", args: { key: "Der Tastencode, zum Vergleichen mit einem Namen wie korg.key.TAP." } },
  buttonRelease: { text: "Eine Taste wurde losgelassen.", args: { key: "Der Tastencode, zum Vergleichen mit einem Namen wie korg.key.TAP." } },
  knob: { text: "Ein Regler wurde bewegt.", args: { index: "Die Nummer des Reglers.", value: "Der neue Wert, 0 bis 1023." } },
  encoder: { text: "Ein Drehgeber wurde gedreht.", args: { index: "Die Nummer des Drehgebers.", delta: "Die Drehung, positiv nach rechts, negativ nach links." } },
  pad: { text: "Ein Pad wurde gedrückt oder losgelassen.", args: { index: "Die Nummer des Pads.", down: "1 beim Drücken, 0 beim Loslassen.", velocity: "Die Anschlagstärke." } },
  touch: { text: "Das Touchpad wurde berührt oder der Finger darauf bewegt.", args: { x: "Die waagerechte Stelle der Berührung, 0 bis 1023.", y: "Die senkrechte Stelle der Berührung, 0 bis 1023.", first: "1 bei der ersten Stelle einer Berührung, also dort, wo der Finger aufsetzt, sonst 0." } },
  step: { text: "Der Sequencer ist einen Schritt (16tel) weitergelaufen.", args: { step: "Der Schritt von Part 0, 0 bis 63." } },
  beat: { text: "Ein Viertel ist vorbei, bei jedem vierten Schritt.", args: {} },
  play: { text: "Der Transport läuft an.", args: {} },
  stop: { text: "Der Transport steht.", args: {} },
  rec: { text: "Die Aufnahme beginnt.", args: {} },
  patternChange: { text: "Es wurde ein anderes Pattern gewählt.", args: { index: "Die Nummer des neuen Patterns, 0 bis 249." } },
  partChange: { text: "Es wurde ein anderer Part gewählt.", args: { part: "Die Nummer des neuen Parts." } },
  mute: { text: "Ein Part wurde stumm geschaltet oder wieder freigegeben.", args: { part: "Die Nummer des Parts.", muted: "1, wenn der Part jetzt stumm ist, sonst 0." } },
  tempo: { text: "Das Tempo hat sich geändert.", args: { tenthsBpm: "Das neue Tempo in Zehntel BPM." } },
  save: { text: "Die Einstellungen werden geschrieben, zum Beispiel beim Ausschalten.", args: {} },
  menu: { text: "Am Hauptrad wurde eine Seite gedreht, die das Plugin mit korg.menu.add angelegt hat.", args: { id: "Die Nummer der Seite, wie korg.menu.add sie zurückgab.", value: "Der neue Wert der Seite." } },
  open: { text: "Nur für Apps: der Nutzer hat die App im Menü BLECH geöffnet. Ab jetzt gehört ihr das Display.", args: {} },
  close: { text: "Nur für Apps: EXIT hat die App geschlossen, das Display gehört wieder der Firmware.", args: {} },
});

export const GROUP_DOCS = Object.freeze({
  GAMES: "Die App steht im Menü BLECH unter GAMES.",
  TOOLS: "Die App steht im Menü BLECH unter TOOLS.",
});

/** The two name families, for the completion entries that lead into them. */
export const NAME_FAMILY_DOCS = Object.freeze({
  key: "Namen der Tasten, zum Beispiel korg.key.TAP. Der Name ist der Wert von buttonPress und buttonRelease.",
  led: "Namen der LEDs, zum Beispiel korg.led.TAP. Der Name ist das erste Argument von korg.led.",
});
