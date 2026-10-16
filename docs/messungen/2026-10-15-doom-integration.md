# Doom mit aktuellem BLECH integrieren

Historischer Zwischenstand, ersetzt durch [Doom auf BLECH v21](2026-10-15-doom-v21.md).

Stand: 15.10.2026. Die abgeschlossenen Prüfungen liefen vollständig im Emulator.
Kein Schreiben, Flashen oder Ausführen auf einem echten Gerät.

## Basis

Codebefund: Der frühere Teststand beruhte auf BLECH v8. Er enthält die
späteren BLECH-Erweiterungen nicht und gilt nur als historische Messung.
Die Basis dieser Anpassung ist `integ/overnight`, zunächst `5b52db6`.
Der separat entwickelte SysEx-Patch liegt auf `feat/blech-ram-sysex`,
Stand `522e055`. Ein endgültiger v21-Build ist damit noch nicht belegt.

## Speicher

Codebefund aus den Patch-Deklarationen und dem SysEx-Quellstand:

| Bereich | Belegung |
|---|---|
| `0xC0172100..0xC0180000` | SysEx-Code, Schutztabelle, Zustand und Puffer |
| ab `0xC0180000` | Patternwechsel und Ladebalken |
| `0xC0182000..0xC0183000` | Startbild-Editor |
| `0xC0184000..0xC0188000` | Blechy |
| ab `0xC0188000` | TAP-Motion |
| `0xC0189000..0xC0189F40` | Note-Assistent |
| `0xC0190000..0xC0190100` | Synth-Filter |
| `0xC0191000..0xC0199000` | neuer Doom-Lader, 32 KiB Reserve |
| `0xC0199000..0xC019E000` | neuer Doom-Laderzustand, 20 KiB Reserve |
| `0xC019E000..0xC019F000` | gemeinsame Doom-Daten, 4 KiB Reserve |
| ab etwa `0xC01A2100` | Plugin-Laufzeit und zugehörige Erweiterungen |

Hergeleitet: Das alte Doom-Layout kollidiert sowohl mit SysEx als auch
mit Pattern-Switch. Nur den Code zu verschieben reicht nicht, weil die
alte gemeinsame Adresse `0xC0180000` ebenfalls belegt ist.

Gemessen durch `test/doom-layout.test.mjs`: Die alten Kollisionen werden
abgelehnt; die neuen Bereiche passen zu den aktuellen Deklarationen.
Eine zukünftige Belegung im neuen Code- oder Zustandsbereich wird ebenfalls
abgelehnt. Das prüft `checkRam` und `checkRamPlacement` aus der zentralen
Speicherprüfung, zusätzlich zu den FF-Bytes des konkreten Basisabbilds.

## Herkunft und ABI

Codebefund: Der Laderbau rekonstruiert die Basis vollständig aus dem
hashgepinnten Original und dem aktuellen Patchsatz. Ein Vergleich aller
Bytes verhindert, dass eine veraltete Basis über einen bloß freien
Doom-Bereich akzeptiert wird. Zusätzliche Patches gehören zum selben
Wiederaufbau. Unbekannte Haken bleiben Fehler.

Gemessen durch die Laderprüfungen: Ein gekürztes oder verändertes Abbild,
eine alte v8-Basis und eine Engine mit alter gemeinsamer Adresse werden
abgelehnt. Neue Engine und Lader verwenden gemeinsam `0xC019E000`.

## Prüfstand

Gemessen am Integrationsstand `5b52db6` mit umgezogenem Doom-Lader:

- `npm test -- --test-concurrency=2`: 806 bestanden, 125 ausdrücklich
  übersprungen, kein Fehler. Darin läuft der neue ARM-Adaptertest.
- `npm run test:e2e -- --test-concurrency=2`: 146 bestanden, keine
  Überspringung und kein Fehler.
- `E2_VSB=SYSTEM.VSB node --test test/patch-ram.test.mjs`: zwölf bestanden,
  keine Überspringung und kein Fehler. Die Variable zeigt auf das eigene
  Ausgangsabbild, weil die Prüfung FF-Reserven in der ungepatchten Basis verlangt.
- TAP-Kompatibilität der echten Doom-Firmware: elf Einträge bestanden.
  Belegt sind Ein-/Ausschalten von Motion im laufenden Takt, unveränderte
  Kopie des Zustands, Wegfall von Tap-Tempo, SHIFT+TAP als BPM-Seite und
  Tastenerfassung der App. Dazu wurden die bestehenden Emulatorfälle
  ausgeführt, keine Ersatzlogik für die Tasten eingeführt.

