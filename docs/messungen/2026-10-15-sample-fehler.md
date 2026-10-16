# Sample-Fehler: ein Sample überspringen und sagen, welches

Stand 2026-10-15. Kein Gerätezugriff, alles im Emulator, mit Korgs Original 2.02 und mit Hacktribe, jeweils mit dem
eigenen Flash-Abbild. Die Samples sind eine Formel (`tools/emu/sampleset.py`), kein Korg-Sample.

## Was die Firmware tut

Beim Start liest sie `e2sSample.all` und lädt Sample für Sample. Die Schleife des Laders (`0xC00364F0`, beide Builds
gleich) fragt je Eintrag der Tabelle die Sample-Funktion (`0xC0035B10`), und bei einem Ergebnis ungleich 0 endet sie. Die
Eingaben danach werden nicht mehr geladen. Das Fenster dazu ist `Error` mit einer Zeile, die die Fensterklasse
(`0xC0063068`) aus einer Tabelle von 35 Texten holt, sonst "Unknown Error.". **gemessen** (Disassembler, Emulator)

| Code | Wann | Fenster der Firmware |
|---|---|---|
| 32 | die Kopfprüfung weist die Datei ab: kein RIFF/WAVE, kein `fmt ` oder `data`, Format nicht 1 (PCM), mehr als 2 Kanäle, Bits weder 16 noch 24 | "Format Error." |
| 33 | das Sample ist länger als der freie DSP-Speicher | "Memory Full" |
| 36 | die Funktion, die das Sample in seinen Platz einträgt (`0xC004EDF0`), lehnt ab: der Platz ist belegt, er hat eine Kategorie, die kein Sample tragen darf, oder das Sample ist länger als der freie Speicher | "Unknown Error." (alles über 35) |
| 4 | Lesefehler der Karte | "Card Error" |

24 Bit nimmt der Lader (PCM, 1 oder 2 Kanäle, er wandelt auf 16 Bit); gemessen mit einem Sample von 24 Bit und eines
mit der Länge in 24-Bit-Bytes im Satz (`pcm24`, `pcm24L`): beide laden. 8 Bit, 32 Bit und Fließkomma ergeben 32, also
"Format Error." **gemessen** Das 24-Bit-Sample auf Platz 371, das bei einem Lauf mit "Unknown Error." stehen blieb, ließ sich
so nicht nachstellen: "Unknown Error." ist nach dem Code ein Platz, den die Firmware nicht eintragen konnte (belegt, nicht
nutzbar, zu lang für den freien Speicher), kein Bitformat. Welcher der drei es dort war, ist **offen**.

Der Lader hat eine zweite Aufrufstelle (`0xC0038E0C`). Die Haken sitzen im Lader selbst und gelten dort ebenso; im Emulator ist nur der
Weg beim Start geprüft.

## Der Patch `sample-errors`

`tools/patch/sample_errors.py`, `data/patches/sample-errors.json`, beide Builds (die Stellen sind Byte für Byte gleich).
Statt auf dem ersten Sample zu enden, überspringt der Lader eines, das er mit **32 oder 36** abweist, und lädt das nächste.
Beide Codes kommen aus der Sample-Funktion, bevor sie etwas verändert hat (nichts eingetragen, kein DSP-Speicher belegt, die
Datei wird für jeden Eintrag neu angefahren), das Überspringen ist also sicher. **hergeleitet** aus dem Code, im Emulator
bestätigt: die übrigen Samples laden vollständig. Jeder andere Code (Lesefehler, "Memory Full") beendet das Laden wie vorher.

Am Ende der Schleife gibt der Lader den Code `0x40` zurück, wenn etwas übersprungen wurde. Die Fensterklasse kennt ihn nicht,
zwei Haken geben ihm unsere zwei Zeilen: die Überschrift nennt den Platz, die Zeile darunter den Grund.

| Zeile 1 | Zeile 2 | Grund |
|---|---|---|
| `Sample 502` | `8 bit, use 16/24` | Bits weder 16 noch 24 (die Zahl wird eingesetzt) |
| | `not PCM, tag 3` | Formatnummer ungleich 1 (3 ist Fließkomma) |
| | `3 channels, max 2` | mehr als 2 Kanäle |
| | `slot in use` | der Platz ist belegt (die Firmware: 36) |
| | `slot not usable` | der Platz hat keine Kategorie, die ein Sample tragen darf (36) |
| | `too big for memory` | länger als der freie Speicher (36) |
| | `bad WAV file` | Kopf unlesbar (32 ohne genaueren Grund) |
| | `cannot be loaded` | 36 ohne genaueren Grund |

Die Nummer ist die Stelle in der Tabelle der Datei plus eins, so wie sie im Gerät und im Export steht. Genannt wird das erste
übersprungene Sample, die Zahl der weiteren steht nirgends. Das Fenster ist das der Firmware, es bleibt, bis EXIT es schließt.
Die Texte sind englisch wie alle Fenster der Firmware; die zweite Zeile hat Platz für rund 18 Zeichen.

