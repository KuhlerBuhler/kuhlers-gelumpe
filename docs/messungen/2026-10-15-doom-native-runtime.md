# Nativer Doom Adapter für den getrennten Startmodus

**Historischer Befund vor der Integration von `integ/overnight`.** Die hier
genannten BLECH-v8-Artefakte und alten Speicheradressen sind kein aktueller
Gerätekandidat. Neue Firmware muss separat gebaut und geprüft werden.

Stand: 15. Oktober 2026. Dieser Bericht beschreibt den nativen Adapter;
der kombinierte Firmwarelauf ist in
[der Integrationsmessung](2026-10-15-doom-integration.md) ausgewertet.
Ein echtes Gerät wurde nicht beschrieben, geflasht oder ausgeführt.

## Aufbau

`tools/doom/runtime.c` ergänzt die unveränderte, gepinnte Doomgeneric Engine
um Electribe Treiberaufrufe. Es enthält keine Host SVCs, keine synthetischen
Tastendrücke und keine Host Dateizugriffe. Die Binärdatei wird von SD geladen.
Die ursprüngliche Machbarkeitsprobe bleibt unabhängig bestehen.

Das Linkerskript legt die erste ARM Instruktion auf `0xC1000000`.
Der Aufrufer setzt den Stack vorher auf `0xC1800000` und übergibt das
geteilte Statusobjekt auf `0xC0180000` in `r0`. Der Adapter löscht ausschließlich
seine eigene BSS, prüft Adresse, Magie und ABI Version und setzt Stufe 4.
Der Speicherbereich endet auf `0xC1800000`; die letzten 64 KiB gehören dem
Stack. Linker Assertions verlangen Platz für die 6 MiB Doom Zone und
mindestens weitere 256 KiB Heap. Ein Heap Überlauf liefert `ENOMEM`.

Die Engine startet E1M1 mit Gegnern, `-nosound` und `-nogui`.
Damit versucht der Fehlerpfad keine Desktop Dialoganwendung aufzurufen. Die Renderauflösung bleibt
320 mal 200. Der Adapter rechnet auf 128 mal 64 mit geordneter Ditherung um,
setzt dabei gemäß dem vorhandenen LCD-Modell Bit 1 für Schwarz und Bit 0 für Weiß,
kopiert 1024 Byte nach `0xC031B310` und ruft den echten SPI Displaypfad
`0xC0015DD0` für beide Hälften auf.

## Native Dienste

| Dienst | Aufruf oder Adresse | Grundlage |
| --- | --- | --- |
| WAD öffnen | `0xC009DB60`, Modus 1 | bestehende SD Probe und Laufzeitrecherche |
| Lesen | `0xC009DD74` | bestehende SD Probe |
| Schließen | `0xC009E3DC` | bestehende SD Probe |
| Seek | `0xC009E404` | Disassembly: `FIL+8` Position, `FIL+12` Größe |
| Panelqueue | `0xC0024B6C`, Objekt `0xC033E57C` | bestehende SD Probe |
| Millisekunden | Kernelwort `0xC06A2930` | Disassembly `0xC0000454` bis `0xC000059C` |

Die Zeit wird aus dem laufenden Kernel gelesen. Der Adapter erhöht keinen
Zähler selbst. `DG_SleepMs` wartet auf einen echten Tickabstand; Interrupts
bleiben im Zustand des Aufrufers. Der kombinierte Firmwaretest bestätigt 1000 Kernelticks je ungefähr einer
emulierten Sekunde; vollständige Werte stehen im Integrationsbericht.

Es gibt vier eigene, auf Wortgrenzen ausgerichtete `FIL` Objekte von je
`0x240` Byte. `_open` erlaubt nur `SD:/KORG/blechtribe/Doom/doom.wad` und
nur Lesezugriffe. Seek jenseits des Dateiendes oder negative Positionen werden
abgelehnt. Konfiguration, Speicherstände, Verzeichnisse und andere Pfade
werden nicht auf SD geschrieben. Standardausgaben gelangen in einen
umlaufenden, 2048 Byte großen Ring im geteilten Statusobjekt.

