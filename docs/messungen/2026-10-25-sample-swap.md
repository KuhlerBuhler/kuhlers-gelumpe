# Sample-Swap: Ladepfad, Platzverwaltung und noch fehlende Gerätetests

Stand: 25.10.2026. Phase 1 zu [Mehr Sample-Speicher](../ideen/25-mehr-sample-speicher.md).
Beleg: `measure:2026-10-25/sample-swap`.

**Gemessen** heißt hier ausdrücklich offline oder im ARM-Emulator. **Hergeleitet**
heißt aus gelesenem Code oder aus einer Rechnung geschlossen. **Offen** heißt,
dass der Versuch am echten Gerät fehlt. Kein Gerät wurde angesprochen. Kein
Sample-Swap-Patch wurde gebaut, keine Firmware, Samples oder Ausschnitte davon
ins Repository geschrieben.

## Entscheidung vor dem Bau

| Betriebsart | Stand | Grund |
|---|---|---|
| Während laufender Wiedergabe | am Gerät gemessen, für eine erste Version freigegeben | 64 KiB in 5,5 bis 6,3 ms, Bytes und Tabellen danach gleich; hörbar nur bei gezieltem Hinhören als ganz kurze Verzögerung (siehe Gerätemessung) |
| Beim Patternwechsel | offen | Alte Stimmen laufen weiter; Ladezeit von der Karte und Vorlaufzeit sind nicht gemessen |
| Bei gestoppter Wiedergabe | am Gerät gemessen | 1 bis 64 KiB, je dreimal, rund 11 bis 12 MiB/s |
| Grundsätzlich unmöglich | widerlegt | Lesen und Schreiben eines geladenen Samples im DSP gehen am Gerät, auch beim Abspielen |

**Entscheidung (25.10., nach der Gerätemessung):** Phase 2 darf gebaut werden. Offen und vor der
Freigabe zu klären: ein gelegentlicher Hänger beim ersten DSP-Zugriff (siehe unten), Slotwechsel,
Lebensdauer klingender Stimmen und die Fehlerbehandlung.

## Grundlage und Wiederholung

Vollständig berücksichtigt: [Idee 25](../ideen/25-mehr-sample-speicher.md),
[freier RAM](2026-10-22-ram-frei.md),
[voller Samplespeicher](2026-10-14-sample-speicher-voll.md),
[Metadaten](2026-10-07-sample-metadaten-ram.md),
[Speicherbereiche](../speicherbereiche.md),
[DSP](../hintergrund/dsp-erster-blick.md),
[Idee 26](../ideen/26-dsp-erfassen.md),
[Ton im Emulator](../ideen/52-ton-im-emulator.md),
[virtuelle SD](../hintergrund/virtuelle-sd.md) und
[Emulator](../emulator.md). Ergänzend die früheren
[DSP-Pfade](2026-10-08-dsp-audiopfade.md) und der
[WAV-Import](2026-10-08-usb-sample-import-offline.md).

**Gemessen offline:** Untersuchte Sampler-Abbilder enthalten jeweils 0x100 Byte
Kopf und 0x200000 Byte Nutzlast. Das zuerst untersuchte Hacktribe-Abbild hat SHA-256
`2df156c8fb7a1bddf7799111b40b04665c89e2341ad5dfaadad09ca92be3fc3f`.
Das zusätzlich geprüfte Originalabbild des roten Samplers hat SHA-256
`1d0f0689d5a12c8a8bde9f821f2a59adc5f6cd6012ddb201ebb192b72468a646`.
Die Profilerkennung erkennt beide ohne verschobene Pflichtstellen.

Für das Nutzabbild gilt ausschließlich:

```text
file = ram - 0xC0000000 + 0x100
```

DSP-Offsets, Arbeitspuffer und RAM oberhalb des Nutzabbilds sind damit keine
Dateioffsets. Der blaue Synth ist durch diese Sampler-Adressen nicht abgedeckt.
Die neuen Versuche verweigern ihn, statt seine RAM-Adressen zu raten. Eine spätere
Umsetzung muss dessen Adressen über `tools/patch/synthaddr.py` auflösen.

## 1. Von der Karte in den DSP

