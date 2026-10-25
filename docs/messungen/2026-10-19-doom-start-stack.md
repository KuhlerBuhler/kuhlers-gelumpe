# Doom: Stack am Lader-Einstieg und sichtbarer Start

Stand 19.10.2026. Kein Firmware-Update und kein Schreiben am Gerät durch
Rechnerbefehle. Markierungen: gemessen, aus Code gelesen, offen.

## Ausgangsstand

Am Gerät gemeldet: SHIFT + TAP beim Einschalten bleibt beim BLECH-Bild.
Die installierte batch3-Datei hat SHA-256
`99dc65bfa5321310f4edaa666f2baef422672ca3b7ecd0cac5afcabbdcdd291d`.
Ihre Laderbytes und der Einstieg entsprechen dem aktuellen Patch.

Aus Code gelesen: Der Einstieg liegt bei `0xC002AE64`, direkt nach der
Abfrage der Sample-Datei. Diese Abfrage ist kein ausdrücklich erfolgreich
abgeschlossenes Einhängen der Karte. FatFs kann das registrierte Volume erst
beim Dateizugriff einhängen. Der vorhandene Lader versucht das Öffnen von
`doom.bin` deshalb höchstens sechsmal mit 500 Millisekunden Abstand.

## Nachgewiesener Fehler

Gemessen mit dem eigenen ARM-Code und synthetischem RAM: Bei einem auf acht
Byte ausgerichteten Startstack sichert der alte Einstieg sechs Register und
danach ein Register mit den Statusflags. Die 28 Byte verschieben SP auf
Rest vier bei Division durch acht. So springt er in den C-Lader.

Zusätzlich im vollständigen Firmwarestart mit derselben Karte gemessen:
Der alte C-Einstieg erhält SP `0xC0202364`, der korrigierte
`0xC0202360`. Damit ist der Versatz auch im Startpfad der installierten
Firmware vorhanden, nicht nur im isolierten Test.

Das verletzt die Stackvorgabe für eine öffentliche C-Schnittstelle aus
[Arm AAPCS32](https://github.com/ARM-software/abi-aa/blob/main/aapcs32/aapcs32.rst#stack-constraints-at-a-public-interface).
Der neue Test scheitert am alten Patch mit `4 != 0`. Der Einstieg sichert
Statusflags und ein weiteres Register zusammen. Die 32 Byte erhalten die
Ausrichtung. Auf dem normalen Rückweg bleiben Register, Stack und Flags
bis auf das ersetzte `mov r4, r0` unverändert.

Dies ist ein nachgewiesener Fehler im Lader. Ob er den gemeldeten Hänger am
Gerät vollständig erklärt, ist offen. Ein erfolgreicher Emulatorlauf
belegt keine Ausrichtungsausnahme auf dem Gerät.

## Sichtbarer Start

Aus Code gelesen: Vor dem ersten Engine-Bild gab es bisher keine Ausgabe.
Das alte BLECH-Bild blieb auch während erfolgreicher Datei- und
Engineinitialisierung stehen. Der Lader sendet jetzt über den vorhandenen
Displaytreiber:

- `DOOM`, `BOOT` vor den eigenen Initialisierungsaufrufen.
- `DOOM`, `READ` und den gelesenen Bytezähler in Hexadezimaldarstellung beim
  Laden des Programms, alle 32 KiB und am Dateiende.
- `DOOM`, `START` nach erfolgreicher Größen- und SHA-256-Prüfung, bevor die
  unveränderte Engine startet.

Die vorhandenen Fehlercodes und die Ausschaltbehandlung bleiben erhalten.
Die Engine und die WAD werden nicht geändert. Ein neues Firmware-Abbild
passt weiterhin zu derselben `doom.bin` mit SHA-256
`17025aae03ef2eb05a9990774c0882f3298b6c0efc54a7173e7dbc6b30373078`.

## USB-Diagnose

Gemessen auf dem angeschlossenen Linux-Rechner: Im gemeldeten Zustand gibt
es keinen Electribe-Eintrag in USB und keinen Electribe-MIDI-Port. Aus Code
und Tasktrace gelesen: Der getrennte Doom-Zweig startet nur Tasks 1 und 8,
nicht die USB- und Command-Tasks. Das vorhandene `doom_probe.py` kann diesen
Start deshalb nicht über BLECH-READ untersuchen. Seine Beschreibung nennt
diese Grenze jetzt ausdrücklich. Es wird kein Hintergrundtask nur für eine
vermeintlich verfügbare Diagnose gestartet.

## Prüfungen

`tools/doom/bootstrap_tests.py` führt ausschließlich den eigenen Lader mit
synthetischem RAM und ausdrücklich simulierten Treiberaufrufen aus:

- C-Einstieg auf acht Byte ausgerichtet; jede überwachte Treiberschnittstelle
  behält diese Ausrichtung.
- Normalstart, einzelne Tasten, EXIT, hohe Tastenbits, Rettungs- und
  Panel-Update-Merker kehren mit erhaltenem Kontext zurück.
- Noch nicht eingehängtes Volume und zwei erfolglose Öffnungsversuche:
  anschließend vollständiges Lesen und Prüfen der passenden Engine;
  mehrere unterschiedliche Fortschrittsbilder und Engine-Eintritt.
- Sechs erfolglose Versuche: Fehler `0x103`, Fehlerbild, kein Engine-Eintritt.

Die vollständige Firmwareprüfung verwendet eine Kopie des angegebenen
batch3-Abbilds und ersetzt ausschließlich den eigenen Lader. Alle anderen
Bytes bleiben erhalten. Die virtuelle Doom-Karte enthält zusätzlich eine
synthetische Sample-Datei, damit auch die vorgemerkte Ladeanzeige im
Startpfad enthalten ist. Eine aktive Anzeige über den Doom-Bildern wird
nicht allein aus diesem Merker abgeleitet.

Gemessen im abschließenden Lauf: `check.py` besteht 412 von 412 Prüfungen.
Referenz ist das unveränderte Hacktribe-Original, der Kandidat ist der
bytegenaue batch3-Wiederaufbau mit neuem Doom-Lader. Die Freigaben enthalten
nur die konkreten Bereiche der ausgewählten Patches. Die Prüffälle stammen
aus dem zum batch3-Abbild gehörenden Commit, damit spätere Funktionen nicht
irrtümlich vorausgesetzt werden.

Der vollständige native Bedienlauf mit zusätzlicher Sample-Datei besteht
17 Prüfungen, einschließlich Levelwechsel, Beenden und Ausschalten. Er
liefert 254 Bilder und 156 Spielticks. Die 34 Prüfungen für Startmodi,
Dateifehler und Ausschalten bestehen ebenfalls. Die Speicherkontrollen
bleiben heil, die virtuelle Karte unverändert. Das ist ein Emulatorbeleg,
kein Gerätebeleg.

Offen bleibt die Sichtprüfung der neuen Datei auf dem Gerät. Der letzte
sichtbare Text trennt Initialisierung, Programmlesen und Engine-Start und
muss bei einem weiteren Hänger mitgemeldet werden. Ein tatsächlicher
Gerätestart wird erst nach dieser Prüfung als bestätigt bezeichnet.