Die Zuordnung der Tasten verwendet die Konstanten der gepinnten `doomkeys.h`:
Part ab/auf bewegt vor/zurück, Edit links/rechts dreht, PLAY schießt, TAP
benutzt, REC bestätigt, MENU und EXIT öffnen beziehungsweise schließen
Dooms Menü. REC bestätigt auch Ja/Nein Dialoge, EXIT bricht sie ab:
Der Adapter setzt dafür nach der Engineinitialisierung `key_menu_confirm`
auf `KEY_ENTER` und `key_menu_abort` auf `KEY_ESCAPE`. Der Adapter liest maximal 32 Nachrichten je Abfrage, damit
unbekannte Nachrichten keinen unbegrenzten einzelnen Aufruf erzeugen.

## Buildnachweis

Quelle: Doomgeneric `e257a09527062bfb986b6e5e0780839b6cbd5b71`.
Der Builder verweigert andere Revisionen und lokale Änderungen an der Engine.
Werkzeug: Arm GNU Toolchain 14.2.Rel1, ARM926EJ-S, ARM Modus, Software FPU.

Ausführung im separaten Worktree:

```sh
python3 tools/doom/build_runtime.py \
  --source $doom_feasibility/engine/doomgeneric \
  --toolchain $doom_feasibility/engine/arm-gnu-toolchain-14.2.rel1-darwin-arm64-arm-none-eabi \
  --output $doom_artifacts/runtime-v3
```

Aktueller erfolgreicher Build: 450612 Byte Flatbinary, 243504 Byte BSS,
keine undefinierten Symbole. Entry `0xC1000000`, BSS
`0xC106E040` bis `0xC10A9770`, Heap bis `0xC17F0000`.
SHA256: `924e4e2b8c81b675eef81cb37121ecf9c6999a5f2720e9da96d6e0b10e57a1db`.
Der Linker meldet ein RWX LOAD Segment. Diese Bare Metal Anwendung verwendet
keinen ELF Programmlader; die SD Flatbinary liegt im vorgesehenen RAM.
Daraus folgt keine Aussage über Speicherschutz auf echter Hardware.

Buildlog: `$doom_artifacts/runtime-v3-build.log`. ELF, Binärdatei, Map,
Symboltabelle und Manifest liegen ausschließlich außerhalb des Repos unter
`$doom_artifacts/runtime-v3/`.

## Isolierte ARM Adaptertests

`runtime_tests.py` lädt genau die gebaute ARM Binärdatei und führt die
Adapterfunktionen mit Unicorn aus. Die Firmwarefunktionen sind in diesem
isolierten Test ausdrücklich simuliert. Die Prüfung belegt daher
Adapterlogik und ARM Ausführung, keine funktionierende SD Hardware.

```sh
python3 tools/doom/runtime_tests.py \
  --build $doom_artifacts/runtime-v3 -v
```

Gemessen: 12 Tests erfolgreich in 0,491 Sekunden. Log:
`$doom_artifacts/runtime-v3-unit.log`.
Geprüft sind Pfadgrenze und Schreibschutz, vier Dateiplätze und deren
Wiederverwendung, Leseergebnisse und Statistik, Seek mit negativen und zu
großen Positionen, Fehlerantworten, vollständige Heapgrenze, alle neun
Tasten inklusive Loslassen, begrenztes Verwerfen unbekannter Nachrichten,
Zeit ohne selbst erzeugten Fortschritt, Zeitüberlauf und extern getaktetes
Warten, Konsolenüberlauf sowie die beiden nativen SPI Aufrufe nach einer
vollständig weißen und vollständig schwarzen Bildumrechnung. Weitere Prüfungen belegen sichtbare
Fehlerzustände und die STOPPED Anzeige nach dem Quit Wrapper.

## Beenden und Fehler

Der gepinnte Port führt in `I_Quit` seine Aufräumfunktionen aus, ruft aber
wegen `ORIGCODE` kein `exit` auf. Der Linker leitet Aufrufe deshalb mit
`--wrap=I_Quit` an einen eigenen Wrapper weiter. Dieser ruft zuerst die
echte Aufräumfunktion auf und beendet anschließend den Doom Task in einer
Warteschleife mit Stufe 6. Das Display zeigt `DOOM STOP` und `POWER OFF`.
Ein Fehler zeigt `DOOM ERROR`, `POWER OFF` und den achtstelligen Hexcode.
Das gemeinsame, libc freie `status_display.h` verwendet einen eigenen
kleinen Glyphsatz und denselben echten SPI Treiber wie die Bildausgabe.