**Hergeleitet, erneut am ARM-Code geprüft:**

| Funktion / Aufrufstelle | Argumente und Aufgabe |
|---|---|
| `0xC0038D34`, Aufruf bei `0xC0038D60` | Startbefehl erzeugt den Pfad über `0xC0035A80`, prüft die Datei über `0xC0035440`, ruft den Gesamtlader auf |
| `0xC00364F0` | `r0 = Dateipfad`; öffnet `e2sSample.all`, liest den 4096-Byte-Kopf und läuft durch dessen Offsets |
| `0xC004F2B4`, Aufruf bei `0xC0036500` | setzt Aktivmarkierungen zurück und den DSP-Frei-Zeiger auf `0x00365EC0`; Gesamtladen ist daher kein inkrementeller Swap |
| `0xC00366E0` | Seek auf den RIFF-Dateioffset des jeweiligen Samples |
| `0xC00366FC` nach `0xC0035B10` | `r0 = Dateiobjekt`, `r1 = 0x494-Byte-Metadatenpuffer`, `r2 = -1`, `r3 = 0`; Parser des einzelnen Samples |
| `0xC003644C` | Einzelimport: `r0 = WAV-Pfad`, `r1 = gewünschter nullbasierter Slot`; derselbe Parser, Aufruf bei `0xC00364B4` |
| `0xC003629C` nach `0xC004EDF0` | reserviert DSP-Platz anhand des geparsten Deskriptors in `r0` |
| `0xC00362B8` nach `0xC00369F0` | liefert Arbeitspuffer `0xC0D3A940`; Freigabe über `0xC0036A08` |
| `0xC009DD74` / `0xC009E404` | Lesen `(Dateiobjekt, Ziel, Bytezahl, gelesene-Bytezahl*)` beziehungsweise Seek `(Dateiobjekt, Dateioffset)` |
| `0xC003631C` und `0xC00363E0` nach `0xC004EF28` | `r0 = CPU-Quelle`, `r1 = DSP-Byteoffset`, `r2 = Zahl der 16-Bit-Wörter` |

**Hergeleitet:** 16-Bit-PCM wird in Blöcken bis 65536 Byte gelesen und danach
geschrieben. 24-Bit-PCM wird im CPU-Puffer auf 16 Bit umgesetzt; bis 98304 gelesene
Bytes liefern 65536 DSP-Bytes. DSP-Offset und Restlänge rücken nach jedem Block
weiter. Eine Dateigröße von 50 MB ist daher keine Aussage über die benötigten
PCM-Bytes im DSP oder den Cache.

**Bereits gemessen im Emulator:** Alle 499 Transfers eines vollen Satzes nahmen
ihre Quelle aus diesem Arbeitspuffer. Das ist ein vollständiger Boot-Lauf aus der
[Messung vom 14.10.](2026-10-14-sample-speicher-voll.md), hier nicht erneut als
50-MB-Boot ausgeführt. Der Emulator hat keinen DMA und keinen Klang.

## 2. Tabellen, Löschen und Wiederbelegen

**Hergeleitet, erneut am ARM-Code geprüft:**

| Struktur | Adresse / Felder |
|---|---|
| Namen | `0xC047B080 + sichtbarer Index * 0x20`; Name ab `+12`, Importnummer bei `+30` |
| Wiedergabe | `0xC0362EE8 + aufgelöster Index * 0x10`; DSP-Start plus relativer Start bei `+0`, Loop/Ende bei `+4/+8`, Flags bei `+14/+15` |
| Metadaten | `0xC036AD88 + aufgelöster Index * 0x45C`; DSP-Basis `+0`, PCM-Bytelänge `+4`, Stereo `+9`, aktiv `+11`, wiederholter Index `+22` |
| Nächster freier DSP-Byteoffset | Wort bei `0xC00F9C80`; Abfrage `0xC004E208` |
| Freie Bytes | `0xC004E218`: `0x01C65EC0 - Zeiger`, Rest von höchstens vier Byte wird als null gemeldet |

**Hergeleitet:** Sichtbarer Slot und physischer Metadatenindex sind nicht
allgemein gleichzusetzen. Die Reservierung beginnt mit der Importnummer aus der
Namentabelle, zieht 50 ab und folgt drei Zuordnungen:

