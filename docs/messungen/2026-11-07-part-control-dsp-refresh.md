# DSP-Transport bei neuen Part-Bedienungen

Messung vom 2026-11-07. Hacktribe-Firmware 2.02 im Emulator, eigene `SYSTEM.VSB`, leerer Flash und Startpattern. Die Firmware lief in frischen Emulatorzustaenden. Erfasst wurden Panelereignisse, Firmwareaufrufe und DSP-Host-Port-Zugriffe. Der DSP ist im Emulator ein Platzhalter. Die Probe belegt gesendete Kommandos und Daten, nicht deren hoerbare Klangwirkung. Es wurde kein Geraet verwendet.

## Ereignispfad

Die drei Encoder gelangen ueber `0xC00419B4(index, delta)` in die Firmware. `delta` ist vorzeichenbehaftet: eine Rastung im Uhrzeigersinn kam als `1`, gegen den Uhrzeigersinn als `0xFFFFFFFF` (-1) an. Vor der UiTask-Benachrichtigung vom Typ `5` rufen Sample/OSC, MOD TYPE und IFX TYPE `0xC0048460` mit ihrem feldspezifischen Code auf.

Die Tasten legen zuerst ein Ereignis vom Typ `1` in die UiTask-Queue. `0xC00700D8` verarbeitet das Ereignis. Setteraufrufe und DSP-Host-Port-Zugriffe, die danach auftreten, sind Teil der Verarbeitung des Tastendrucks. Die UiTask-Benachrichtigung selbst ist kein Nachweis fuer einen DSP-Refresh.

## Encoder in beide Richtungen

**Offline im Emulator.** Fuer jeden der drei Encoder wurde aus dem Startwert je eine Rastung `+1` und `-1` in derselben frischen Firmwareinstanz gesendet. Der Part-Wert stieg und fiel jeweils um eins und kehrte zum Startwert zurueck; es gab keine Assertion. Es war ein Richtungs- und Reihenfolgetest, kein Durchlauf aller Sample-, Modulations- oder Effekttypen.

| Encoder | Feld im Part-Datensatz | Wert `+1`, dann `-1` | Reihenfolge beim negativen Schritt |
|---|---:|---|---|
| Sample/OSC | `+0x08` | `0 -> 1 -> 0` | `0xC0048460` betritt den Pfad noch mit Wert `1`; das Feld wird auf `0` geschrieben, danach beginnt der 32-Wort-Transfer an `0xFF900A34` |
| MOD TYPE | `+0x10` | `0 -> 1 -> 0` | `0xC0048460` betritt den Pfad noch mit Typ `1`; Typ, Speed und Depth werden innerhalb des Pfads auf ihre Werte fuer Typ `0` gesetzt. Kein neuer typabhaengiger Schreibblock im unmittelbaren Fenster; nach einer Note unterscheidet sich der DSP-Datenstrom vom Zustand mit Typ `1` |
| IFX TYPE | `+0x21` | `0 -> 1 -> 0` | `0xC0048460` betritt den Pfad noch mit Wert `1`; das Feld wird auf `0` geschrieben, danach folgen je drei 64-Wort-Transfers an `0xFF900018` und `0xFF900098` |

Damit liegt der Eintritt in `0xC0048460` zeitlich vor der RAM-Schreibstelle; die Routine beziehungsweise ihr aufgerufener Pfad schreibt den neuen Wert aber vor den beobachteten DSP-Schreibtransfers. Ein separates Refresh-Bit wurde nicht gefunden. Das bestaetigt nicht, dass der DSP-Platzhalter die Daten verarbeitet oder dass der Klang am Geraet sofort wechselt.

## Aufloesung von `0xC00419B4`

**Offline im Emulator.** Direkte Aufrufe von `0xC00419B4` mit den Encoder-Indizes `1`, `3` und `4` sowie `delta` `1` und `0xFFFFFFFF` wurden in frischen Zustaenden verfolgt. `0xC00419B4` richtet den Kontext ein, ruft `0xC00418D0` mit Encoder-Index und Delta auf und ruft danach `0xC0083A18` auf. `0xC00418D0` prueft den Zustand und waehlt anhand des Encoder-Index den feldspezifischen Pfad: Index `1` fuer Sample/OSC, Index `3` fuer MOD TYPE und Index `4` fuer IFX TYPE. `0xC0059720` wurde in diesen Pfaden nicht aufgerufen.

