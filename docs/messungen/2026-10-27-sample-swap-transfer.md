# Sample-Swap: begrenzter Transfer am Gerät

Stand: 27.10.2026. Fortsetzung von [RAM-Besitz und Timeout](2026-10-25-sample-swap-timeout.md).
Beleg: `measure:2026-10-27/sample-swap-transfer`.

**Grenze des Messstands:** Diese Messung prüft die Rohtransfers, nicht den
inzwischen gebauten Sample-Swap. Während der Versuche fehlte im verwendeten
Werkzeug die neuere Prüfung, ob dessen RAM-Bereiche bereits einem aktiven
Swap gehören. Der Swap-Modus wurde vor den Schreibzugriffen nicht festgehalten.
Die spätere lesende Prüfung konnte nicht mehr erfolgen, weil kein Electribe-
MIDI-Port mehr sichtbar war. Die Zahlen sind daher keine Freigabe des
Parallelbetriebs mit einem aktiven Swap und kein Nachweis seines Cache-Besitzes.

## Gemessen

Roter Electribe 2 Sampler über USB-MIDI am Linux-Laptop. Als installierte
Versionen wurden BLECH 1.3.4 und Korg 2.02 angegeben. Diese Versionsangaben
wurden nicht am Gerät ausgelesen. Die eigene Referenzdatei wurde vom Werkzeug
als Hacktribe eingestuft; das belegt nicht die vollständige Firmware des
angeschlossenen Geräts. Die benutzten nativen Routinen stimmen mit dieser
Referenzdatei überein. Das Feld `build` in den Einzelergebnissen bezeichnet
die Referenzdatei, nicht eine unabhängig ermittelte Geräteversion. Werkzeug:
[sample_swap_paths.py](../../tools/device/sample_swap_paths.py).
Die [Einzelergebnisse](2026-10-27-sample-swap-transfer.json) enthalten die
Zeiten, Rückgaben und bestätigten Wiederherstellungen, keine Audiodaten.

Zuerst lief ein reiner DSP-Lesetest: 1024 Byte in 0,15796 ms, Status null,
512 Wörter vollständig, Fehlerzustand null, CPU-Arbeitsbereiche danach
wiederhergestellt. Dabei wurden keine Sampledaten geschrieben.

Der Nutzungsabgleich las danach alle 250 Bankpattern und das aktuelle
Pattern, zusammen 4016 Parts. Slot 503 war unter den drei konservativen
ID-Normalisierungen einschließlich indirekter Zuordnungen unbenutzt.
Sein geladenes PCM umfasst 36030 Byte ab DSP-Offset `0x0037857E`.
Getestet wurde der ausgerichtete Ausschnitt ab `0x00378580`, also zwei
Byte hinter dem Sampleanfang. Slot 999 war nicht geladen. Ein vollständiger
64-KiB-Test passt nicht in den gewählten Slot und wurde nicht ausgeführt.

### Gestoppt

Der erste Schreibversuch mit 1 KiB dauerte 0,07182 ms aus RAM und
1,74263 ms vom Kartenlesen bis zum abgeschlossenen DSP-Schreiben.
Der Kartentakt blieb dabei unverändert bei 25 MHz.

Danach je drei Läufe mit 32 KiB. Durchsatz jeweils aus dem Median der
Zeiten berechnet, mit 1 MiB = 1048576 Byte:

| Kartentakt | RAM -> DSP, min/Median/max | RAM -> DSP | Karte -> DSP, min/Median/max | Karte -> DSP |
|---|---|---|---|---|
| 12,5 MHz | 2,150 / 2,153 / 2,186 ms | 14,51 MiB/s | 12,207 / 13,329 / 13,993 ms | 2,34 MiB/s |
| 25 MHz | 2,175 / 2,187 / 2,505 ms | 14,29 MiB/s | 10,724 / 11,158 / 11,190 ms | 2,80 MiB/s |

