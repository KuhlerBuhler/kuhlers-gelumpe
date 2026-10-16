# Apps und Display der Plugins

Stand 2026-10-14. Alles im Emulator gemessen (Firmware 2.02 mit Hacktribe, virtuelle Karte),
am Gerät nichts geprüft. Markierungen: **gemessen**, **hergeleitet**, **offen**.
Code: `tools/patch/script_app.s`, `tools/patch/script_hooks.s` (Eingangsfilter und
Rahmenhaken), `tools/patch/script_display.s`; Prüfungen: `tools/emu/script_cases.py`
(`app-*`, `snake-*`, `exit-*`, `take-*`), `tools/patch/test_script_hooks.py`,
`tools/patch/test_script_display.py`, `test/script-app.test.mjs`. Anwendersicht:
[Plugins](../plugins.md), Abschnitt "Apps und das Display".

## Der Fehler am Gerät (v12)

Nach dem Laden von `e2sPlugin.all` zeichnete Snake sofort in jedem Rahmen über das ganze
Display, der Nutzer sah seine Patterns nicht und kam nicht heraus. Ursache **gemessen**: die
Laufzeit kopierte das Bild "sobald ein Plugin etwas ausgegeben hat" über das Display RAM, und
EXIT erreichte das Plugin nur als Taste. Jetzt zeichnet nur der Besitzer des Displays.

## Wie es jetzt läuft

- **Besitzer.** Ein Wort in der Laufzeit (`APP_STATE`, `RT_APPS`) hält den Besitzer des Displays
  (0, wenn niemand). Die Zeichenaufrufe prüfen vor jedem Pixel, ob das laufende Plugin der
  Besitzer ist, sonst tun sie nichts und melden nichts. Der Rahmenhaken kopiert das Bild nur, solange
  es einen Besitzer gibt und der Hauptbildschirm (Bildschirm 1) offen ist. **gemessen**
  (`test_script_display.py`, Fälle `only_the_owner_...`, `the_picture_reaches_...`).
- **App anmelden.** `korg.app(name, gruppe)` im Rumpf trägt Plugin, Namenszeiger (er zeigt in den
  Block, der im Pool bleibt) und Gruppe in eine Tabelle von 8 Plätzen (seit 15.10. mit einem neunten: Eintrag 0 gehört Blechy, der in BLECH eingebauten App in einer Gruppe, die kein Menü zählt, [Blechy](2026-10-15-blechy.md); für Plugins bleibt es bei 8). Das Menü zählt sie je Gruppe.
- **Öffnen.** ENTER auf der App-Seite: Besitzer setzen, das Bild löschen, `open` an genau dieses Plugin,
  dann `SWITCH_SCREEN(1, 0)` zum Hauptbildschirm (die Funktion stellt nur eine Nachricht ein, der
  Wechsel läuft in der nächsten Runde). **gemessen:** der Hauptbildschirm steht beim ersten Rahmen.
- **Rahmen und Ereignisse.** Eine App bekommt `frame` nur, solange sie Besitzer ist. `open` und `close`
  tragen den Eintrag des Plugins im ersten Argument und gehen nur an dieses Plugin. **gemessen**
  (`test_script_hooks.py`, Fälle `app_events_reach_...`).
- **EXIT.** Im Eingangsfilter, vor dem Ring: ist ein Besitzer da, schließt EXIT ihn, das Plugin bekommt
  `close` und nie die Taste, die Firmware bekommt EXIT wie immer. Solange ein Besitzer da ist, gehören die
  Tasten ihm (sie gehen in den Ring, die Firmware sieht sie nicht), Encoder, Regler, Pads und Touchpad
  bleiben bei der Firmware. **gemessen** (Fälle `exit_closes_...`, `the_buttons_belong_...`).