```text
k = name[slot].importnummer - 50
a = u16(0xC035738C + k * 0x20 + 0x10)
b = u16(0xC035F06C + a * 0x10 + 8)
i = u16(0xC0350644 + b * 8 + 2)
```

Die Löschroutine `0xC004E558` nimmt bereits `k`; sie löst über `0xC004E2F0`
auf. Für höhere oder umsortierte Slots reicht eine Rechnung mit dem sichtbaren
Index nicht. Der Gerätetest akzeptiert nur eine nachgelesene identische
Zuordnung. Er bildet keine neue allgemeine Gerätekarte ab.

**Gemessen im isolierten ARM-Emulator:**
[sample_swap_cases.py](../../tools/emu/sample_swap_cases.py) führt die originalen
Reservierungs-, Lösch- und Kapazitätsroutinen aus. Nur die Tabellen und Deskriptoren
sind selbst erzeugt, mit ausdrücklich identischen Zuordnungen für Index 500 und
501. Kein Boot, kein DSP-Ersatz und kein PCM-Transfer. Beide geprüften Builds
zeigen:

1. 1024 Byte für Index 500 beginnen bei `0x00365EC0`.
2. 2048 Byte für Index 501 folgen bei `0x003662C0`.
3. Erneutes Reservieren eines aktiven Platzes wird ohne Tabellenänderung abgewiesen.
4. Löschen von Index 500 deaktiviert ihn, lässt den Zeiger aber bei `0x00366AC0`.
5. Erneutes Laden von 512 Byte in denselben Slot beginnt bei `0x00366AC0`, nicht im Loch.
6. Löschen dieses letzten Samples setzt den Zeiger auf dessen Anfang zurück.
7. Danach Löschen von Index 501 lässt das erste Loch von 1024 Byte verloren.
8. Eine Reservierung bis genau `0x01C65EC0` geht; weitere 32 Byte werden abgewiesen.

**Hergeleitet:** Nur das letzte physische Sample gibt Platz an den normalen
Allocator zurück. Ein logischer Slot lässt sich wieder belegen, aber ohne eigene
Platzverwaltung bleibt ein Loch unbenutzt. Ein Swap müsste einen vorhandenen
DSP-Bereich direkt überschreiben und die zugehörigen Tabellen konsistent halten.
Die normale Reservierung ist dafür keine fertige Schnittstelle. Die Löschroutine
verschiebt keine PCM-Daten und löscht den DSP-Inhalt nicht.

**Offen:** Lebensdauer laufender Stimmen, Besitz des DSP-Offsets in weiteren
Strukturen und Übernahme geänderter Tabellen beim nächsten Note-On. Der
Tabellenversuch belegt keine hörbare Umschaltung. Ein im Pattern nicht mehr
ausgewähltes Sample kann noch ausklingen. Es darf deswegen nicht bereits als
verdrängbar gelten. Der bekannte Importfehler nach der Reservierung hat außerdem
keinen vollständigen Rollback, siehe [Import](2026-10-08-usb-sample-import-offline.md).

## 3. Host-Port und Durchsatz

**Hergeleitet, erneut am ARM-Code geprüft:**

```text
0xC004EF28(Quelle, DSP-Byteoffset, count16)
  -> 0xC0014284(DSP-Byteoffset, Quelle, count16)
  -> 0xC0014C34
  -> 0xC00146B4
```

Die normale Task-API sperrt Semaphore 1 und verwendet die Portbasis aus
`0xC0015C98`. `0x60000000` ist der 16-Bit-Datenport, `0x60000002` der
Status-/Steuerport. Der Kopf besteht aus sieben 16-Bit-Wörtern:

```text
0xAB, Offset_low16, Offset_high16, count16, 2, 0, 0
```

Zunächst warten GPIO und Statusbit 7, nach dem Kopf Statusbit 0. Je Gruppe von
höchstens 16 Wörtern wartet erneut `0xC00145F0`; der Helfer prüft über
`0xC001716C` GPIO `0x01E26098`, Bit 1, invertiert. Es gibt hier keine feste
Wartezeit und keine Zeitgrenze.