In jedem erfolgreichen Lauf wurde zuerst zweimal aus dem DSP gelesen und
verglichen. Karten-PCM und DSP-Ausgangsinhalt mussten übereinstimmen.
Der RAM-Weg schrieb anschließend XOR-veränderte Daten, las sie zurück und
stellte das Original wieder her. Der Kartenweg ersetzte erneut veränderte
DSP-Daten durch Kartenlesen und DSP-Schreiben innerhalb eines EXEC.
Danach waren der übertragene DSP-Ausschnitt, seine drei Tabelleneinträge,
der Frei-Zeiger und die kontrollierten Zuordnungen unverändert. Die
CPU-Arbeitsbereiche und der ursprüngliche Kartentakt `0x102` wurden
ebenfalls wiederhergestellt. Kein Fehler und kein Hänger in diesen Läufen.

### Wiedergabe

Der globale Chain-Modus war an, das aktuelle Pattern hatte aber kein
Kettenziel. Der interne Takt war gewählt. Nach MIDI-Start zeigte die
Kontrolle noch Transport null; deshalb begann darüber kein DSP-Test.
Anschließend wurde MIDI-Stop gesendet. Die vorhandene Tastensteuerung
wurde ebenfalls vor jedem Schreibzugriff verweigert, weil ihr Live-Code
nicht der auf dem Laptop gespeicherten eigenen Patchdatei entsprach.
PLAY wurde daraufhin am Gerät gedrückt. Das Transportwort stand vor der
Messreihe und nach jedem erfolgreichen Versuch auf eins, der Schrittzähler lief weiter.
Das aktuelle Pattern blieb bei Index null.

Der 1-KiB-Versuch ergab 0,07226 ms aus RAM und 1,38373 ms von Karte, bei
unverändertem Kartentakt. Danach drei vollständige 32-KiB-Läufe bei 12,5 MHz:

| Kartentakt | RAM -> DSP, min/Median/max | RAM -> DSP | Karte -> DSP, min/Median/max | Karte -> DSP |
|---|---|---|---|---|
| 12,5 MHz | 2,347 / 2,363 / 2,626 ms | 13,22 MiB/s | 13,818 / 14,285 / 14,344 ms | 2,19 MiB/s |

Die Zeiten messen nur den erfolgreichen Transfer, nicht die zusätzliche
Wartezeit auf einen freien Port. Im gesamten jeweiligen Prüfablauf gab es
24, 6 und 21 bestätigte BUSY-Wiederholungen, einschließlich der Sicherungs-
und Kontrollzugriffe. Diese zählen nicht allein zum zeitlich erfassten
RAM- oder Kartenaufruf.

### BUSY-Abbrüche und Wiederherstellung

Der erste Wiedergabeversuch brach mit Status 2 und null übertragenen
Wörtern ab. Der genaue Teilschritt wurde dabei nicht protokolliert. Ein
nachfolgender Leseversuch gelang, ein weiterer lieferte zweimal BUSY und
dann Erfolg. Der 1-KiB-Testbereich stimmte danach mit der Karte überein.

Der Host wiederholt deshalb jetzt ausschließlich bestätigtes BUSY mit null
übertragenen Wörtern, höchstens acht Aufrufe mit jeweils 10 ms Pause
zwischen ihnen. Beim kombinierten Kartenweg müssen außerdem Öffnen,
vollständiges Lesen, Schließen und Rücksetzen des Kartentakts bestätigt
sein. TIMEOUT, FAULT, teilweise Übertragung oder eine unbestätigte EXEC-
Rückgabe werden nicht wiederholt. Der DSP-Transport selbst bleibt unverändert.

Trotzdem brachen zwei 32-KiB-Versuche bei 25 MHz nach acht belegten
Portzugriffen ab. Der erste kam vor dem erneuten Ändern der DSP-Daten zum
Stehen; deren Original war unmittelbar davor bereits zurückgelesen und
geprüft. Der zweite scheiterte beim Kartenweg, nachdem der Testausschnitt
bereits XOR-verändert war. Für 25 MHz unter Wiedergabe liegt deshalb kein
vollständig abgeschlossener Zeitvergleich vor.