- **Der Hauptbildschirm kommt zurück.** Die Firmware zeichnet ihre Widgets nur dort neu, wo sich etwas
  geändert hat. Gibt die Laufzeit das Display zurück, bliebe also unser Bild stehen
  (4539 Pixel Unterschied zu einem Gerät ohne App, **gemessen**). Die Bildschirmroutine
  (`0xC006F178`, aufgerufen mit `0xC06C2220`) löscht und zeichnet alles neu, wenn das Byte bei `+0x4c`
  gesetzt ist. Die Laufzeit setzt es beim Schließen und bei `korg.display.release()`: danach ist das
  Display Pixel für Pixel gleich dem eines Geräts, das nie eine App hatte (**gemessen**, Fall
  `app-exit-zurueck-auf-den-hauptbildschirm`). **Hergeleitet** statt gemessen: dass es ein Neuzeichner ist
  und nichts anderes bedeutet, steht nicht in Korgs Code, es folgt aus dem Verhalten und dem Befund,
  dass `0xC006F178` bei gesetztem Byte erst `0xC003F55C(0, 0, 128, 64)` ruft.
- **Schließen aus dem Rahmenhaken.** Verlässt die Firmware den Hauptbildschirm, schließt der Rahmenhaken
  den Besitzer (`close`), damit er keine Tasten behält, die er nicht mehr braucht.
- **`korg.display.take()`.** Ein Plugin, das keine App ist, wird Besitzer, wenn der Hauptbildschirm offen ist
  und niemand das Display hat. Ein Plugin mit `korg.app` bekommt 0. **gemessen**
  (`test_take_and_release`, Fälle `take-*`, `exit-beendet-take`).

## Gemessen (14.10., Emulator)

- **Laden** (`app-laden-laesst-das-display-in-ruhe`, `app-ohne-oeffnen-zeichnet-nichts`): vier Plugins aus
  einer Datei, darunter eines, das in jedem Rahmen das ganze Display füllen will und keine App ist: das
  Display ist gleich dem eines Geräts ohne Plugins.
- **Öffnen und Zählen** (`app-oeffnet-aus-dem-menue`, `app-zaehlt-und-zeigt`, `app-zaehlt-auch-geschlossen`,
  `app-oeffnet-wieder-mit-dem-stand`): das Bild der geöffneten Klicker-App ist das des Browsermodells; TAP
  zählt und setzt die LED auch bei geschlossener App, das Display bleibt dabei die Firmware.
- **EXIT** (`app-exit-zurueck-auf-den-hauptbildschirm`, `snake-exit`): der Hauptbildschirm mit den Patterns ist
  nach EXIT Pixel für Pixel der eines Geräts ohne App. Die Taste MENU wird, solange die App offen ist, nicht an die
  Firmware gegeben (`app-tasten-gehoeren-der-offenen-app`).
- **Snake aus dem Menü** (`snake-aus-dem-menue-in-der-firmware`, `snake-faengt-bei-open-neu-an`): 150 Rahmen mit
  denselben Eingaben ergeben dasselbe Display wie im Browsermodell; nach EXIT und erneutem Öffnen fängt ein neues Spiel an.
- **Fehler** (`app-fehler-auf-dem-eigenen-bildschirm`, `fehler-ohne-app-zeichnet-nichts`, `fehler-seite-im-menue`):
  die offene App, die ausfällt, zeigt Name, Zeile und Fehler auf ihrem Bildschirm; der Fehler eines Plugins ohne Display
  steht nur im Menü (`DIV_ZERO L3`) und das Display bleibt unberührt.
- **EXIT lässt sich nicht abfangen** (`exit-oeffnet-die-falle-nicht-zu`, `exit-schliesst-trotz-fallen-app`,
  `take-zeigt-das-bild`, `exit-beendet-take`, `laden-allein-zeichnet-nie`): eine App, die jede Taste fängt und
  das Display füllt, und ein Plugin, das das Display nahm, werden von EXIT geschlossen; keines sieht die Taste.

## Offen

- **Am Gerät nichts geprüft.** Der Neuzeichner-Mechanismus und die Reihenfolge Öffnen, Bildschirmwechsel,
  erster Rahmen sind nur im Emulator gespielt.
- Eine App, die sich durch ein Fenster der Firmware (zum Beispiel ein Fehlerfenster) verdeckt sieht, wird nicht
  geschlossen: Fenster ändern die Bildschirmnummer nicht, das Bild der App läge dann über dem Fenster (derselbe
  Befund wie bei jedem Bild, das die Laufzeit zeigt, nicht gesondert gespielt).
