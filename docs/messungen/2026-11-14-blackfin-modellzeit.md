# Blackfin: gemeinsame ARM-/DSP-Modellzeit und GPIO

Fortsetzung von [HOSTDP-FIFO und DMA1](2026-11-14-blackfin-host-fifo.md).
Alle folgenden Ausführungen fanden im Simulator statt. Kein Gerät wurde angesprochen.

## Hergeleitet

Das [BF52x-Hardwarehandbuch](https://www.analog.com/media/en/dsp-documentation/processor-manuals/ADSP-BF52x_hwr_rev1.2.pdf)
beschreibt in Kapitel 5 die von `SIC_IMASK` unabhängige Weckfunktion von
`SIC_IWR`. Ein freigegebener Weckwunsch darf einen schlafenden Kern auch dann
wecken, wenn der zugehörige Interrupt maskiert ist. Umgekehrt dürfen
beliebige Zeitgrenzen eines Emulators den Kern nicht aus `IDLE` holen.

Kapitel 8 beschreibt FRDY im Interruptmodus: Der Host darf bei leerem
Schreib-FIFO beziehungsweise vollem Lese-FIFO einen Block übertragen.
Diese Bereitschaft gilt innerhalb eines aktiven Datenauftrags. Nach dem
letzten Wort darf ein leerer Schreib-FIFO keinen weiteren Datenblock anfordern.
Die Zuordnung zu GPIO 6.1 folgt der ARM-Abfrage aus der vorigen Untersuchung;
ein elektrischer Nachweis der Verbindung ist damit nicht erbracht.

Die vorhandene ARM-Zeitbewertung und die GNU-Befehlslaufzeiten sind Modelle.
Der DSP-Prüftakt `516096000` ist ausdrücklich gewählt. Gemeinsame Zeit schafft
eine konsistente Reihenfolge, keinen Nachweis echter BUSY- oder Buslaufzeiten.

## Gemessen mit erzeugten Programmen

Der Worker `BFIN7` kann bis zu einer vorgegebenen Taktgrenze laufen. Ein
Aufruf umfasst höchstens eine Million Takte. Befehlsrestzyklen bleiben über
Aufrufe hinweg erhalten. Die Ereigniszeit läuft unabhängig vom einschaltbaren
`CYCLES`-Register. Bei aktiviertem Zähler werden nur tatsächlich abgearbeitete
Kernzyklen zugerechnet.

Der Kern bleibt nach `IDLE` schlafen, während SPORT und DMA ihre Ereignisse
weiter abarbeiten. Ein passender Weckwunsch beendet diesen Zustand.
Konfigurationsänderungen an `SIC_IWR` berücksichtigen bereits anstehende
Quellen. Unbekannte ROM-Aufrufe bleiben auch im Taktbetrieb Fehler mit
PC, Aufrufer und Registern.

126 gezielte Modulprüfungen bestehen, darunter 22 Zeit-, GPIO- und
Startaufbauprüfungen. Eine unabhängige Nachprüfung bestätigt den Stand.
Abgedeckt sind insbesondere:

- Teilung eines mehrzykligen Befehls ohne verlorene oder doppelte Restzyklen.
- Gleiche Register und Ereigniszeit bei einem ganzen oder vielen geteilten Aufrufen.
- Weiterlaufende Gerätezeit bei ausgeschaltetem `CYCLES`-Zähler.
- Schlaf über eine Zeitgrenze hinaus, ohne die nächste Anweisung auszuführen.
- SPORT-Empfang und DMA bei schlafendem Kern; anschließendes Wecken durch `SIC_IWR`.
- Bereits anstehende und neu eintreffende Weckwünsche bei maskiertem Interrupt.
- FRDY ohne Abfrageeffekt und mit korrekter Polarität während und nach einem Auftrag.
- Abbruch bei nicht unterstütztem FRDY-Modus oder unbekanntem ROM-Aufruf.
- Erzeugte ARM-Anweisungen und GPIO-Zugriffe unter derselben DSP-Zeit.
- Fortgesetzter ARM-Schlaf über Zeitgrenzen hinweg und Aufwachen erst bei freigegebenem AINTC-Ausgang.
- Ausführung eines bereits angenommenen IRQs auch nach Abfallen seiner Quelle.
- Festgehaltene Taktkonfiguration ohne veränderbare Übergabeobjekte.
- Beobachtete Bereitschaft statt einer erzwungenen Erfolgsmeldung.

## Gemessen am gekoppelten Originalstart

`Machine` bindet die native FIFO-Auswahl ausdrücklich an ihre Zeit. Der
DSP-Ladestrom wird weiterhin vom Host in den Speicher geladen. Danach beginnt
der originale Reset-/RTOS-Pfad. Er läuft unter der ARM-Modellzeit weiter,
ohne einen vorgezogenen, getrennten Startlauf. Vor einem Host-Port- oder
GPIO-Zugriff und am Ende eines ARM-Abschnitts erreicht der DSP dessen Zeit.
GPIO 6.1 liest dann den nativen FRDY-Zustand.

Die erste gekoppelte Gegenprobe bleibt nach einem bereits bestätigten
Schreibauftrag stehen: Der FIFO ist leer, `HOST_STATUS` zeigt `0x018C`,
aber das Modell hält FRDY weiterhin aktiv. Die Gegenprobe für das beendete
Datenfenster schlägt mit diesem Modell fehl. Nach ihrer Korrektur kommt der
ARM ohne künstlichen GPIO-Wechsel weiter.

Die rote Originalfirmware 2.02 erreicht in drei Modellsekunden die Hauptseite.
Alle sieben Prüfbedingungen bestehen: gemeinsame Zeit, native Initialisierung,
Verkehr in beiden Richtungen, keine ARM-Assertion, keine DSP-Ausnahme,
eingeschaltetes Gerät und erreichte Hauptseite. Erfasst werden 5558
Steuerzugriffe, 13072 geschriebene und 4128 gelesene Datenwörter.

Die abschließende Wiederholung des aktuellen Stands über jeweils eine
Modellsekunde besteht auf allen drei Originalfassungen:

| Fassung | Steuerzugriffe | Daten geschrieben | Daten gelesen | Ergebnis |
|---|---:|---:|---:|---|
| Rot | 4158 | 11472 | 2528 | bestanden |
| Hacktribe | 4158 | 11920 | 2528 | bestanden |
| Blau | 2646 | 7232 | 2512 | bestanden |

Der blaue Aufbau verwendet die erzeugte Flash-Kennung der blauen Hardware.
Ein erster Lauf mit roter Kennung wird wegen fehlendem Host-Verkehr und
nicht erreichter Hauptseite als Fehlschlag erfasst. Die Gegenprobe für die
Kennung schlägt vor ihrer Korrektur fehl.

Auch der vollständige BLECH-Patchsatz dieses Zweigs besteht denselben
Startfall über eine Modellsekunde auf allen drei Grundlagen:

| Grundlage | Steuerzugriffe | Daten geschrieben | Daten gelesen | Ergebnis |
|---|---:|---:|---:|---|
| Rot | 4193 | 11568 | 2560 | bestanden |
| Hacktribe | 4193 | 12016 | 2560 | bestanden |
| Blau | 2674 | 7264 | 2544 | bestanden |

Die erzeugten Firmwarekopien bleiben außerhalb des Repositorys. Dieser
Startfall enthält weder eine große Sample-Bibliothek noch aktive
Sample-Auslagerungen.

### Ein Pad-Anschlag im ausgeführten DSP-Code

Weitere BLECH-Läufe auf Rot, Hacktribe und Blau starten ohne offene Stimmen. Ein
Panelereignis `[4, 0, 0, 100, 1]` drückt Pad eins, danach laufen 100 ms
Modellzeit weiter. `[4, 0, 0, 0, 0]` lässt es los; der Lauf geht weitere
500 ms weiter. Die Bedienereignisse entsprechen dem vorhandenen
[Pad-Prüffall](../../tools/emu/dsp_cases.py).

Das Stimmenfeld bei `0xFF900EAC` ist vorher null, nach dem Anschlag
`0x00010000` und nach Loslassen wieder null. Die übrigen 23 geprüften
Stimmenfelder bleiben null. Gelesen wird jeweils Wort null mit 26 Wörtern
Abstand; die Adresse ist aus der früheren
[DSP-Untersuchung](2026-11-12-dsp-modell.md) abgeleitet. Die Beobachtung
schreibt weder einen erwarteten Feldwert noch ruft sie einen DSP-Handler
direkt auf. `SEQSTAT` bleibt null, der ARM meldet keine Assertion.

Das belegt die Verarbeitung dieses Pad-Gates im nativen DSP. Natürliche
One-Shot-Enden und hörbare Ausklänge sind damit nicht allgemein nachgewiesen.

Ein Lauf ohne Assertion allein gilt ausdrücklich nicht als bestanden.
Fehlende Rücklesedaten, eine nicht erreichte Hauptseite, ein abgelaufener
Ausführungsrahmen oder ein abgebrochener Worker führen zum Fehlschlag.

Der gekoppelte Fall ist mit jeder eigenen Originaldatei ausführbar:

```bash
python3 tools/dsp/build_blackfin.py "$BFIN_SDK"
tools/emu/.venv/bin/python tools/emu/blackfin_cases.py \
  --vsb "$E2_STOCK_VSB" --worker "$BFIN_SDK/blackfin-worker" \
  --core-hz 516096000 --seconds 3 --input lcg
```

Die bisherige Kompatibilitätsauswahl bleibt ausdrücklich als Vorgabe erhalten.
Sie ist kein automatischer Rückfall des nativen Prüffalls.

## Abschließende Projektprüfungen

- Der vollständige Unitlauf besteht mit 1616 bestandenen und 166 ausgelassenen Prüfungen.
- Der abschließende Browserlauf besteht mit 353 bestandenen und einer ausgelassenen Prüfung. Ein erster Gesamtlauf enthielt zwei Timeouts der Versionsanzeige; die betroffene Datei bestand danach isoliert und der vollständige Wiederholungslauf ebenfalls. Die Ursache der ersten Timeouts bleibt offen.

## Offen

- Effektwechsel, natürliche Stimmenenden und Sample-Swap sind durch die Start- und Pad-Fälle allein nicht belegt.
- Hardwarekonformität von BUSY-Zeiten, GPIO-Verbindung, RAM-Besitz und Durchsatz bleibt eine Gerätefrage.
- Eine Audioausgabe ist nicht Bestandteil dieses Prüfpfads.