Nach STOP am Gerät wurden die erhaltene RAM-Originalkopie und die zuletzt
vollständig gelesenen Kartenbytes verglichen. Beide waren gleich. Der
32-KiB-Originalbereich wurde zurückgeschrieben und vollständig aus dem DSP
zurückgelesen. Abschließend waren alle 32768 Byte gleich der Originalkopie,
der DSP-Lesestatus null, die Wortzahl 16384, der Fehlerzustand null und das
Transportwort null. Es blieb keine Änderung des getesteten Samplebereichs.

Bei diesem Abschluss wurde die Sammelmeldung für einen misslungenen
RAM-Lesezugriff zunächst als CRC-Problem eingeordnet. Tatsächlich betraf
sie den direkten SysEx-Zugriff auf das MMCCLK-Register bei `0x01C40004`:
Die getrennte Statusabfrage ergab RANGE 3. Der vollständige DSP-Datenvergleich
hatte zuvor bereits bestanden. Die bestätigte Schlusskontrolle las die
RAM-Daten in 512-Byte-Blöcken, ohne weitere DSP-Schreibzugriffe.

**Grenze des Werkzeugs:** Nach den BUSY-Abbrüchen gab es keinen pauschalen
CPU-Rückbau; Testcode und Testpuffer verblieben im ARM-RAM. Die vollständigen
Läufe restaurierten jeweils ihren eigenen Ausgangszustand, nicht rückwirkend
den Zustand vor einem früheren Abbruch. Es wurde kein Ausführungshaken oder
dauerhafter Cache installiert. Der Abbruch nach einer bereits erfolgten
Teständerung braucht vor weiteren unbeaufsichtigten Wiedergabetests eine
eigene, sichere Rücksetzbehandlung. Ein Portfehler oder unklarer EXEC-Rücklauf
darf dabei weiterhin kein blindes Aufräumen auslösen.

## Korrekturen am Messwerkzeug

**Gemessen am Abbild und am Gerät gegengeprüft:** Die Routine
`0xC004EBD4` liest die Importnummer. Bei `0xC004EBF4` vergleicht sie diese
mit 49 und kehrt für Werte bis einschließlich 49 ohne Sample-Zuordnung
zurück. Erst größere Importnummern betreten die drei Sampletabellen.
Das Werkzeug behandelte diese eingebauten Oszillatoren vorher als
unauflösbare Sample-Referenzen und verweigerte dadurch alle Kandidaten.
Jetzt werden sie wie im nativen Pfad abgegrenzt. Ab Importnummer 50 bleibt
die vollständige Aliasprüfung bestehen, ungültige Tabellenindizes führen
weiter zum Abbruch. Die Live-Prüfung umfasst `0xC004EBD4` bis `0xC004EDDC`,
einschließlich der ausgelagerten Zeiger im Literalpool.

**Gemessen am Gerät:** Die unbenutzten geladenen Kandidaten begannen nicht
auf einer 32-Byte-Grenze. Der Transport verlangt diese Ausrichtung weiterhin.
Das Werkzeug wählt deshalb einen ausgerichteten Ausschnitt innerhalb der
vollständig geprüften Samplebelegung. Beim Kartenlesen wird genau derselbe
Versatz addiert. Der erste und letzte Rand bleiben außerhalb des Transfers.
Der DSP-Transport und die Firmwaretabellen wurden dafür nicht verändert.

34 synthetische Python-Prüfungen des Werkzeugs, einschließlich der
unregelmäßigen PCM-Testdaten für beide versetzten Ladewege, bestanden.
Die neuen Fehlerfälle wurden zunächst als fehlgeschlagene Prüfungen
beobachtet. Die vorhandenen 14 ARM-Prüfungen des Transports und der echte
JS-Patchertest bestanden ebenfalls. Eine unabhängige Prüfung deckte
zusätzlich 144 Grenzfälle des Ausschnitts ab. Keine Korg-Testdaten.