`native_power.h` prüft echte Panelmeldungen vom Typ 6. Loslassen mit Wert 0
bewirkt nichts; Drücken mit Wert 1 ruft ausschließlich den letzten nativen
Stromhalteaufruf `0xC001734C(0x01E26000, 1)` auf. Die volle Sampler
Ausschaltroutine mit Einstellungsverwaltung und Flashspeichern wird nicht
verwendet. Dieser letzte Aufruf löscht über `0xC0016BB4` den GPIO 7.11.
Nach der Anforderung läuft die Engine nicht weiter.

Das lässt sich getrennt im Emulator belegen: derselbe native Endaufruf
führt im Doomzweig ohne SD von `powered=true` zu `powered=false`, bei
Tasks 1 und 8, ohne Sampler und ohne Assertions. Beleg:
`$doom_artifacts/power-call.json`.
Die beiden zusätzlichen ARM Tests prüfen Weiterleitung, Loslassen und
Fehlererhalt mit simuliertem GPIO Dienst. Der kombinierte Produktlauf
muss zusätzlich den Meldungsweg über den wirklichen Panel UART belegen.

Im Spiel verarbeitet `DG_GetKey` die Powernachricht. Während des ersten
WAD Ladens prüft `_read` die Queue nach jedem Dateilesen und verwirft
andere frühe Eingaben. Sobald das Spiel läuft, bleibt die Eingabe vollständig
bei `DG_GetKey`. Fehler und reguläres Quit warten ebenfalls auf den
Powerknopf. Die echte Stromversorgung und das erneute Einschalten bleiben
ein manueller Gerätetest durch den Gerätebesitzer.

## Integration und Testmetadaten

Die Produktmatrix mit passender Referenz `SYSTEM-blech-v8.VSB` ist für den
zweiten Build erfolgreich: 34 von 34 Prüfungen. Sie vergleicht Normalstart,
EXIT, Doom Kombination plus EXIT, alle elf bestehenden Startmodi und
Firmware Updatewege mit dem tatsächlichen gepatchten Produktimage.
Geprüft sind Aufgaben, Sampleraufrufe, Assertions, Bildschirm und sämtliche
LED Werte. Es wird kein Diagnoseprogramm in den Referenzlauf injiziert.
Die weiteren Fälle prüfen fehlende Karte, fehlendes oder falsches Programm,
SHA Fehler, fehlende oder ungültige WAD sowie Power im Fehlerzustand und
während der nativen Engineinitialisierung. Die Powerfälle laufen über
Panel UART und echte Firmwarefunktion; weder voller Sampler Powerpfad noch
Schreibzugriffe werden dabei ausgeführt.

Beleg: `$doom_artifacts/regression-v2/regression.json`.
Produktimage SHA256:
`b6e22dc9ad6bb22e67869a9714d6e76f636aa89549447bf777367074464f9287`.
Die frühere Matrix verwendete versehentlich `SYSTEM.VSB` als Referenz zu
einem aus `SYSTEM-blech-v8.VSB` gebauten Produkt. Dieser Vergleich ist kein
Regressionsbeleg. Der Prüfer verweigert inzwischen jede Basis, die sich
außerhalb der ausgewiesenen Doom Bereiche vom Produkt unterscheidet.

`runtime_layout.c` erzeugt ausschließlich Compiler Metadaten über
`player_t` und `mobj_t`. Der Builder kompiliert sie in ein eigenes Objekt
mit Section `.doom_layout`; dieses Objekt wird nicht in die Engine gelinkt.
`--layout-only` erstellt `layout.json`, ohne die Engine Binärdatei zu ändern.
Die erneute SHA Prüfung bestätigt weiterhin den oben angegebenen Runtime
Build. Ermittelt sind: Spielergröße 284 Byte, Objektpointer bei 0,
Ammunition bei 160 mit vier Byte je Slot, Waffe bei 120, Gesundheit bei 40;
Objektposition X und Y bei 12 beziehungsweise 16. Eine zusätzliche
Compilermessung bestätigt die Feldbreiten: `readyweapon` ein Byte,
`usedown` vier Byte und `boolean` vier Byte. Die Waffenkennung darf
daher nicht mit einem vier Byte breiten Lesezugriff interpretiert werden.
Damit können weitere
Integrationstests echte Spielzustände statt allein Tastenzähler prüfen.