Gemessen im abschließenden nativen Lauf: drei Pflichtprüfungen bestanden,
keine Überspringung. Der Spielteil besteht 17 Bedienprüfungen, erzeugt
261 Frames und erreicht 160 Spielticks. Quit endet mit STOPPED und
Fehler null; der Powerknopf schaltet das emulierte Gerät aus.
Die Start-/Fehlerregression besteht 34 von 34 Einträgen. Alle drei
Randwächter bleiben intakt; keine Assertion und kein SD-Schreibaufruf.
Der Inhalt der virtuellen Karte bleibt unverändert.

Der gemessene Heapverbrauch beträgt 6646032 Byte. Die simuliertermaßen
verstrichenen 68,6145 Sekunden und die 270,77 Sekunden Hostlaufzeit
sind keine Messung der realen Gerätebildrate. Ein gemeinsamer SysEx-Lauf wartet gemäß der Entscheidung vom 15.10.2026
auf die fertige v21-Integration. Die separaten Haken werden nicht übernommen.
Der erste unbeschränkte Gesamtlauf hatte Zeitüberschreitungen unter
paralleler Last; im Browser fehlte zusätzlich eine Testabhängigkeit.
Die Wiederholung verwendet isoliert installierte Abhängigkeiten und
begrenzte Testparallelität.

## Quellen und Gerät

Der [Lizenzbefund](2026-10-15-doom-lizenzen.md) hält die unterschiedlichen
GPL-Angaben der verlinkten Engine-Dateien fest. Der neue Build sichert
die passenden Quellen. Eine Freigabe zur Binaryweitergabe ist daraus
noch nicht abgeleitet.

Das alte Paket `SYSTEM-blech-doom-v1.VSB` ist als veraltet gekennzeichnet.
Ein neuer Hardwaretest wird erst auf Basis des endgültig geprüften
Integrationsstands vorbereitet. Hardware, Ton und reale Bildrate bleiben
offen.

## Reproduzierbarkeit

Gemessen: Das separat entpackte Quellenarchiv baut ohne Git-Metadaten
und ohne Netz mit derselben Werkzeugkette eine identische Engine.
Das Archiv enthält alle lokalen Adapterheader, vollständige Enginequellen,
Bauanleitung, Neubauskript und Dateihashes. Compiler-Prefix-Maps halten
`__FILE__` unabhängig vom lokalen Quellpfad.

- Engine: 450492 Byte.
- Engine-SHA256:
  `ecf71d0ae826f50cf7a3bb6a12438269b4c8623dedd3f7e17b74aa1d68642bba`.
- Archiv-Neubau: identischer SHA256.

Gemessen im ersten Zwischenbuild nach dem Speicherumzug: Doom besteht
17 Bedienprüfungen bis Quit und Ausschalten. Die folgende Startregression
fand noch die alten Adressen in ihrem eigenen Referenzvergleich.
Der Vergleich verwendet jetzt den gemeinsamen Layoutplan; ein zusätzlicher
Test lehnt Änderungen außerhalb der neuen Reservierung ab.
Der abschließende Gesamtlauf besteht mit dem oben genannten
reproduzierbaren Enginebuild.

Die Firmwarebasis hat SHA256
`6ea176fbcfaa72f9066e0359a20031e070641c6c5c7c585a0619489e5d7da8d7`.
Das neue Doom-Abbild hat SHA256
`d017d4816f9af3397af412eeed468378c9e53d744b07f41ccf23b8ca2ee31e99`.
Der Lader umfasst 2732 Byte innerhalb seiner 32-KiB-Reserve.

Codevergleich: Der spätere Integrationsstand `0f1d142` hat dieselben
Firmwarepatches, Patchwerkzeuge, Haken und Speicherdeklarationen.
Die seit `5b52db6` hinzugekommenen Änderungen betreffen die Oberfläche.
SysEx ist in beiden eingefrorenen Integrationsständen noch nicht enthalten.
Eine gemeinsame SysEx-/Doom-Freigabe und eine v21-Freigabe bleiben offen.
Die Entscheidung vom 15.10.2026 lautet, auf die v21-Integration zu warten.
Die beiden separaten SysEx-Haken werden deshalb nicht vorab übernommen.

Die abschließende Codeprüfung fand keine offenen blockierenden Befunde.
Die dabei gefundene Quellenpaketlücke wurde behoben und durch den
bytegleichen Neubau geprüft.

Die fünf passenden Speicherplatzierungs-/FF-Prüfungen aus
`test/patch-ram.test.mjs` bestehen auch am fertigen Doom-Abbild.
Der vollständige Aufruf auf diesem bereits gepatchten Abbild scheitert
am Fall, der alle BLECH-Patches erneut anwenden will; dieser benötigt
das ungepatchte Ausgangsabbild und besteht damit. Für den Kandidaten
werden deshalb ausdrücklich nur die passenden Speichertests gewählt.