Der Part ist kein Argument von `0xC00419B4`. `0xC00418D0` liest ihn aus dem Zustand des Sequenzermodells. Nach Auswahl von Part 3 bewegten dieselben Aufrufe nur die Hauptbytes und Mirrors von Part 3; Part 0 blieb unveraendert. Der Encoderpfad wirkt also auf den aktuell ausgewaehlten Part, nicht auf einen frei uebergebenen Part-Index.

Die feldspezifischen Pfade berechnen erst den neuen Wert und rufen dann `0xC0048460` auf. Dessen Aufruf erhielt die Codes `8`, `14` und `26`; der berechnete Wert und Flag `1` lagen auf dem Stack. Am Eintritt in `0xC0048460` stand im Pattern noch der alte Wert. Vor der anschliessenden `0xC0083A18`-Benachrichtigung waren das Hauptfeld und sein Mirror aktualisiert.

**Part-Index-Test der internen Routinen.** Nach der Kontextinitialisierung ueber `0xC00419B4` blieb Part 0 ausgewaehlt. Danach wurden die feldspezifischen Routinen direkt mit `(Kontext, Part, delta)` fuer jeden Part von 0 bis 15 aufgerufen: `0xC0041834` fuer Sample/OSC, `0xC0040F3C` fuer MOD TYPE und `0xC00412D4` fuer IFX TYPE. Fuer alle 48 Part-Routine-Paare aenderte `+1` nur die getrackten Werte des Ziel-Parts; anschliessendes `-1` stellte dessen Ausgangswerte wieder her. Die `0xC0048460`-Aufrufe enthielten jeweils `Part | 0x10` und den passenden Code `8`, `14` oder `26`. Das belegt, dass die internen Routinen einen expliziten Part entgegennehmen. Es macht `0xC00419B4` selbst nicht zu einem Setter fuer einen beliebigen Part: der oeffentliche Encoderpfad nimmt den Part weiterhin aus der Auswahl. Die internen Routinen verarbeiten Deltas und sind kein bestaetigter absoluter BLECH-Setter.

| Index | Feld und Apply-Code | Eine Rastung `+1` ab 0 | Eine Rastung `-1` ab 0 |
|---:|---|---|---|
| 1 | Sample/OSC, Code `8` | Sample `0 -> 1` | Sample `0 -> 0x0111` (273); der Pfad sucht den vorherigen nutzbaren Sample-Wert. Von `1` aus fuehrt `-1` wieder zu `0`. |
| 3 | MOD TYPE, Code `14` | Typ `0 -> 1`, Speed `0x17 -> 0x20`, Depth `0 -> 0x61` | Typ `0 -> 0x47` (71), Speed `0x17 -> 0x2A`, Depth `0 -> 0x7F` |
| 4 | IFX TYPE, Code `26` | Typ `0 -> 1` | Typ `0 -> 0x30` (48) |

Die Sample-Rastung `-1` ab 0 ist kein einfaches numerisches Unterlaufen des Feldes; die Sample-Routinen suchen in der Sample-Tabelle nach einem nutzbaren Wert. MOD TYPE laeuft im getesteten Zustand von `0` rueckwaerts auf `71`; `71` plus `1` lief in der Gegenprobe wieder auf `0`. IFX TYPE lief von `0` rueckwaerts auf `48`; `48` plus `1` lief wieder auf `0`. Beim IFX-Test blieb IFX Edit samt Mirror auf `0x40`.

## Beobachtungen