Die native Uhr liefert im Doomzweig über 0,9999894 Sekunden genau 1000
Ticks. Dieser Abstand zwischen 1,5000106 und 2,5 Emulatorsekunden bestätigt
die Millisekundeninterpretation mit 10,6 Mikrosekunden Phasenabweichung.
Die Matrix fordert maximal einen Tick Abweichung.

## Darstellungsbefund und Bedienungsszenario

Die erste native Umrechnung setzte Bit 1 für helle Pixel. Das widerspricht
der vorhandenen LCD Darstellung in `machine.py`: Bit 1 ist dort schwarz.
Der dritte Runtime Build korrigiert die Polarität. Der ARM Test fordert
jetzt ausdrücklich 1024 Nullbytes für eine weiße Quelle und 1024 Mal
`0xFF` für eine schwarze Quelle. Die früheren Buildnachweise bleiben
Belege für den jeweiligen Stand; die endgültige Spielausgabe und Matrix
müssen mit dem dritten Build erneut geprüft werden.

`controls_scenario.py` erzeugt ausschließlich normale Panelnachrichten.
Es wartet auf echte Spielticks und prüft Blickrichtung, Spielerposition,
weniger Munition nach Schießen, `usedown` während Benutzen und reguläre
Menüwechsel. Das Szenario wählt über NEW GAME die zweite Episode, wartet
auf E2M1 und speichert ein frisches SPI Bild vor dem Quit Menü. Anschließend
bestätigt es Quit, verlangt STOPPED ohne Fehler und betätigt den
Powerknopf. Die aktuellen Menüobservablen und Compiler Offsets werden
vom Runner geliefert; der Controller verändert keinen Enginezustand.
Die neu erzeugte Metadatenkonstante für `usedown` liegt bei Spielerbyte
196. Der tatsächliche Erfolg dieses Szenarios muss der integrierte
Produktlauf belegen, nicht die Syntaxprüfung des Controllers.

## Tonpfad: untersucht, nicht implementiert

**Aus Code gelesen:** Der aktuelle Port startet mit `-nosound`
(`tools/doom/runtime.c:228`). `build_runtime.py` definiert kein
`FEATURE_SOUND` und nimmt die Objekte aus `SRC_DOOM` des gepinnten
Makefiles. Diese Liste enthält `i_sound.c`, aber weder `i_sdlsound.c` noch
`i_sdlmusic.c`. Im gepinnten `i_sound.c` enthält `sound_modules` ohne
`FEATURE_SOUND` nur den Endmarker; `InitMusicModule` setzt ebenfalls nur
unter diesem Schalter ein Musikmodul. `I_InitSound` überspringt mit
`-nosound` die Initialisierung. Das Entfernen dieses Arguments allein
würde daher noch keinen Tonpfad ergänzen. Ein nativer Mixer, eine
PCM Warteschlange und ein Electribe Audiotreiber gehören nicht zum
Adapter. Die externe Enginequelle bleibt unverändert.

**Aus Emulatorcode gelesen:** `tools/emu/machine.py:681` ersetzt den
DSP Bootaufruf `0xC0011AB8` durch einen protokollierten Zeitpunkt und
ein festes Erfolgsergebnis 1. Es wird dabei kein DSP Programm ausgeführt.
Am Steuerport liefert `machine.py:291` stets den angenommenen Wert `0x81`.
Schreiben an den Datenport erhöht in `machine.py:338` lediglich die
Adresse und vermindert den Zähler; die PCM Wörter werden weder berechnet
noch als Ton ausgegeben. Lesen liefert in `machine.py:436` Werte aus dem
kleinen `dsp_mem` Wörterbuch, sonst 0. Das Modell ist daher kein
Audiogerätenachweis, selbst wenn alle ARM Aufrufe erfolgreich zurückkehren.