Die BUSY-Prüfungen decken die endliche Wiederholung, den unveränderten
Abbruch bei Protokollfehlern und den tatsächlich assemblierten Kartentreiber
ab. Letzterer kennzeichnet erfolgreiches Öffnen mit `R_OPEN = 1`, während
die nativen Erfolgsstatus für Lesen und Schließen null sind. Die Prüfung
verwendet dieses echte Ergebnisformat und keine nur angenommene Struktur.

Nach dem Versionsabgleich wurde die im neueren Werkzeug vorhandene
MODE-Sperre übernommen. Sowohl der Rohtransfer als auch der RAM-Nutzungsscan
verweigern nun vor jedem Upload einen aktiven Swap bei `0xC0188530`.
Ein zusätzlicher Regressionstest prüft, dass dabei kein Schreibzugriff erfolgt.
Diese Sperre wurde nach den Messungen ergänzt und noch nicht am Gerät geprüft.
Für den laufenden Swap ist dessen eigener, nur lesender Beobachter
`tools/device/sample_swap_stats.py` vorgesehen; er prüft zunächst den geladenen
Swap-Code und liest anschließend dessen eigene Ladezähler und Zeiten.
Auch die erneute Portsuche nach Angabe der Versionen fand am Linux-Laptop
nur den virtuellen MIDI-Through-Port; am Mac war kein passendes USB-Gerät
sichtbar. Es erfolgte dabei kein weiterer Zugriff auf das Gerät.

`GELUMPE_JOBS=2 npm test` bestand mit 1071 bestandenen und 148 übersprungenen
Prüfungen, ohne Fehler. Die danach ergänzte MODE-Sperre wurde zusätzlich
gezielt geprüft. `npm run test:e2e` ergab dagegen
189 bestandene, eine fehlgeschlagene und eine übersprungene Prüfung. Der
Fehler betraf den unveränderten Hintergrundtest für reduzierte Bewegung;
auch dessen getrennte Wiederholung schlug fehl. Ein zusätzlicher serieller
Lauf zeigte denselben Fehler und wurde danach beendet. Keine vollständige
Browserfreigabe dieser Runde.

## Hergeleitet und offen

**Hergeleitet:** Für diesen 32-KiB-Ausschnitt ist RAM -> DSP etwa fünf- bis
sechsmal schneller als Kartenlesen plus DSP-Schreiben. Ein RAM-Cache kann
also die beobachtete Kartenlatenz vermeiden. Das belegt noch keinen freien
dauerhaften Cachebereich und keine vollständige Sample-Umschaltung.

Die Portbelegung unter Wiedergabe ist eine zusätzliche Grenze. Aus der
reinen Kopierzeit folgt keine garantierte Ladezeit. Ein späterer Ladepfad
muss den Zugriff einplanen und bei fehlender Bereitschaft den Patternwechsel
auslassen. Das beobachtete BUSY verlangt keine Lockerung der Zeitgrenzen.

Die Kartenzeit umfasst `f_read` plus den begrenzten DSP-Transfer. Öffnen,
Positionieren und Schließen liegen außerhalb der Zeitmessung. Das vorherige
Prüfen desselben Bereichs kann Karten-Caches erwärmen. Die Zahlen gelten
für den beobachteten 32-KiB-Ausschnitt, keine Kaltstart-Latenz und keinen
langen sequenziellen Ladevorgang. Die früheren Kartenmessungen mit 2 MiB
nur lesend sind deshalb kein gleichartiger Vergleich.

**Offen:** Vollständiger Vergleich bei Wiedergabe und 25 MHz, längere
Transfers, Klang und Aussetzer unter nachgewiesener Stimmenlast,
Stimmenlebensdauer, Slot-Neubindung, echte DSP-Speichergrenze und der
RAM-Besitz bei Sampling/Resampling sowie der während dieser Rohmessung
tatsächlich gewählte Swap-Modus. Native FatFs-Aufrufe haben weiterhin
keinen eigenen Timeout. Kein High Speed mit 50 MHz, keine Flash-Schreib-
zugriffe, keine Änderung einer Sampledatei auf der Karte. Durch diese Werkzeuge
wurde kein Cache aktiviert; ein bereits laufender Swap wurde nicht abgesichert.