| Bedienung | Firmwarepfad | DSP-Host-Port im Emulator |
|---|---|---|
| Sample/OSC, Encoder 1 | `0xC0048460`, Code `8`, danach Ereignis Typ `5` | Neuer `0xAB`-Schreibtransfer an `0xFF900A34` mit 32 Woertern |
| MOD TYPE, Encoder 3 | `0xC0048460`, Code `14`, danach Ereignis Typ `5`; Speed und Depth aendern sich mit | Im direkten Encoderfenster kein neuer DSP-Transfer. Bei einer anschliessenden Note unterscheidet sich der DSP-Datenstrom vom Startzustand. Nach Rueckkehr des Modulationstyps zum Startwert entspricht die Zahl unterschiedlicher Payloads wieder dem Ausgangslauf. |
| IFX TYPE, Encoder 4 | `0xC0048460`, Code `26`, danach Ereignis Typ `5` | DSP-Transfers an `0xFF900018` und `0xFF900098`, darunter `0xAB`-Schreibtransfers mit 64 Woertern. Zusaetzlich wurde ein `0xA9`-Lesezugriff an `0xFF803CF8` beobachtet. |
| LPF, HPF und BPF | Ereignis Typ `1`, UiTask-Verarbeitung; kein Aufruf von `0xC0048460` oder `0xC0059720` | Mehrere `0xAB`-Schreibtransfers an `0xFF900A34`; die Payloads aendern sich passend zum Filtertyp. |
| MFX SEND | Ereignis Typ `1`, danach `0xC0059720` mit Setter-ID `18` | Veraenderter `0xAB`-Schreibtransfer an `0xFF900A34` |
| IFX ON | Ereignis Typ `1`, danach `0xC0059720` mit Setter-ID `17` und Wert `127` beim Einschalten | Veraenderter `0xAB`-Schreibtransfer an `0xFF900A34` |
| AMP EG | Ereignis Typ `1`; Pattern-Byte und Mirror werden gesetzt, ohne Aufruf von `0xC0048460` oder `0xC0059720` | Beim Tastendruck allein kein neuer DSP-Transfer. Bei einer Note nach dem Einschalten stieg die Zahl der `0xAB`-Schreibtransfers an `0xFF900A34` im 300-ms-Fenster nach Note-on von 1.123 im ausgeschalteten Lauf auf 3.016 im eingeschalteten Lauf. Der Aufruf `0xC005AD44` fuer Note-on wurde in beiden Laeufen beobachtet. |

Beim MOD-TYPE-Notenvergleich aenderte sich auch die DSP-Transaktionsmenge mit der Laufzeit. Deshalb werden hier die Unterschiede der Payloads, nicht die Transaktionszahlen, als Befund festgehalten. Bei AMP EG belegen die Messwerte einen anderen Host-Port-Datenstrom nach Note-on; sie belegen keine hoerbare Klangwirkung.

## Kontrolllauf fuer die vier Tastenfunktionen

**Offline im Emulator, 2026-11-08.** Mit eigener Hacktribe-`SYSTEM.VSB` und leerem Flash wurden IFX ON, AMP EG und MFX SEND auf Part 0 und Part 3 jeweils ein- und ausgeschaltet. LPF, HPF und BPF wurden auf beiden Parts je einmal betaetigt. Die Codebloecke wurden vor dem Setzen der Hooks verworfen, damit auch bereits uebersetzte Routinen erfasst wurden.

| Taste | Part-Feld und Mirror | Aufruf bei beiden Parts |
|---|---|---|
| IFX ON | Part 0 `0xC06B2FBC`, Mirror `0xC06B67E6`; Part 3 `0xC06B394C`, Mirror `0xC06B6852` | Kein `0xC0048460`. `0xC0059720` mit Setter-ID `17`, Wert `0` oder `0x7F`, Flag `1` |
| AMP EG | Part 0 `0xC06B2FB6`, Mirror `0xC06B67E4`; Part 3 `0xC06B3946`, Mirror `0xC06B6850` | Weder `0xC0048460` noch `0xC0059720`, auch beim Umschalten waehrend eines laufenden Sequenzers |
| MFX SEND | Part 0 `0xC06B2FB7`, Mirror `0xC06B67E5`; Part 3 `0xC06B3947`, Mirror `0xC06B6851` | Kein `0xC0048460`. `0xC0059720` mit Setter-ID `18`, Wert `0` oder `0x7F`, Flag `1` |
| LPF, HPF und BPF | Part 0 `0xC06B2FA8`, Mirror `0xC06B67D6`; Part 3 `0xC06B3938`, Mirror `0xC06B6842` | Weder `0xC0048460` noch `0xC0059720`; ausgehend von `1` ergaben sich `2`, `8` und `13` |

Damit ist fuer keine der vier Funktionen ein `applyCode` fuer `0xC0048460` beobachtet worden. IFX ON und MFX SEND benutzen stattdessen die bekannten Setter-IDs `17` und `18`. AMP EG und Filtertyp schreiben Pattern-Feld und Mirror direkt. Bei IFX ON, MFX SEND und den Filtertasten aenderten sich im Ereignisfenster die an `0xFF900A34` gesendeten Datenwoerter; das belegt CPU-Transfers, nicht die Klangwirkung des echten DSP.

## Gemeinsamer Dispatcher fuer Tasten-Updates