**Im Firmwareemulator gemessen:** Eine zusätzliche Beobachtung des dritten
Produktimages bis 0,8 Sekunden meldet sowohl beim normalen Start als auch
beim Doom Fehlerstart ohne Karte einen DSP Bootzeitpunkt von 56,18 ms.
Beim Doomstart laufen dabei ausschließlich Tasks 1 und 8; keiner der
überwachten Sampler Initialisierer wurde betreten. Beim Normalstart laufen
alle zehn Tasks, und die Sampler Initialisierer für Globals und Patterns
wurden betreten. Beide Läufe bleiben ohne Assertions.
Beleg: `$doom_artifacts/audio-path-observation.json`.
Das zeigt einen bereits vor der Anwendungswahl aufgerufenen DSP Bootpfad,
keinen ausgeschalteten DSP. Wegen des oben beschriebenen Ersatzmodells
belegt es allerdings keine tatsächlich gestartete oder hörbare DSP
Ausgabe auf dem Gerät.

**Vorhandene Offlinebelege:**
[Die Untersuchung der DSP Audiopfade](2026-10-08-dsp-audiopfade.md)
beschreibt `0xC004EF28` über `0xC0014284`, `0xC0014C34` und
`0xC00146B4`: CPU Wörter werden mit Kommando `0xAB` in den DSP Adressraum
übertragen. Diese Untersuchung ersetzt DSP Ports und GPIO und prüft
Sample Speichertransfers. Sie weist weder einen fortlaufenden PCM
Wiedergabering noch einen direkten DAC Aufruf nach. Sperren und Taskkontext
sind dort ausdrücklich Teil der Grenze. Der bekannte Exportpuffer
`0xC0D3A940` ist außerdem ein Arbeitsbereich für Dateien, kein belegter
Audioausgabepuffer.

**Aus bestehender DSP Forschung gelesen:**
[Der erste DSP Befund](../hintergrund/dsp-erster-blick.md)
führt einzelne reine Blackfin Funktionen im GNU Simulator aus. Dort fehlen
SPORT, DMA und HOSTDP Peripherie; es gibt ausdrücklich keine entsprechende
Zeitmessung. Die Dokumentation des SD Pfades mit MMC FIFO und ohne
programmiertes EDMA beschreibt den Kartenverkehr und belegt keinen
Audio DMA Pfad. Die zwei Fälle dürfen nicht miteinander gleichgesetzt
werden.

**Hergeleitet:** Nach den vorhandenen Belegen steht kein fertiger direkter
PCM Ausgabepfad für Doom ohne Samplerstart zur Verfügung. Das ist eine
Aussage zum untersuchten Code und Wissensstand, keine Behauptung, die
Hardware könne prinzipiell kein Audio. Der bereits aufgerufene originale
DSP Bootpfad könnte ein Ausgangspunkt sein. Ob dessen Wiedergabeprotokoll
ohne VoiceTask und Samplerverwaltung nutzbar ist, ist offen. Eine separate
Tonausgabe auf dem Host würde diese fehlenden Gerätebelege ebenfalls
nicht ersetzen.

**Offen für einen eigenen Folgeschritt:** Zuerst müssen Audioanschluss,
Wiedergabetakt, PCM Format, Puffereigentümer, Ringnachfüllung und
Unterlaufverhalten identifiziert werden. Darauf kann ein nativer Doom
Soundeffektmixer mit gemessener CPU Last, Speicherbedarf und
Cachepflege aufgebaut werden; Musik ist gesondert zu behandeln. Danach
braucht es einen durch den Gerätebesitzer manuell ausgeführten Gerätetest mit
bekanntem Signal und belegtem Ausgang. Es gibt hier weder einen solchen
Treiber noch eine vorbereitete Audiofreigabe. Die offene Tonaufgabe im
Doom Plan bleibt ausdrücklich unerledigt. Für diese Untersuchung wurden
keine Laufzeit, Binärdatei, Firmwaredaten oder Audioattrappen geändert.

## Grenzen

Der Build allein belegt keine laufende Engine mit Firmwaretreibern.
SD Durchsatz, Rendergeschwindigkeit, Stackspitze, Taktumrechnung,
Tastenreaktion und korrekte SPI Ausgabe benötigen den kombinierten Test.
Ton und Speicherstände sind nicht implementiert. Der Adapter meldet einen
Enginefehler als Fehlerstufe und ein reguläres Quit als STOPPED. Danach
wartet er jeweils auf die Powernachricht; es gibt keinen Rücksprung in die
Sampleranwendung.
