/**
 * What is new, per app version, in plain words for people who do not read release notes. The desktop app shows the
 * entries the user has not seen yet once after an update (site/app/update.mjs, showNews); the firmware has no room for it.
 */
export const NEWS = Object.freeze([
  Object.freeze({
    version: "1.3.0",
    items: Object.freeze([
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
    ]),
  }),
]);