**Offline im Emulator, 2026-11-08.** Alle vier Tastenpfade rufen nach dem Schreiben des Hauptfelds `0xC004B208` auf. Die Funktion ist ein gemeinsamer Dispatcher mit feldspezifischem Code in `R2` und einem optionalen Refresh-Flag als erstem Stack-Argument. Sie aktualisiert das Mirror-Byte; bei gesetztem Flag ruft sie den jeweiligen Parameterpfad auf.

| Feld | Code in `R2` | Mirror-Offset relativ zu `R0 + Part * 0x24` | Aufgerufener Pfad bei gesetztem Flag |
|---|---:|---:|---|
| Filtertyp | `0x1D` | `0x22` | `0xC009A5EC(Part, Wert)` |
| AMP EG | `0x28` | `0x30` | `0xC009A700(Part, Wert)` |
| MFX SEND | `0x29` | `0x31` | `0xC009A704(Part, Wert)` |
| IFX ON | `0x2C` | `0x32` | `0xC009A764(Part, Wert)` |

Bei ausgewähltem Part 3 war `R0` die Mirror-Basis `0xC06B67B4` und `R1` hatte den Wert `3`; der Dispatcher gab `3` auch an die spezifischen Pfade weiter. Ein Gegenversuch ließ Part 0 ausgewählt und setzte beim Eintritt in den Dispatcher `R1` auf `3`: Auswahl und Hauptbyte von Part 0 blieben unverändert, während Mirror und Pfad `0xC009A5EC` Part 3 und den neuen Wert erhielten. Es gab keine Assertions.

Die beobachtete ABI eines direkten Aufrufs lautet `R0=0xC06B67B4`, `R1=Part-Index`, `R2=Code`, `R3=Refresh-Wert`; das erste Stack-Argument ist `1`. Bei `filterType` und `egOn` entspricht der Refresh-Wert dem Feldbyte. Bei `ifxOn` und `mfxSend` bleibt das Hauptbyte `0`/`1`, während der Refresh-Wert ausgeschaltet `0` und eingeschaltet `0x7F` ist.

IFX ON und MFX SEND erreichen den Dispatcher im nativen Pfad zuerst ohne Refresh und danach über die Setter `17` und `18` mit aktivem Refresh. AMP EG und Filtertyp rufen den Dispatcher dagegen direkt mit aktivem Refresh auf. Plugin-Zuweisungen gehen den Weg des jeweiligen Bedienelements, siehe [Part-Werte aus Plugins](2026-11-09-plugin-part-dsp.md). Der Dispatcher aktualisiert das Mirror-Byte und ruft den spezifischen Parameterpfad auf, ohne den ausgewählten Part zu ändern.

## Einordnung

Sample/OSC, IFX TYPE, Filtertyp, MFX SEND und IFX ON loesen in der simulierten Firmware Verarbeitung aus, die sich in DSP-Host-Port-Transfers zeigt. MOD TYPE ruft den Parameter-Aktualisierungspfad auf; sein Datenstromunterschied wurde nach einer Note beobachtet, nicht als unmittelbarer Transfer beim Encoderereignis. AMP EG veraendert in dieser Probe den spaeteren Notenpfad, nicht den DSP-Datenstrom beim Tastendruck.

Ein separates DSP-Refresh-Flag wurde in diesen Laeufen nicht beobachtet. Sichtbar sind Schreibtransfers der CPU ueber den DSP-Host-Port mit Kommando `0xAB` und konkreten Datenworten: Sample/OSC fuegt einen 32-Wort-Block an `0xFF900A34` hinzu, IFX TYPE Effektbloecke mit je 64 Woertern an `0xFF900018` und `0xFF900098`. MOD TYPE ruft den Aktualisierungspfad auf, aber im unmittelbaren Encoderfenster kommt kein zusaetzlicher Schreibblock hinzu; erst der Notenpfad erzeugt einen vom Ausgangslauf abweichenden Datenstrom. Das spricht fuer konkrete Parameteruebertragungen statt eines einzelnen Refresh-Bits.

Der DSP-Platzhalter rendert kein Audio und prueft weder die Uebernahme durch den echten DSP noch den Klang. Dafuer ist eine getrennte Geraete- und Hoerprobe noetig.

## Probe fuer den BLECH-Aufruf

