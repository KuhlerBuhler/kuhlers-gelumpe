# Sample-Metadaten im RAM, 2026-10-07

- **Gemessen:** Das neue Leseskript wurde vor Gerätezugriff gegen SimDevice,
  Kanal 9, mit der eigenen SYSTEM.VSB und einer transienten Metadaten-Fixture
  aus dem vorherigen Dump geprüft: 18 Anfragen, korrekte Dekodierung und
  vollständige SHA-256-Übereinstimmung der Antworten, keine Simulationsfehler.
  Die Fixture enthält kein Audio und prüft keine Wirkung von Parameteränderungen.
- **Gemessen:** Am Gerät beantwortet: 18 reine RAM-Leseanfragen, zusammen
  6.984 Byte, für die nullbasierten Indizes 500, 503, 652, 654, 711 und 723.
  Keine Schreib-, Execute- oder DSP-Portbefehle; kein Timeout.
- **Gemessen:** Referenz ist das geprüfte SD-Backup von 03:08:27,
  SHA-256 `38f8575c1f1032f038e80a7cd281cf9979366a86ee80f04d286ccb35d9cd4586`.
  Die SD-Karte war bei dieser Prüfung nicht mehr am Mac eingehängt.

## Feldzuordnung

Jede Zuordnung in der Tabelle ist **gemessen durch Bytevergleich** mit
`esli` der SD-Datei. `i` ist der nullbasierte Sample-Index. Die Audio-Offsets
sind keine bestätigten CPU-RAM-Adressen.

| Tabelle und Eintragsadresse | Offset im Eintrag | Wert / SD-Entsprechung |
|---|---|---|
| Name: `0xC047B080 + i * 0x20` | `+0`, 12 Byte | `esli[22:34]`, feste Headerdaten |
| Name | `+12`, 16 Byte | Name, `esli[2:18]` |
| Name | `+28`, u16 LE | Kategorie, `esli[18:20]` |
| Name | `+30`, u16 LE | Import-Nummer, `esli[20:22]` |
| Playback: `0xC0362EE8 + i * 0x10` | `+0`, u32 LE | Audio-Offset plus Startwert aus `esli[40:44]` |
| Playback | `+4`, u32 LE | Loop-Wert, `esli[44:48]` |
| Playback | `+8`, u32 LE | End-Wert, `esli[48:52]` |
| Playback | `+14`, u8 | One-Shot, `esli[52]` |
| Playback | `+15`, u8 | Unbekanntes Byte, gleich `esli[53]` |
| Metadaten: `0xC036AD88 + i * 0x45C` | `+0`, u32 LE | Vermuteter Audio-Offset |
| Metadaten | `+4`, u32 LE | PCM-Bytelänge, `esli[60:64]` |
| Metadaten | `+9`, u8 | Stereo-Flag, `esli[65]` |
| Metadaten | `+10`, u8 | Play-Level-Flag, `esli[66]` |
| Metadaten | `+16`, u32 LE | Samplerate, `esli[72:76]` |
| Metadaten | `+21`, i8 | Tune, `esli[77]` |
| Metadaten | `+22`, u16 LE | Wiederholter Index, `esli[78:80]` |
| Metadaten | `+24`, 64 × 16 Byte | Slice-Records, `esli[80:1104]` |
| Metadaten | `+1048`, 64 Byte | Slice-Steps, `esli[1104:1168]` |
| Metadaten | `+1112`, u8 | Step-Anzahl, `esli[1168]` |
| Metadaten | `+1113`, u8 | Beat, `esli[1169]` |
| Metadaten | `+1114`, u8 | Anzahl aktiver Steps, `esli[1170]` |

## Prüfergebnis und Grenzen

- **Gemessen:** Im alten Dump passen Kategorie, Import-Nummer, feste
  Headerdaten, PCM-Länge, komplette Metadaten ab `+4`, Start/Loop/Ende
  und One-Shot für alle 239 Samples. Bei Namen passen 238/239 zum neuen
  Backup; die einzige Abweichung ist die inzwischen erfolgte Umbenennung
  von Index 652 von No!! zu Blech.
- **Gemessen:** Beim frischen Gerätezugriff stimmen alle genannten Felder
  für alle sechs geprüften Samples mit dem neuen Backup überein. Gegenüber
  dem alten Dump sind ausschließlich die bereits bekannten fünf Namensbytes
  von Index 652 verändert; die Playback- und Metadateneinträge sind gleich.
- **Gemessen:** Index 723, E.Bass 2/125, hat One-Shot 0, Loop-Wert 0,
  32 Steps und 16 aktive Steps. Alle 64 Slice-Records und die 64 Step-Bytes
  stimmen bytegenau mit der Datei überein; 24 Slice-Records enthalten
  mindestens einen nicht null gesetzten Wert. Indizes 654 und 711 haben
  Tune -16; auch dies passt im frischen RAM zur Datei.
- **Gemessen:** Die Bank enthält 13 Einträge mit One-Shot 0 und 226 mit
  One-Shot 1; 235 Loop-Werte sind nicht null. Alle 239 relativen Startwerte
  sind null. Die Startwert-Formel ist daher noch nicht mit einem nicht null
  gesetzten Startpunkt getestet.