Die Datenschleife `0xC0014834` bis `0xC0014864` enthält 13 ARM-Befehle je
16-Bit-Wort, darunter einen CPU-Halbwort-Lesezugriff und einen Port-Halbwort-
Schreibzugriff. Ein ausgerichteter Transfer von N KiB bedeutet 512*N Wörter,
32*N Gruppen und mindestens 6656*N Befehlsausführungen dieser Schleife.
Kopf, Sperren, äußere Schleifen und unbekannte Wartezeiten kommen dazu.

**Offen:** Takte der externen Buszugriffe, GPIO-Wartezeiten und wirkliche KB/s.
13 Befehle sind weder 13 reale Takte noch eine gemessene Zeit. Die früheren
157 KB/s umfassen im Emulator das ganze Kartenladen. Sie dürfen nicht als
Host-Port-Geschwindigkeit oder als Gerätemessung verwendet werden.

**Hergeleitet:** Der untere Schreibpfad kürzt count16 auf 16 Bit. 65536 Wörter
würden zu null. Unter 16 Wörtern liest der Wrapper zunächst einen 16-Wort-Block,
ändert ihn und schreibt ihn zurück, auch bei Länge null. Größere Restblöcke
können überlappen. Für den Gerätetest gelten deshalb ganze KiB, 1 bis 64 KiB,
innerhalb eines nachweislich vorhandenen Samplebereichs.

## 4. Weiterlaufen während des Schreibens

**Hergeleitet:** Der Sampletransfer ist der direkte Host-Port-Befehl `0xAB`,
getrennt vom Frame- und A34-Postfach. Der ARM-Pfad selbst fordert vor diesem
Transfer keinen globalen Stopp an. Das beweist noch keine unterbrechungsfreie
Wiedergabe. Die Port-Semaphore kann andere Kommandos verzögern.

**Offen:** Ob der DSP während der Übertragung weiterrechnet, ob gehaltene
Stimmen aussetzen und ob neue Noten oder Patternwechsel verspätet ankommen.
Ein bereits klingender Dauerton allein genügt als Test nicht. Der
[Emulator](../emulator.md) ersetzt den DSP und DMA; auch das erfolgreiche
Rücklesen von Testdaten beweist keinen fehlerfreien Klang.

## 5. Grenzen von DSP und CPU-Cache

**Gemessen im früheren Boot-Lauf, hergeleitet als Softwaregrenze:**
`0x01C65EC0 - 0x00365EC0 = 26214400 Byte = 25 MiB` für die Nutzerbank. Die
neuen isolierten Versuche bestätigen die Grenze des Allocators, keine
physische RAM-Grenze.

**Gemessen offline am Bootformat:** 157 gültige DSP-Blöcke; höchstes Ende
eines SDRAM-Datenblocks `0x01F11B40`. Der DSP-Bootstrom hat in den drei
verglichenen lokalen Sampler-Abbildern denselben SHA-256
`83259e30eec2c6586c3756fa3a75d1f831f02e2436d950c4fdb648322a9ca774`.
**Hergeleitet:** 25 MiB sind nicht die Größe des gesamten DSP-SDRAMs.
Andere Bereiche enthalten DSP-Code, Werksbank und Effektspeicher.
**Offen:** Bestückung, physische Obergrenze und zusätzlich sicher nutzbare Bytes.
Kein Abtasten jenseits der belegten Samplebereiche ist vorbereitet.

**Hergeleitet aus der RAM-Karte:** Der konservative obere Cachebereich
`[0xC274F000, 0xC4000000)` bietet 25890816 Byte, rund 24,69 MiB. Für eine
Datei mit 50 MB dezimal kann das ausreichen. Exakt 50 MiB reines PCM ergeben
bei 25 MiB DSP-Belegung weitere 25 MiB; dafür fehlen dort schon 323584 Byte,
noch ohne Index und Verwaltung.

Der scheinbar freie Bereich darunter überlappt den offiziell gemeldeten
Arbeitspuffer `[0xC0D3A940, 0xC273AA40)`, den Startstack und die IRQ-Stacks.
Die Canary-Messung allein hebt deren Besitz nicht auf. Nur den 4-KiB-Block
`0xC274E000` auszusparen wäre unzureichend. Ein späterer Patch muss entweder
mit dem oberen Bereich auskommen oder die übrigen Pufferwege gesondert klären.