Die elf Haken: Der Anfang des Laders (`0xC00364F0`, leert den Zustand), drei Verzweigungen der Sample-Funktion,
die ein Format abweisen (`0xC0035FB4`, `0xC0035FC4`, `0xC0035FD4`: merken Art und Zahl), drei der Eintragsfunktion
(`0xC004EE0C`, `0xC004EE50`, `0xC004EE68`), der Befehl hinter dem Aufruf der Sample-Funktion (`0xC0036700`: zählt und geht
weiter), das Ende der Schleife (`0xC0036714`: baut die Zeilen, gibt `0x40` zurück) und die zwei Aufrufe, die die Textobjekte des
Fensters bauen (`0xC00630F0`, `0xC0063144`). Die Kette heißt `sample-errors` (`data/hooks.mjs`). Code `0xC0183000` bis
`0xC0183700` (852 Byte belegt), Zustand und die zwei Zeilen `0xC0183800` bis `0xC0183900`, nur RAM, im freien Block vor
Blechys Block. Mit EXIT beim Einschalten springt jeder Haken sofort zum Original. Der Code läuft in der Startphase
(`startPhase` nennt jede Stelle).

## Im Emulator geprüft

`tools/emu/sample_error_cases.py`, von `check.py` auf jeder Kopie mit den Haken gerufen, auf beiden Builds mit dem Flash-Abbild
(`test/sample-errors.test.mjs`, `npm run test:emu`):

- **überspringen:** zwischen guten Samples drei, die der Lader abweist (8 Bit, Fließkomma, 32 Bit): alle guten laden, das Fenster
  nennt `Sample 502` und `8 bit, use 16/24`, gezählt sind drei; Stereo und 24 Bit zwischen ihnen werden genommen;
- **Gründe:** Fließkomma ("not PCM, tag 3"), ein Platz, den zwei Einträge beanspruchen ("slot in use"), eine Datei, die keine
  WAV ist ("bad WAV file"), jeweils mit dem Sample dahinter geladen;
- **sauber:** 16 Bit, 24 Bit und Stereo: kein Fenster, nichts gezählt;
- **EXIT beim Einschalten:** wie vorher, das Laden endet beim ersten schlechten Sample, nichts gezählt, die Zustandswörter
  bleiben unbeschrieben;
- **Werksplätze, leerer Flash:** siehe unten (nur Korgs Build).

`check.py` mit dem Flash-Abbild auf dem ganzen BLECH-Satz mit dem Patch: Hacktribe 303 von 303 Prüfungen, Korgs Build 328 von 328
(darunter je 12 des Patches). **gemessen**

## Der leere Flash des Emulators bekommt eine Werksbank

Mit einem gelöschten Flash zeigten alle Werksplätze auf denselben Eintrag der Tabelle (Index 0), das zweite Sample für einen
Werksplatz wurde als "slot in use" abgelehnt, also mit "Unknown Error." (Samples auf den Plätzen 150, 250 und 350: nur eines
lud). Mit dem Flash-Abbild laden alle, jedes in seinen Eintrag (140, 240, 340). **gemessen**

Was die Firmware dafür braucht, ist die Werksbank bei Flash `0x800000` ([Struktur](2026-10-07-werks-sample-flash.md)):
die Tabellen, nicht das Audio. Eingrenzung im Emulator (Teile des Abbilds in einen leeren Flash kopiert, nur zur Messung,
nichts davon im Repository): Kopf, die Abschnitte DRMP und DRUM, MSPR, MSRL, MSVS und SMPR sind alle nötig, SMPL und das
Audio nicht; fehlt MSVS oder MSRL, fehlt DRMP oder DRUM, bleibt es bei Index 0 oder die Firmware liest ins Leere (der Emulator
meldet einen Lesefehler). Der Abschnitt MSVS hat in seinem Kopf als einziges Wort hinter der Zahl der Einträge eine 1, nicht FF. **gemessen**

`tools/emu/factorybank.py` baut eine Bank mit demselben Aufbau und denselben 411 Einträgen, ohne Korg-Daten: die Namen heißen
`Fac001` bis `Fac411`, Nummern und Längen sind Formeln, kein Audio. `machine.blank_flash` legt sie bei `0x800000` in jeden
leeren Flash (`tools/emu/test_factorybank.py`). Damit laden Korgs Build und der leere Flash dieselben Werksplätze wie mit dem
Abbild: 4 von 4 (Plätze 150, 250, 350, 500). **gemessen**

**Hacktribes Build** lehnt die meisten Werksplätze auch mit dem Abbild ab (Plätze 150 und 250 nicht, 350 ja; ohne Patch bricht
das Laden am ersten ab). Das ist nicht der Flash, es ist der Build: Hacktribe belegt die Namen der Werksplätze neu. Dort gibt es
nichts zu beheben, die Prüfung der Werksplätze gilt nur für Korgs Build. **gemessen**

## Am Gerät offen

Alles: ob das Fenster am Gerät so aussieht (die Texte sind im Emulator am Display gelesen), ob die Zeile 2 breit genug ist,
ob das Überspringen einer Probe mit echten 24-Bit-Samples auf den Werksplätzen standhält, und welcher der drei Gründe das
"Unknown Error." des 24-Bit-Samples auf Platz 371 war.
