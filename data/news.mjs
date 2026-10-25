/**
 * What is new, per app version, in plain words for people who do not read release notes. The desktop app shows the
 * entries the user has not seen yet once after an update (site/app/update.mjs, showNews); the firmware has no room for it.
 */
export const NEWS = Object.freeze([
  Object.freeze({
    version: "1.3.0",
    items: Object.freeze([
      "Sync Groups: Patterns derselben Gruppe wechseln ohne MENU am Sequenzende und spielen wie eine lange Sequenz. Einstellen auf der Seite SYNC GROUP.",
      "16 neue Effekte hinten in INSERT FX und MASTER FX: Delays, lautere Verzerrer und fünf neue Master-Effekte. Die Werks-Presets bleiben auf ihren Plätzen.",
      "Doom ist spielbar: SHIFT + TAP beim Einschalten, Laufen, Feuern und Waffenwahl liegen auf den Pads.",
      "Der Emulator startet von selbst neu, wenn er abstürzt. Unter Windows ohne eigenes Konsolenfenster.",
      "Rettung: eine Seite mit Schritten für jede Lage, auch wenn die Electribe nicht mehr startet.",
      "Im Patcher wählst du selbst: neueste BLECHTRIBE-Version oder eigene BLECH.patch, Hacktribe dazu oder nicht.",
      "Firmware-Update über USB: ein Knopf im Patcher, keine SD-Karte mehr nötig, sobald BLECHTRIBE einmal drauf ist.",
      "Plugins per USB direkt auf die Electribe schicken.",
      "GIF Player: Bilder und kleine Animationen von der Karte auf dem Display abspielen (unter TOOLS).",
      "Bis zu 12 Apps statt 8. Sind alle Plätze voll, sagt die Electribe es beim Import.",
      "Plugins mit Bildern brauchen viel weniger Platz.",
      "Blechy zeichnet beim Laden, winkt beim Ausschalten und ersetzt den Kasten bei Kartenfehlern.",
      "POWER SAVE im Menü: LEDs dimmen und Displaylicht einstellbar.",
      "Effekt-Presets als Datei (.e2fx) weitergeben.",
      "Fehlermeldungen in einfachen Worten, jede sagt, was zu tun ist.",
      "CALIBRATE DISPLAY: drei unterschiedlich schnelle Bälle auf der Kontrastseite helfen beim Einstellen des Displays.",
      "Plugins werden beim Laden mit weniger Rechenarbeit geprüft. Die Größenlimits bleiben gleich.",
      "Auch auf der blauen Electribe: BLECH-Menü mit Plugins, Sync Groups, EXIT + WRITE speichert, EXIT + Pad setzt einen Part zurück, Akkorde in Pink.",
      "Untere LEDs: RAINBOW jetzt auch bei vollem Pegel (METER LOUD), eine Farbrunde pro Takt im Tempo des Patterns.",
      "Baukasten: Werks-Presets lassen sich beim Export auf andere Plätze schieben. Aus deiner SYSTEM.VSB, etwa Korgs Original, holst du dir deren Presets als eigene, zum Beispiel den Slicer.",
      "Hinweise und Fehler erscheinen unten rechts statt mitten auf der Seite.",
      "Ein/Aus 7 s gedrückt halten schaltet auch beim Laden der Samples aus.",
      "BLECHTRIBE lässt Hacktribes USB-Befehle nicht mehr durch, das Flash-Schreiben darüber ist gesperrt. Hacktribe-Werkzeuge gehen mit EXIT beim Einschalten weiter.",
    ]),
  }),
]);
