# USB

Was die Electribe am USB anbietet, wo der Treiber in der Firmware liegt, was eine zweite Schnittstelle für Daten bräuchte
und wie die Treiber der Rechner sie sehen. Alles gilt für den roten Sampler 2.02 mit [Hacktribe](../glossary.md#hacktribe).
Der Weg der Daten über [SysEx](../glossary.md#sysex) steht in [Sample-Datei](sample-datei.md) und
[development.md](../development.md).

Die Rohmessung ist gelöscht und in der Git-Geschichte lesbar:
`git show 03c7827adc7b:docs/messungen/2026-10-24-usb.md`.

Markierungen: **gemessen am Gerät**, **offline gelesen** (Abbild `hacktribe-original.VSB` gelesen), **hergeleitet**,
**offen**.

## Was das Gerät anbietet

Gemessen am Gerät (24.10.), nur lesend an einem Linux-Rechner: `lsusb`, `/sys/bus/usb/devices`, `dmesg`, `/proc/asound`.
Kein SysEx, keine MIDI-Nachricht, kein Reset. Ohne Root meldet `lsusb -v` "Couldn't open device", die Deskriptoren kommen
dann aus dem Cache des Kernels, die Jack-Namen fehlen dort.

| Eigenschaft | Wert |
|---|---|
| VID/PID | `0944:012E`, "KORG INC." / "electribe2 sampler", keine Seriennummer, `bcdDevice` 1.00 |
| Geschwindigkeit | USB 2.0, High Speed (480 Mbit/s) |
| Geräteklasse | 0 (pro Schnittstelle), EP0 64 Byte |
| Konfiguration | eine, selbst versorgt, `MaxPower` 0 mA, `wTotalLength` 83 Byte |
| Schnittstellen | **eine**: Nummer 0, Klasse Audio (1), Unterklasse MIDI Streaming (3). Keine AudioControl-Schnittstelle, die die USB-MIDI-Norm vor MIDI Streaming verlangt |
| Jacks | zwei pro Richtung: Embedded IN 16 / External OUT 64, Embedded OUT 48 / External IN 32 (ein Kabel je Richtung) |
| Endpunkte | EP1 OUT `0x01` und EP1 IN `0x81`, beide Bulk, 512 Byte |
| Andere Klassen | keine: kein Massenspeicher, kein CDC, kein Vendor |
| Linux | bindet `snd-usb-audio` und meldet "Quirk or no altset; falling back to MIDI 1.0"; ALSA-Port `hw:2,0,0` "electribe2 sampler _ PAD/KNOB", Typ Legacy |

## In der Firmware

| Aussage | Status |
|---|---|
| Controller ist USB0 des AM180x bei `0x01E00000` (Mentor MUSBMHDRC, OTG, High Speed). Der Getter `0xC0016628` gibt die Basis zurück. USB1 (OHCI, `0x01E25000`) kommt im Abbild nicht vor | offline gelesen: die Basis steht einmal als Immediate, die Konstante `0x01E25000` gar nicht |
| Treiber in vier Quelldateien laut Assert-Strings: `MCU/Component/AM180xUSB.cpp` (rund `0xC00195D8` bis `0xC001AA7C`), `usb/cusbdc.cpp`, `usb/cusbreq.cpp`, `usbmidi/cusbmin.cpp` und `tusbmin.cpp` (`0xC002C6CC` bis `0xC002CA04`) | offline gelesen |
| Kein Code für andere Klassen: keine Quelldatei, keine Strings, keine Deskriptoren für Massenspeicher, CDC oder Vendor | hergeleitet, das Fehlen von Code ist so nur wahrscheinlich |
| Deskriptortabelle bei `0xC00A40B4`: FS-Gerät `0xC00A3FD0` (`bcdUSB` 1.10), FS-Konfiguration `0xC00A3FF8` (Bulk 64 Byte), HS-Gerät `0xC00A3FE4` (2.00), HS-Konfiguration `0xC00A404C` (Bulk 512 Byte), dahinter die Zeiger auf die Strings. 11 Verweise aus dem Treiber | offline gelesen |
| Strings in UTF-16 ab `0xC00A410E`: Hersteller, Produkt, Jack 3 "electribe2 sampler _ SOUND", Jack 4 "electribe2 sampler _ PAD/KNOB". Linux zeigt nur den zweiten | offline gelesen |
| Endpunkt-Einrichtung `0xC0019990` setzt nur Index 1 (`INDEX` `0x40E`): RX-FIFO bei FIFO-Adresse 64 Byte, TX-FIFO direkt dahinter, Größe gleich Paketgröße (64 oder 512, sonst Assert). EP2 bis EP4 werden nicht eingerichtet | offline gelesen (Schreibzugriffe auf `0x40E`, `0x462`, `0x463` und weitere Register des Index-Fensters) |
| FIFO-RAM belegt: 64 (EP0) + 512 + 512 Byte bei High Speed | hergeleitet; die Größe des FIFO-RAM im AM1808 ist nicht nachgelesen |

## Was eine zweite Schnittstelle bräuchte

Ziel wäre ein Bulk-Kanal für Samples neben MIDI, zum Beispiel Schnittstelle 1, Klasse `0xFF` (Vendor), EP2 OUT/IN Bulk
512 Byte. Alles hier ist **hergeleitet**, nichts gebaut oder ausgeführt.

1. **Deskriptoren:** zwei neue Konfigurationen (FS und HS) mit `bNumInterfaces` 2 und neuer `wTotalLength` im
   Patch-Bereich, die Zeiger in der Tabelle `0xC00A40B4` auf sie umbiegen. Die Strings können bleiben.
2. **Endpunkt einrichten:** in oder nach `0xC0019990` Index 2 setzen, FIFO-Adressen hinter die von EP1 legen, Paketgrößen
   und Bulk-Modus in die CSR-Register. Platz im FIFO-RAM sollte reichen (offen, siehe oben).
3. **Interrupts:** die Endpunkt-Interrupts für EP2 freischalten und im Handler von `AM180xUSB.cpp` an eigenen Code geben.
   Ob der Handler nur EP0 und EP1 kennt, ist offen.
4. **Standardanfragen:** `SET_INTERFACE`/`GET_INTERFACE` und `CLEAR_FEATURE(HALT)` für Schnittstelle 1 und EP2 beantworten
   statt abweisen (`cusbreq.cpp`, offen).
5. **Wohin mit den Daten:** in den Arbeitspuffer, dann über die Dateifunktionen der Firmware auf die Karte
   ([Virtuelle SD-Karte](virtuelle-sd.md)). Der Empfang läuft im Interrupt, das Schreiben auf die Karte muss in eine Task.
6. **Rechner:** Linux und macOS lassen eine Vendor-Schnittstelle frei, libusb (im Browser WebUSB) kann sie öffnen, während
   `snd-usb-audio` Schnittstelle 0 behält. Windows braucht WinUSB, also MS-OS-Deskriptoren (BOS, `bcdUSB` 2.01) oder einen
   von Hand gebundenen Treiber.

**Risiko:** Jede Änderung an den Deskriptoren ändert, was alle Rechner sehen. Ein Fehler kann die MIDI-Verbindung kosten,
und die ist auch der Weg für Updates über USB. Der Weg über die Karte (SOFTWARE UPDATE) bleibt, solange die Firmware
startet. macOS und Windows nehmen das Gerät heute trotz fehlender AudioControl-Schnittstelle an; ob das mit zwei
Schnittstellen so bleibt, ist offen.

**Ohne neue Schnittstelle:** Die vorhandenen Bulk-Endpunkte haben bei High Speed schon 512 Byte. Der Engpass beim SysEx-Weg
ist eher die Arbeit im Gerät (7-Bit-Packen, ein Block unterwegs) als der Bus: gemessen sind 152 bis 200 KiB/s beim
Flash-Lesen ([Ganzer Flash](../messungen/2026-10-09-flash-dump.md)). Größere Blöcke und mehrere Blöcke unterwegs im
bestehenden BLECH-Protokoll wären der kleinere Schritt, wie viel das bringt, ist nicht gemessen. **hergeleitet**

## Treiber am Rechner

| System und Treiber | Was der Rechner sieht | SysEx-Antworten | Stand |
|---|---|---|---|
| Linux, `snd-usb-audio` | ein Port "electribe2 sampler _ PAD/KNOB" | kommen an | gemessen am Gerät (24.10.) |
| Windows, Korgs USB-MIDI-Treiber | ein Eingang "… PAD/KNOB" (Clock kommt an), ein Ausgang "… SOUND" | kommen nicht an, die App findet die Electribe nicht | gemessen (Windows 10, Treiber 1.15.63, 28.10.) |
| Windows, Klassentreiber von Windows | ein Ein- und ein Ausgang mit dem Gerätenamen | kommen an, die App verbindet | gemessen (Windows 10, 28.10.) |
| macOS, mit und ohne Korgs Treiber | zwei Eingänge | kommen an, der Treiber blockiert sie nicht | Rückmeldung (14.11.) |

Abhilfe unter Windows: Korgs Treiber im Geräte-Manager samt Treibersoftware entfernen und neu starten. Bietet das KORG
Driver Setup Utility danach die Neuinstallation an, schließen. Die App sagt das (`settings.midi.korgDriver`), die Seite
Blechy auch ([Rettung](../rettung.md)). Korgs Windows-Treiber bindet nach VID/PID; wie er auf eine zweite Schnittstelle
reagiert, ist offen.

## Offen

- Device-Qualifier und BOS am Gerät (brauchen Root für `lsusb -v`).
- Ob der Handler EP2 bis EP4 schon im Interrupt abfragt oder nur EP1.
- Größe des FIFO-RAM und ob Doppelpuffer genutzt wird.
- Verhalten von macOS, Windows und Korgs Treiber bei einer zweiten Schnittstelle.

Quelle: Messung 2026-10-24/usb
