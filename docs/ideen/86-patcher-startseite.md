# 86. Patcher: neue Startseite, SD-Karte wählen

Wunsch (31.10.), geplant für 1.3.9. Stand 2026-10-31: **aufgeschrieben, nichts gebaut.** Marker: **gemessen**,
**hergeleitet**, **ungeprüft**.

## Was schiefgeht

- Viele sehen auf der Startseite nur den Knopf für das Update über USB und den Rest nicht. (Rückmeldungen aus der Community)
- Viele legen den Ordner `KORG/blechtribe` an, bevor die Firmware drauf ist, oder legen die Firmware in diesen Ordner und
  wundern sich, dass nichts passiert. (Rückmeldungen)
- Die fertige Datei landet im Downloads-Ordner; den Weg auf die Karte muss jeder selbst finden. (gemessen, heutiger Ablauf)

## Vorschlag

- Startseite neu: ein klarer Weg von oben nach unten, das Update über USB als ein Weg unter mehreren, nicht als einziger
  Knopf.
- Hacktribe mit in die erste Auswahl: wer Hacktribe will, hakt es an und klickt einen Knopf, statt auf der folgenden Seite
  noch ein Feld zu wählen. Die Datei `hacktribe-2.patch` dürfen wir nicht mitliefern; ob die App sie auf dem Rechner des
  Nutzers direkt bei Hacktribe laden darf, ist eine Frage der Lizenz. (**ungeprüft**, vorher klären)
- Als letzter Schritt das Laufwerk der SD-Karte wählen. Gibt es dort `KORG/hacktribe` oder `KORG/electribe sampler`
  (blau: `KORG/electribe`), legt die App die Datei je nach Firmware in den richtigen Ordner. Sonst wählt man den Ordner
  selbst im Dateidialog, nicht im Downloads-Ordner.
- Warnung, wenn die Datei in `KORG/blechtribe` landen würde oder dieser Ordner schon vor der Firmware angelegt wurde.

## Offen

- Im Browser gibt es keinen freien Zugriff auf Laufwerke; dort bleibt der Dateidialog (File System Access nur in Chromium).
  (hergeleitet)
- Woran die App eine SD-Karte erkennt (Wechseldatenträger, Ordner `KORG`). (**ungeprüft**)