- **Gemessen:** Playback `+12`, u16 LE, ist bei den sechs frischen Einträgen
  null und stimmt nicht mit der Playback Period aus `esli[34:36]` überein.
  Beispiel Ringy: RAM 0, Datei 17126. Das Feld wird nicht als Playback Period
  zugeordnet. Lautstärke und Playback Period sind im RAM noch nicht lokalisiert.
- **Vermutet:** Die Tabellen liefern die vom Sampler verwendeten Metadaten.
  Struktur und aktueller Inhalt sind lesend bestätigt; eine kausale Wirkung
  von Änderungen auf Wiedergabe oder Anzeige ist für diese Parameter noch
  nicht geprüft. Der frühere Namensversuch bestätigt nur das Namensfeld.
- **Vermutet:** Start/Loop/Ende beziehen sich intern auf Byte-Offsets. Einheiten
  und Umrechnung zur Geräteanzeige sind hier noch nicht unabhängig geprüft.
  Die Slice-Feldnamen stammen aus dem Dateiformat; ihre Wirkung im Gerät
  ist durch bloße Bytegleichheit noch nicht bewiesen.

Keine Firmware-, Pattern- oder Sample-Audiodaten sind in diesem Dokument enthalten.

## Tune-Schreibtest, ausdrücklich freigegeben am 2026-10-07

- **Gemessen:** Der begrenzte Test wurde zuvor mit SimDevice, Kanal 9,
  eigener SYSTEM.VSB und transienter Fixture der zuletzt gelesenen
  Metadateneinträge geprüft. Tune 0 → -12 → 0 ändert nur ein Byte;
  doppelte Wiederherstellung wird vor einem Schreibheader abgewiesen,
  ein falscher Header-ACK stoppt vor dem Datenpaket. Keine Simulationsfehler.
- **Gemessen:** Bei Sample 653, nullbasierter Index 652, Blech, liegt Tune
  bei `0xC041C7ED`, Metadateneintrag `0xC041C7D8 + 21`. Originalwert 0
  wurde zusammen mit dem vollständigen 1.116-Byte-Eintrag und dem
  16-Byte-Playback-Eintrag vor dem Schreiben außerhalb der Repositories
  gesichert. Name Blech und Originalwert 0 wurden als Vorbedingung gelesen.
- **Gemessen:** Ein ausdrücklich freigegebener Schreibheader und ein
  Datenpaket setzten ausschließlich dieses Byte auf `0xF4`, i8 -12.
  Beide Antworten hatten Funktion `0x21`. Zurücklesen: Tune -12,
  alle anderen 1.115 Metadatenbytes und alle 16 Playback-Bytes unverändert.
- **Gemessen, am Gerät beim Anspielen bestätigt:** Mit Tune -12 änderte
  sich die hörbare Tonhöhe von Blech. Die Größe der Änderung wurde nicht
  gemessen; -12 wird hier nicht als zwölf Halbtöne oder eine Oktave belegt.
  Ob ein erneutes Auswählen des Samples nötig war, ist nicht bestätigt.
- **Gemessen:** Danach wurde ausschließlich das Tune-Byte aus der Sicherung
  auf 0 zurückgesetzt. Der gesamte 1.116-Byte-Metadateneintrag stimmt im
  abschließenden Zurücklesen exakt mit dem gesicherten Original überein;
  die 16 Playback-Bytes sind unverändert und der Name bleibt Blech.
  Keine Sample-/Pattern-Dateien oder DSP-Ports wurden beschrieben.
- **Vermutet:** Das Tune-Metadatenfeld wirkt auf die Wiedergabe des Samples.
  Ein einzelner Versuch mit einer am Gerät bestätigten Tonhöhenänderung
  stützt dies; Skalierung, Zeitpunkt der Übernahme und andere Parameter
  sind weiterhin offen.

## Unbenutzte Plätze und Schreiben im Emulator, 2026-10-15

Alles hier ist im Emulator gemessen (Firmware 2.02 mit Hacktribe, Start ohne Sample-Karte), am Gerät
nichts. Ein Emulatorergebnis ist keine Gerätemessung.

- **Gemessen (Emulator):** Ohne `e2sSample.all` auf der Karte tragen alle Plätze von Index 499 (Sample 500)
  bis Index 997 den Namen `SampleNNN` mit NNN gleich Index plus 1 (`Sample701` bei Index 700), auch weiter
  unten steht er noch (Index 498 heißt `Sample499`). Dazu steht im
  Metadateneintrag Samplerate 48000, PCM-Länge 0, Tune 0 und der wiederholte Index (`+22`) gleich dem
  Index. Von 998 Namen sind 724 solche Standardnamen, die übrigen 274 sind Werksnamen (`SAW`, `PULSE`, `VPM-SAW 1`
  und so weiter). Ein leerer Name ist also kein Zeichen für einen unbenutzten Platz, die PCM-Länge 0
  ist das einzige gemessene Merkmal. Ob ein echtes Gerät dieselben Standardnamen trägt, ist nicht gemessen.
- **Gemessen (Emulator):** Name und Tune wurden an Index 700 über den Editor geschrieben (Plan, Türsteher,
  Sicherung, Zurücklesen) und wieder zurückgenommen. Verändert haben sich nur die Namensbytes, die sich
  zwischen `Sample701` und dem neuen Namen unterscheiden, und das Tune-Byte `+21`. Die Wiedergabetabelle blieb
  gleich, der übrige Metadateneintrag auch, die Firmware antwortete danach weiter. Test:
  `test/emulator-sample-meta.test.mjs`.