**Hergeleitet:** Ein Cache erweitert die auswählbare Bank, nicht den gleichzeitig
spielbaren DSP-Inhalt. Alle benötigten Samples samt noch ausklingender Stimmen
müssen weiterhin in dessen Nutzerbereich passen. Auch Fragmentierung, ein
einzelnes zu großes Sample und fehlender verdrängbarer Platz brauchen vor dem
Bau eine definierte Behandlung.

## Gerätetests

Werkzeug: [sample_swap_probe.py](../../tools/device/sample_swap_probe.py).
Ohne `--execute` entsteht nur ein Offline-Plan. Der echte Test braucht eine
aktuelle BLECH-Firmware auf dem roten Sampler, USB und die unveränderte eigene
Sampler-2.02-Datei für den Vergleich der benötigten Routinen. Stock ohne BLECH,
unbekannte Builds und der blaue Synth werden nicht als unterstützt behandelt.

Der Zielslot muss ein selbst erzeugtes, entbehrliches Sample enthalten und
mindestens die angeforderte PCM-Länge besitzen. Er darf von keinem Part,
ausklingender Stimme oder anderer Funktion benutzt werden. Keine Aufnahme,
kein Import, Export oder Speichern gleichzeitig. Die Probe ruft ausschließlich
RAM- und DSP-Funktionen auf, keine Karten- oder Flash-Schreibfunktion.

Vorbereitung ohne Gerätekontakt, im Repository aufrufen:

```bash
PYTHON=tools/emu/.venv/bin/python
"$PYTHON" -m pip install mido python-rtmidi
"$PYTHON" tools/device/sample_swap_probe.py --plan --slot 501 --kib 64
"$PYTHON" tools/device/sample_swap_probe.py --make-wav "$HOME/sample-swap-probe.wav" --kib 64
```

Die erzeugte WAV enthält ausschließlich berechnete 16-Bit-Monodaten mit
44100 Hz, 65536 Byte PCM. Das Werkzeug verweigert ihre Ausgabe innerhalb
eines Git-Repositories. Die Datei danach selbst mit dem normalen Import in
einen freien Nutzerplatz laden. Die Beispiele nehmen den angezeigten Slot
501 an; bei einem anderen Platz `--slot` anpassen. Nicht den Zielslot spielen.

1. **Gestoppt beginnen:** Samplemodus verlassen, Aufnahme und Wiedergabe stoppen,
   ausklingende Stimmen abwarten. Eigene Originaldatei als `SAMPLER_VSB` angeben.
   Zunächst nur 1 KiB testen:

   ```bash
   "$PYTHON" tools/device/sample_swap_probe.py --execute --vsb "$SAMPLER_VSB" --slot 501 --kib 1 --unused-confirmed --stopped-confirmed --json "$HOME/swap-stopped-1.json"
   ```

   Nur wenn die Ausgabe erfolgreiches Rücklesen und unveränderte Tabellen
   bestätigt, jeweils einzeln 4, 16 und 64 KiB mit eigenen Ergebnisdateien
   messen. Bei fehlender Antwort abbrechen und das Gerät neu starten. Das
   Werkzeug wiederholt Execute nicht und sendet keine Bereinigung, solange
   ein ARM-Aufruf noch laufen könnte.

2. **Andere Stimmen aufnehmen:** Auf anderen eigenen synthetischen Samples
   mehrere Parts spielen, darunter gehaltene Töne und regelmäßig neue Noten.
   Audio und nach Möglichkeit ein gemeinsames MIDI-Zeitzeichen extern aufnehmen.
   Einmal ohne Probe als Vergleich, dann die gleichen Größen mit
   `--playback-confirmed` statt `--stopped-confirmed` einzeln ausführen:

   ```bash
   "$PYTHON" tools/device/sample_swap_probe.py --execute --vsb "$SAMPLER_VSB" --slot 501 --kib 1 --unused-confirmed --playback-confirmed --json "$HOME/swap-playing-1.json"
   ```

   Für jede Größe mindestens fünf erfolgreiche Einzelmessungen mit eigenen
   Dateinamen aufheben. Danach dieselbe Aufnahme mit Patternwechseln auf den
   anderen Parts wiederholen. Den Zielslot in keinem Pattern verwenden. Bei
   Aussetzern, verspäteten Noten, einer Fehlermeldung oder einer fehlenden
   Antwort keine größere Probe anschließen. Das Aufnahmeprotokoll soll
   Firmware-Build, BLECH-Version, Größe, Zeit, Zahl der aktiven Parts und die
   beobachteten Aussetzer oder Notenverzögerungen nennen.

