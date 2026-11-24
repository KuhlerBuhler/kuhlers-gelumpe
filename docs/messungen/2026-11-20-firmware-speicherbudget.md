# Platz für weitere ARM- und DSP-Funktionen

Stand 20. November 2026. **Offline neu gerechnet:** vollständige BLECH-Sätze auf develop `d4a401e87b4ebcd423f28b45d7e9850f5aaaaa4f`, Vergleich main `3b207cf8cfecd43af93e3657ff12b9867694ccb1`. Die Laufzeitpatches aller drei Builds wurden jeweils aus diesem Quellstand neu gebaut. Keine Originalfirmware gelesen, kein neuer Geräteversuch. Die [DSP](../glossary.md#dsp)-Grenzen stammen aus den unten genannten früheren Messungen und dem aktuellen Patchcode.

## Kurzfassung

Der ARM-Teil ist noch erweiterbar. Im aktuellen Stock-Satz bleiben rund **50 KiB**, mit Hacktribe rund **53 KiB** und im nativen Synth rund **210 KiB** innerhalb der vermessenen Patchflächen unbeschrieben und unreserviert. Diese Summe verteilt sich auf viele Lücken und enthält Reststücke bestehender Bausteine. Sie ist kein einzelner neu vergebbarer Codeblock.

Eine zusammenhängende **19-KiB-Lücke** ist ausdrücklich für alle drei Builds gegen den vollständigen Satz geprüft. Zusätzlich hält die bestehende Laufzeit ihren eigenen Codeplatz für Erweiterungen frei: rund **15 KiB auf Stock/Hacktribe**, rund **22 KiB auf Synth**. Diese Wachstumsreserve gehört bereits der Laufzeit und wird in der freien Gesamtsumme nicht mitgezählt.

Beim DSP gibt es derzeit **kein allgemein freigegebenes neues Code- und Datenbudget**. Das heißt nicht, dass keine weitere DSP-Funktion möglich wäre. Der geladene L1-Code reicht aber bis acht Byte vor das dokumentierte Ende seines Bereichs, und größere scheinbar leere Speicherflächen werden durch Samples, Effektpuffer und Allocatorbereiche genutzt. Für eine neue DSP-Funktion muss zuerst ein konkreter Speicher- und Zeitbedarf samt sicherem Bereich nachgewiesen werden.

**Ergänzung vom 20. November:** Die [anschließende konkrete DSP-Prüfung](2026-11-20-dsp-sdram-freiraum.md) belegt inzwischen auf statischer Ebene, für native Start-/Audioleerlaufläufe und vier gekoppelte Ein-Stimmen-Fälle 1,421875 MiB gemeinsame sowie 10,421875 MiB native blaue SDRAM-Kandidaten. Es handelt sich um definierte Modellnachweise, noch keine allgemeine Geräte- oder Volllastfreigabe.

Plugins sind eine andere Art, eigene Logik auf dem ARM auszuführen. Sie erzeugen keinen zusätzlichen DSP-Speicher und ersetzen keine neue native Klangroutine.

## Was die ARM-Zahlen zählen

**Offline gerechnet:** Für jeden Build wird aus dem vollständigen [roten Satz](../../data/patches/blech.json) oder [Synth-Satz](../../data/patches/blech-synth.json) genau die passende Variante jeder Patch-ID ausgewählt. Basis sind ausschließlich die bekannten freien Intervalle aus [patch-ram.mjs](../../data/patch-ram.mjs).

Davon wird die Vereinigungsmenge abgezogen aus:

- tatsächlich geschriebenen Bereichen der Patches;
- eigenen RAM-Zuordnungen, einschließlich Puffer, Zustand und freigehaltener Wachstumsbereiche;
- dem auf develop zusätzlich reservierten Sprachslot `[0xC016C000, 0xC0170000)` mit 16.384 Byte.

Mehrfach berührte Bytes werden nur einmal gezählt. `shares` beschreibt den Zugriff auf den Bereich eines anderen Besitzers und ist keine zweite Reservierung. Die bestehende [RAM-Prüfung](../../src/ramspans.mjs) bestätigt Kollisionsfreiheit und Lage der deklarierten Bereiche.

| Build auf develop | Vermessene Patchflächen insgesamt | Beschrieben oder reserviert | Verbleibend unbeansprucht |
|---|---:|---:|---:|
| Stock, roter Sampler | 707.012 Byte | 655.795 Byte | **51.217 Byte, 50,02 KiB** |
| Hacktribe | 707.012 Byte | 652.876 Byte | **54.136 Byte, 52,87 KiB** |
| Nativer Synth | 911.356 Byte | 696.334 Byte | **215.022 Byte, 209,98 KiB** |

Hacktribe auf blauem Gerät verwendet das Hacktribe-Codebudget, nicht die größere freie Fläche der nativen Synth-Firmware; siehe [Firmwareerkennung](../../src/firmware.mjs). Ein anderer Kopf macht aus dem Hacktribe-Abbild kein natives Synth-Abbild.

Die bekannten freien Flächen sind eine konservative Auswahl. Nicht vermessene FF- oder Nullfolgen werden nicht hinzugezählt. Umgekehrt können manche unbeanspruchten Bytes am Ende eines festen Bausteinfensters nur nach Abstimmung mit dessen Größenprüfung neu vergeben werden. Beispielsweise liegen 6.444 Byte hinter dem eingebauten Blechy-Block innerhalb seines festen Slots. Das ist kein automatisch unabhängiger Platz für einen neuen Patch.

### Zusammenhängende Flächen und bestehende Reserven

| Bereich | Größe | Bedeutung |
|---|---:|---|
| `[0xC019A400, 0xC019F000)` | **19.456 Byte, 19 KiB** | Auf allen drei Builds als zusätzliche Bereichszuordnung gegen den vollständigen Satz geprüft; angrenzende belegte Bytes werden abgewiesen |
| Synth `[0xC0139100, 0xC014EE00)` | 89.344 Byte, 87,25 KiB | Größte unbeanspruchte Lücke der Synth-Rechnung; kein gemeinsamer Bereich aller Builds |
| Synth `[0xC01217F4, 0xC0128000)` | 26.636 Byte | Weitere unbeanspruchte Lücke der Synth-Rechnung |
| Stock/Hacktribe `[0xC0168494, 0xC016C000)` | **15.212 Byte** | Bereits der Laufzeit zugeordnete Code-Wachstumsreserve |
| Synth `[0xC016695C, 0xC016C000)` | **22.180 Byte** | Bereits der Laufzeit zugeordnete Code-Wachstumsreserve |
| `[0xC018E9D0, 0xC018FF00)` | 5.424 Byte | Weitere bereits zugeordnete Laufzeitreserve, nicht Teil der unbeanspruchten Gesamtsumme |
| Synth `[0xC01A6000, 0xC01ADF00)` | 32.512 Byte | Bereits zugeordnete alte Laufzeitfläche; beim Sampler liegt dort unter anderem die Ladeanimation |
| `[0xC016C000, 0xC0170000)` | 16.384 Byte | Sprachslot, auch ohne aktivierte deutsche Oberfläche freigehalten |

Der [vorhandene Platztest](../../test/patch-ram.test.mjs) prüft die 19-KiB-Lücke ausdrücklich auf Hacktribe, Stock und Synth. Die übrigen Zahlen folgen aus der Belegungsrechnung und den Grenzen in [script_hooks.py](../../tools/patch/script_hooks.py). Eine neue Funktion muss ihren konkreten Bereich weiterhin deklarieren und die bestehenden Prüfungen bestehen.

Das gemeinsame Codefenster der Laufzeit reicht von `0xC0150300` bis `0xC016C000`, insgesamt 113.920 Byte. Aktuell sind davon auf Stock/Hacktribe 98.708 Byte und auf Synth 91.740 Byte beschrieben. Die verbleibenden 15.212 beziehungsweise 22.180 Byte sind bereits in der Besitzerzuordnung enthalten. Sie dürfen deshalb nicht nochmals zur unbeanspruchten Gesamtsumme addiert werden.

## Laufzeitspeicher des ARM

Codeplatz und Arbeitsdaten sind getrennte Grenzen. Ein kurzer neuer Handler kann einen großen Puffer benötigen.

| Zuordnung | Größe | Stand |
|---|---:|---|
| Laufzeitzustand ab `0xC01AE000` | 166.960 Byte | Zugeordnet, einschließlich der festen Laufzeitstrukturen |
| Abstand bis zur nächsten Menüzuordnung | 432 Byte | Rechnerischer Abstand, keine bereits freigegebene Erweiterung |
| Gemeinsamer Plugin-Pool | **131.072 Byte, 128 KiB** | Für geladene Blobs, Variablen und Einträge zusammen |
| Karten-Arbeitsbereich | 4.096 Byte | Bereits zugeordnet |
| Datei-/Store-Puffer | 32.752 Byte | Bereits zugeordnet |
| Kleine Zustandsfläche `[0xC0188A00, 0xC0188F00)` | 1.280 Byte | Vollständig zugeordnet |

Der native Heap ist separat. Dokumentiert sind 2.097.152 Byte Gesamtpool. Eine ältere Emulatormessung sah nach Start noch 1.927.488 Byte bis zur Obergrenze. Das ist keine aktuelle Freiliste nach beliebigem Betrieb: Fragmentierung, späteres Wachstum und weitere Verbraucher sind offen. Der Audio-Dienst hält nach erster Nutzung 103.424 Byte, der Dateidatendienst kann weitere 32.788 Byte halten. Siehe [Dateidatendienst](../../tools/patch/script_data.s).

## DSP: gespeicherter Strom und laufender Speicher

Der DSP-Bootstrom liegt innerhalb des Firmwareabbilds. Seine gespeicherte Länge ist nicht seine RAM-Belegung: Füllbefehle können mit wenigen gespeicherten Bytes große Speicherbereiche initialisieren.

| Größe | Dokumentierter Wert | Bedeutung |
|---|---:|---|
| Roter DSP-Bootstrom | 271.008 Byte | Gespeicherter Loaderstrom, kein freies Codebudget |
| Blauer DSP-Bootstrom | 269.428 Byte | Eigenes Layout, nicht mit roten Parser-Vorgaben auswerten |
| DSP-SDRAM | 32 MiB | Getrennt vom ARM-Speicher, bereits für Code und Daten genutzt |
| Geladener roter L1-Code `[0xFFA00000, 0xFFA0BFF8)` | 49.144 Byte | Acht Byte bis zum dokumentierten Ende `0xFFA0C000`; keine vollständige Suche aller internen Lücken |
| DSP-Heap 1 nach Stufe-2-Patch | 7.456 Byte | RTOS-Speicher, nicht eine neue Codefläche |
| Beobachtete Belegung dieses Heaps am Gerät | 3.776 Byte | Leerlaufmessung eines früheren Stands |
| Daraus verbleibende Heapreserve | 3.680 Byte | Reserve für weitere RTOS-Allokationen, keine neue allgemeine Patchfreigabe |
| Stufe-2-Zustand und Koeffizienten `[0xFF906320, 0xFF908000)` | 7.392 Byte | Bereits durch stage2-memory zugeordnet |
| PCM-Fenster rot | 25 MiB | Aktiver Samplespeicher |
| PCM-Fenster nativ blau | 16 MiB | Aktiver Samplespeicher |
| Insert-Puffer insgesamt | 3.072.000 Byte | 16 bereits zugeordnete Effektpuffer |
| Master-Puffer | 384.000 Byte | Bereits zugeordnet |

Grundlagen: [DSP-Aufbau](../hintergrund/dsp-erster-blick.md), [blauer Sample-Import](2026-11-12-blau-sample-import.md), [Stufe-2-Speicher](2026-11-13-stufe2-speicher.md) und [aktueller Stufe-2-Patch](../../tools/patch/stage2_memory.py). Die auf dem Gerät beobachteten Heapwerte sind keine neue Messung vom 20. November. Die [anschließende Nachprüfung](2026-11-20-dsp-sdram-freiraum.md) bestätigt inzwischen die vollständige originale Heap-Tabelle auch auf Synth.

### Warum die großen Lücken nicht als frei zählen

Der rote Bootstrom löscht einen Bereich von 29.776.912 Byte. Später liegen darin unter anderem PCM und Effektpuffer. Nullfüllung bedeutet hier Vorbereitung von Arbeitsdaten.

Eine ältere blaue Untersuchung nennt rund 11,5 MiB ohne damals bekannten Nutzer, schließt berechnete Zugriffe aber ausdrücklich nicht aus. Die später dokumentierten roten DSP-Heaps bei `0x1D00000` und `0x1E00000` liegen geometrisch in dieser Spanne. Die Nachprüfung bestätigt diese beiden Heaps nun auch im blauen Original. Die gesamte alte Kandidatenfläche ist deshalb nicht frei.

Auch der [DSP-Extractor](../../tools/dsp/dsp_extract.py) erzeugt keine vollständige Freiliste. Er expandiert große Füllblöcke nicht und berücksichtigt bestimmte Loaderphasen nicht; spätere Blöcke können frühere überlagern. Seine extrahierten Dateien allein belegen deshalb keine freien Laufzeitflächen.

DSP-Code läuft bereits auch aus SDRAM. Das fast volle dokumentierte L1-Fenster verbietet daher nicht jede neue Funktion. Für eine Erweiterung fehlen aber ein eindeutig reservierbarer Code-/Datenbereich, dessen sichere Einbindung in den Loader und die Zeitreserve unter voller Audiolast. Ein ARM-Plugin stellt keinen dieser DSP-Nachweise bereit.

## Wie viele weitere Funktionen sind realistisch?

Eine feste Zahl wäre nicht belastbar. Die bestehenden Bausteine zeigen die Größenordnung:

| Vorhandener Baustein auf develop | Vereinigung seiner Schreib- und RAM-Bereiche innerhalb der geprüften ARM-Flächen |
|---|---:|
| Stereo-Ein-Pad, rot | 164 Byte |
| Notenhilfe, rot | 2.052 Byte |
| MFX-Schalter, rot | 2.296 Byte |
| Doom-Lader, rot | 13.312 Byte einschließlich Reserven und Puffern |
| User-Samples, nativ blau | 62.476 Byte einschließlich Daten und Zustand |

Diese Größen enthalten je nach Baustein Code, Tabellen und Arbeitsspeicher. Sie sind keine gemessenen allgemeinen Funktionspreise. Rein rechnerisch passen in 19 KiB neun Blöcke zu 2 KiB, aber eine konkrete Funktion kann andere Puffer, weitere Haken oder mehr Rechenzeit benötigen. Ein Menühelfer und ein neues Audioverfahren sind damit nicht vergleichbar.

Für eine Erweiterung der vorhandenen Laufzeit ist die gemeinsame engere Grenze derzeit die 15.212-Byte-Code-Wachstumsreserve auf Stock/Hacktribe. Für einen eigenen portablen ARM-Baustein ist die separat geprüfte 19-KiB-Lücke ein konkreter Ausgangspunkt. Native Synth-Funktionen können zusätzlich größere nur dort vorhandene Flächen nutzen. Keine dieser Angaben legt fest, dass danach zwingend nur noch Plugins möglich wären: ein anderer Zuschnitt bestehender Bereiche wäre eine eigene Änderung mit neuem Nachweis.

Plugins sind für veränderliche Abläufe und eigene Bedienlogik geeignet, weil ihr Bytecode von der Karte kommt und nicht jede Funktion die native Laufzeit vergrößert. Sie teilen sich aber denselben 128-KiB-Pool für geladene Blobs und Variablen. Der aktuelle [Vertrag](../../data/script/contract.mjs) begrenzt Code je Plugin auf 16.384 Byte und die gemeinsame Framearbeit auf 5 ms. Daraus folgt weder eine garantierte Pluginzahl noch zusätzliche Kapazität für neue Blackfin-Algorithmen.

## Nachvollziehen und Grenzen

Ausgewertet wurden die vollständigen Standard-Sätze, keine einzelnen bequem gewählten Patches. Die Sprachreserve ist enthalten; zusätzliche optionale Patches müssen erneut auf Überschneidungen geprüft werden. Die Originalabbilder wurden nicht nach weiteren Null- oder FF-Folgen durchsucht. Aussagen über unbeanspruchte ARM-Flächen sind deshalb eine Rechnung innerhalb der bereits vermessenen Freigaben, keine neue Freigabe unklassifizierten Speichers.

| Vergleich main | Unbeansprucht im damaligen vollständigen Satz |
|---|---:|
| Stock | 54.345 Byte |
| Hacktribe | 57.264 Byte |
| Nativer Synth | 318.942 Byte |

Auf main hält die ältere Laufzeit ihr Code-Restfenster noch ohne gesonderten Sprachslot frei. Die Null im eigenen Sprachreserveposten bedeutet dort nicht, dass diese Bytes zusätzlich frei wären. Seitdem hinzugekommene Funktionen erklären den anderen Belegungsstand; Quellstände und Patchauswahl gehören deshalb zu jeder Zahl.

Die Belegungsrechnung wurde unabhängig mit byteweisen Masken nachgerechnet. Die vorhandenen Tests zur RAM-Zuordnung und zur 19-KiB-Lücke sowie die Dokumentationsprüfung gehören zum Nachweis. Ein neuer DSP-Bereich braucht dagegen eine eigene Laufzeituntersuchung mit Heaps, Stacks, DMA und voller Audiolast. Der DSP-Testharness bildet nicht das gesamte Gerät ab; seine zusätzlichen Testadressen oberhalb der dokumentierten 32 MiB sind kein Gerätespeicherbeleg.