**Offline im Emulator, 2026-11-07.** Die Aufrufe der drei physischen Encoder wurden an `0xC0048460` abgefangen. In allen drei Faellen waren die Register `(Kontext, Part | 0x10, 0, Code)` und die beiden Stack-Werte `(neuer Wert, 1)`. Die Codes waren `8` fuer Sample/OSC, `14` fuer MOD TYPE und `26` fuer IFX TYPE.

Die Apply-Funktion wurde danach getrennt mit Stack-Flag `0` und `1` aufgerufen. Bei Code `8` erschien der 32-Wort-Transfer an `0xFF900A34` nur mit Flag `1`. Bei Code `26` erschienen die sechs 64-Wort-Transfers an `0xFF900018` und `0xFF900098` ebenfalls nur mit Flag `1`. Code `14` veraenderte Typ, Speed und Depth wie der Encoder, sendete aber mit keinem der beiden Flags sofort einen neuen typabhaengigen Block. Die neun SLOTS-Bytes nach dem Aufruf entsprachen dem Encoderlauf. Das bestaetigt die Argumente fuer `0xC0048460`, aber nicht automatisch einen zusaetzlichen Setter-Aufruf.

Ein Hook auf `0xC0059720` sah waehrend der drei Encoderbewegungen keinen Aufruf. Auch nach einer Note auf MOD TYPE folgte kein Setter-Aufruf.

Ein direkter Aufruf von Code `8` mit denselben Registern und Stack-Werten setzte den Sample-Wert ebenfalls auf `1` und sendete 32 Woerter. Die letzten zehn Woerter unterschieden sich jedoch vom Encoderlauf: dort waren es zehnmal `0x3333`, beim direkten Aufruf zehnmal `0x4444`. Das direkte Aufrufen aus dem Emulator-Tick bildet also nicht den vollstaendigen Aufrufkontext des Encoders nach.

**Setter-IDs.** Die Dispatch-Tabelle von `0xC0059720` nimmt die IDs `1` bis `19` an. Die bereits bekannten Part-Setter verwenden die IDs `2` bis `14` sowie `17` und `18`. Die verbleibenden Handler fuer ID `15`, `16` und `19` benutzen die Sprungtabellencodes `4`, `5` und `2`.

**Part-Index-Gegenprobe.** In getrennten Emulatorlaeufen wurde `0xC0059720` fuer Part 0 und Part 3 mit dem jeweiligen Argument `Part + 1` aufgerufen. ID `1` schrieb bei Part 3 an `0x403C + 3 * 0x24`, ohne das Byte von Part 0 zu aendern. ID `15`, `16` und `19` schrieben dagegen auch bei Part 3 weiter an den festen Part-0-Offsets `+6`, `+7` und `+4`; die entsprechenden Bytes von Part 3 blieben unveraendert. Diese drei IDs sind damit keine Setter fuer explizite `korg.parts[i]`-Zuweisungen.

Ein Vergleich mit einem wirkungslosen Aufruf aus demselben Tick zeigte fuer ID `1`, `15`, `16` und `19` dieselbe periodische DSP-Pollfolge an `0xFF900A34` und keinen zusaetzlichen Nicht-Poll-Transfer. Die fruehere Zuordnung eines 64-Wort-Schreibtransfers an `0xFF900018` zu den IDs `15`, `16` und `19` liess sich in dieser kontrollierten Gegenprobe nicht reproduzieren und wird daher nicht als bestaetigter Messbefund gewertet.

ID `1` benutzt Code `25` und schreibt ein Byte an die per-Part-Adresse `0x403C + Part * 0x24`; der Handler ruft danach keine weitere Funktion auf. Die Konvertierungsfunktion ist ein unmittelbares `bx lr`. Nach Aufruf mit den Sample-Werten `1`, `300`, `512` und `999` stand dort jeweils nur das untere Byte des Werts. Das ist kein ausreichender Nachweis, dass ID `1` der Setter fuer das 16-Bit-Feld `sample` ist.

Die Codes `33` und `42` der Handler-Sprungtabelle speichern an den Part-Offsets `+0x26` und `+0x33`, aber keine der IDs `1` bis `19` in der Setter-Tabelle waehlt diese Codes aus. Ein passender Setter fuer `modType` oder `ifxType` wurde in `0xC0059720` damit nicht gefunden. Die Probe belegt weder einen alternativen Setter noch eine sofortige Klangwirkung am Geraet.

Ein direkter Versuch mit ID `20` endete im Emulator in einem ungemappten Instruktionsabruf. IDs ausserhalb des Tabellenbereichs sind daher keine sicheren Kandidaten.