**Was die Probe prüft:** Firmwareprofil und benötigte ARM-Routinen werden mit
der eigenen Datei verglichen. Der belegte DSP-Bereich muss ausgerichtet sein
und vollständig vor dem aktuellen Frei-Zeiger liegen. Slotzuordnung,
Metadaten, Wiedergabeeintrag, Name und Zeiger werden vor und nach der Probe
verglichen. Die ausdrückliche Bestätigung der Nichtbenutzung bleibt nötig;
die Probe kann aktive oder ausklingende DSP-Stimmen nicht selbst ausschließen.

Zwei DSP-Lesevorgänge in verschieden vorgefüllte CPU-Puffer müssen zunächst
identische Originaldaten liefern. Der zweite Puffer wird danach wortweise
mit `0x01010101` XOR-verändert. Nur dessen Schreiben wird mit Timer 3
gemessen. Rücklesen muss genau diese geänderten Bytes ergeben. Danach werden
Originalbytes zurückgeschrieben und noch einmal gelesen. Ein undefinierter
Rückgabewert der Firmware wird nicht als Erfolg benutzt.

**Grenzen und Wiederherstellung:** Die 688 Byte große ARM-Routine liegt bei
`0xC1000000`, zwei Puffer zu höchstens 64 KiB bei `0xC274F000` und
`0xC275F000`. Diese Puffer müssen vorher vollständig null sein. IRQs bleiben
an; der vorhandene Task-Pfad mit Sperren wird verwendet. Nach erfolgreicher
Wiederherstellung werden beide Puffer genullt und der vorherige Stubinhalt
zurückgeschrieben. Bei ungeklärter Wiederherstellung bleibt die Sicherung ab
`0xC274F000` erhalten; nicht erneut starten oder manuell weiterschreiben,
sondern Gerät neu starten. Die Samples auf der Karte bleiben unberührt.

Timer 3 wird nur gelesen: Zähler bei `0x01F0D010`, Periode bei
`0x01F0D018`, 150 MHz gemäß dem vorhandenen Gerätetest
[timing_probe.py](../../tools/device/timing_probe.py). Kontinuierlicher Betrieb
und eine ausreichend lange Periode sind Pflicht. OS-Tick und gemessene
USB-Aufrufdauer begrenzen die Auswertung: mehrdeutige Intervalle, eine
überschrittene Timerperiode oder mehr als 500 ms werden nicht als Durchsatz
gemeldet. USB-, Sicherungs- und Rücklesezeit gehören nicht zur gemeldeten
Transferzeit; Sperrwartezeit innerhalb des Schreibwrappers dagegen schon.

**Offen bleibt auch bei erfolgreicher Ausgabe:** Klang, Notenlatenz und
physische DSP-Grenze. Das JSON meldet deshalb `audio_verified: false` und
`limit_verified: false`. Es enthält weder PCM noch Firmwarebytes. Ohne die
externe Aufnahme gibt es keine Aussage zur Wiedergabe beim Schreiben.

Eine vollständige Probe enthält vier Lese- und zwei Schreibtransfers. Die
gemeldete Zeit gehört nur zum ersten Schreiben. Eine Störung in der Aufnahme
kann auch beim Sichern, Rücklesen oder Wiederherstellen entstehen; sie belegt
zunächst nur, dass die gesamte Probe die Wiedergabe stört. Für eine spätere
gezielte Ursachenmessung müssen die einzelnen Aufrufe getrennt markiert werden.

Der Vergleich mit der Originaldatei umfasst getrennt `0xC00141F8` plus
`0xD10` Byte, den Lesewrapper `0xC004EDDC` plus `0x14` Byte und den
Schreibwrapper `0xC004EF28` plus `0x6C` Byte. Die benachbarten Haken des
vorhandenen Sample-Fehler-Patches gehören nicht dazu. Ein Regressionstest
akzeptiert die Änderung bei `0xC004EE0C`, verweigert aber eine Änderung im
Schreibwrapper bei `0xC004EF7C`, bevor ein Upload erfolgt. Auch die 434
Änderungen der 23 Dateien des regulären BLECH-Patchsatzes wurden gegen diese
Bereiche geprüft: keine Überschneidung. Unbekannte Änderungen innerhalb der
drei aufgerufenen Bereiche bleiben ein Abbruchgrund.

## Prüfbefehle

Die Originaldateien bleiben außerhalb des Repositories. `E2_VSB` und
`E2_EMU_PYTHON` zeigen auf die eigenen lokalen Dateien beziehungsweise die
Python-Umgebung aus [Entwicklung](../development.md).

```bash
E2_VSB="$SAMPLER_VSB" node --test test/emulator-sample-swap.test.mjs
"$E2_EMU_PYTHON" tools/emu/sample_swap_cases.py --vsb "$SAMPLER_VSB"
node --test test/sample-swap-probe.test.mjs
npm test
npm run test:e2e
```

Bei begrenzter Rechnerleistung die Tests wie in der Entwicklungsanleitung
nacheinander mit begrenzter Parallelität ausführen:

```bash
GELUMPE_JOBS=2 npm test -- --test-concurrency=1
npm run test:e2e -- --test-concurrency=1
```

## Ergebnisse der lokalen Prüfung

**Gemessen am 25.10., ohne Gerät:**

| Prüfung | Ergebnis |
|---|---|
| `npm test`, Parallelität wie oben begrenzt | 1022 bestanden, 148 übersprungen, keine Fehler, keine Abbrüche |
| `npm run test:e2e`, Dateien nacheinander | 183 bestanden, eine übersprungen, keine Fehler, keine Abbrüche |
| Originale Allocator-Routinen mit eigener Stock-Datei | acht Prüfungen bestanden |
| Originale Allocator-Routinen mit eigener Hacktribe-Datei | acht Prüfungen bestanden |
| Gerätetest-Werkzeug gegen selbst gebaute Daten | 21 Python-Prüfungen bestanden, einschließlich Ausführung der eigenen ARM-Routine |
| Dokumentation und Node-Einbindung des Werkzeugs | zehn Prüfungen bestanden |
| Python-Syntax und `git diff --check` | bestanden |

Die übersprungenen Tests sind keine Bestätigung weiterer Firmware- oder
Hardwareeigenschaften. Die neuen Allocator-Versuche wurden deshalb zusätzlich
gezielt mit den beiden eigenen Dateien ausgeführt. Die ARM-Prüfungen des
Gerätetests ersetzen nur dessen DSP-Lese- und Schreib-APIs durch einen
selbst gebauten Speicher. Sie messen keinen echten Port und keinen Klang.

Der erste Testlauf hatte in der neuen Arbeitskopie noch keine Unicorn-Umgebung;
außerdem lief die parallele Browserprüfung in die bestehende Zeitgrenze.
Nach Installation der vorhandenen Emulator-Abhängigkeit und begrenzter
Parallelität bestanden die oben genannten abschließenden Läufe. Dafür wurden
keine Produktfunktionen oder Testzeitgrenzen verändert.

**Offen:** Kein Gerätetest, keine 50-MB-Datei auf dem Gerät, kein Klangtest und
kein Swap-Patch. Phase 2 bleibt bis zu den Messwerten angehalten.

## Gerätemessung 25.10.

**gemessen** am roten Sampler, Hacktribe 2.02 mit BLECH, über USB am Linux-Laptop (ALSA, `mido`). Zielplatz 645
(ein vorhandenes Nutzer-Sample mit 115346 Byte PCM, DSP-Offset `0x8E4F40`, identische Zuordnung), in keinem
gespielten Pattern benutzt (Pattern-Bank im RAM gelesen, Sample-ID bei `0x808` je Part). Alle 499 Nutzerplätze
waren belegt, ein synthetisches Sample ließ sich nicht importieren. Die Probe stellt die Bytes wieder her und
prüft sie, die Karte bleibt unberührt.

| Größe | gestoppt (je 3 Läufe) | beim Abspielen, Pattern 020 (5 Läufe) |
|---|---|---|
| 1 KiB | 0,080 bis 0,091 ms | |
| 4 KiB | 0,313 bis 0,338 ms | |
| 16 KiB | 1,327 bis 1,440 ms | |
| 64 KiB | 5,433 bis 5,455 ms (11,5 MiB/s) | 5,451 bis 6,276 ms (10 bis 11,5 MiB/s) |

Jeder Lauf: Bytes nach dem Wiederherstellen gleich, Metadaten, Wiedergabeeintrag, Name, Zeiger und Zuordnung
gleich. Hörbar beim Abspielen: nach Aussage am Gerät nur bei gezieltem Hinhören eine ganz kurze Verzögerung,
"hättest du mir nicht gesagt, dass ich darauf achten soll, wäre es mir nicht aufgefallen". Keine Aufnahme.

**Korrekturen an der Probe:**

- Die Periode von Timer 3 steht am Gerät auf 149999999 (der Zähler läuft von 0 bis PRD, also 150 MHz). Die Probe
  verlangte mindestens 150000000 und brach so vor jedem DSP-Zugriff ab. Jetzt `TIMER_HZ - 1`.
- Die Puffer bei `0xC274F000` und `0xC275F000` waren nach dem Einschalten nicht null, sondern zeigten das Muster
  nie beschriebenen RAMs (vereinzelte gesetzte Bits, in beiden fast gleich). Sie wurden vor dem Test per BLECH
  WRITE in 2-KiB-Blöcken genullt.
- ALSA am Linux-Laptop verschickt keine SysEx-Nachricht mit 32 KiB (`MidiOutAlsa::sendMessage`); die abgebrochene
  Nachricht ließ das Gerät mit "MIDI receive error" zurück. 2 KiB gehen.

**offen, ein gelegentlicher Hänger:** Dreimal kam auf EXEC keine Antwort mehr und das Gerät musste neu gestartet
werden: einmal direkt nach der abgebrochenen 32-KiB-Nachricht, dann zweimal mit dem vollen Testcode der korrigierten
Probe, jeweils in einer anderen Sitzung nach dem Einschalten. Danach liefen derselbe Testcode und alle Teilschritte
(Lesen und Schreiben bis 512 Wörter, in beide Puffer, nacheinander in einem Lauf, mit geänderten Bytes) in über 20
Läufen ohne Hänger, darunter die 17 Messläufe oben. Die Ursache ist nicht gefunden; der Host-Port-Pfad wartet ohne
Zeitgrenze (Abschnitt 3). Ein Swap-Patch braucht dort eine Zeitgrenze oder einen Weg, der nicht aus EXEC kommt.

## Kartenlesen am Gerät, 25.10.

**gemessen** am selben Gerät: ein Testcode öffnet `SD:KORG/blechtribe/Sample/e2sSample.all` mit der FatFs der
Firmware (`0xC009DB60`, Modus 1), liest vom Anfang in festen Blöcken nach `0xC274F000` (FIL bei `0xC275F000`),
schließt die Datei und misst mit Timer 3 und dem OS-Tick (beide gleich). Nur Lesen, über EXEC. Pattern 020 lief
dabei weiter.

| gelesen | Blockgröße | Zeit | Durchsatz |
|---|---|---|---|
| 256 KiB | 32 KiB | 84 ms | 3048 KiB/s |
| 2 MiB | 32 KiB | 657 ms | 3117 KiB/s |
| 2 MiB | 64 KiB | 662 ms | 3094 KiB/s |
| 256 KiB | 4 KiB | 116 ms | 2226 KiB/s |

**hergeleitet:** Die 157 KB/s aus dem Emulator (Abschnitt 3) gelten nicht für das Gerät; dort liest die Karte rund
zwanzigmal schneller. 10 MB brauchen von der Karte gut 3 s, aus einem RAM-Cache in den DSP rund 1 s.
