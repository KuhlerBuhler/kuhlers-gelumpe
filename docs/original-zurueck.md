# Zurück zu Korgs Original

Stand: 6. November 2026. [English](original-zurueck.en.md). Die Anleitung für alle, die BLECHTRIBE (oder Hacktribe) wieder von
ihrer Electribe haben wollen, mit Schwerpunkt auf der blauen. Marker wie überall: **gemessen** (am Gerät oder im Emulator,
die Messung ist genannt), **hergeleitet**, **offen**. Am Gerät ist der Weg für die blaue noch nicht gegangen worden, alles
dazu ist im Emulator gemessen.

## Geht das?

**Ja, auch auf der blauen.** BLECHTRIBE ersetzt Korgs Firmware wie ein Update von Korg, über SOFTWARE UPDATE von der
SD-Karte. Der Rückweg ist dasselbe noch einmal mit Korgs unveränderter Datei. Dafür sorgt, was die Installation am Gerät ändert:

| Behauptung | Marker | Beleg |
|---|---|---|
| Hin (Korgs blaue zu BLECHTRIBE-Synth-Satz) und zurück (Korgs Datei im selben Ordner) schreiben beide nur `[0x020000, 0x220000)`, 512 Löschbefehle und 8192 Programmierungen; Bootloader, Nutzerbereich und PCM-Bank bleiben gleich | gemessen (Emulator) | [Messung 15.10.](messungen/2026-10-15-blaue-electribe.md), Abschnitt SOFTWARE UPDATE der blauen |
| Nach Hin und Zurück ist der ganze 16-MiB-Flash byteweise gleich dem Stand davor | gemessen (Emulator) | dieselbe Messung |
| BLECHTRIBE-Synth-Satz liest nach der ersten Installation `KORG/blechtribe/System/SYSTEM.VSB`; Korgs unveränderte blaue Datei von dort schreibt Korgs Firmware zurück, Neustart bis zum Hauptbild | gemessen (Emulator) | [Messung 26.10.](messungen/2026-10-26-blech-hacktribe-blau.md), Abschnitt Kartenordner |
| Läuft Hacktribe (auch mit BLECHTRIBE) auf der blauen, nimmt das Update Korgs blaue Datei nur mit dem Kopf des Samplers (Byte `0x12` auf `0x53`, Byte `0x2E` auf `0x24`); unverändert sagt es "Invalid File" und schreibt nichts | gemessen (Emulator) | Messung 26.10., Tabelle Update-Wege |
| Die Einstellungen von BLECHTRIBE liegen auf der Karte (`KORG/blechtribe/`), nicht im Flash; der Patcher fasst den Bootloader nie an | offline (Code) | [Rettung](rettung.md), [Patcher](patcher.md) |
| Der Weg am echten Gerät: Hin und Zurück über Korgs Update ist am 10.10. auf einem Gerät geübt, mit der roten | gemessen (Gerät, rot) | [Rückweg geübt](messungen/2026-10-10-rueckweg-geuebt.md) |
| Derselbe Weg auf einem echten blauen Gerät, ein Stromausfall mitten im Schreiben, Korgs Update ohne Netzteil | offen | braucht einen Test am Gerät |

Was die Installation also nicht ändert, und was deshalb nichts zum Zurückholen braucht: den Bootloader, den Nutzerbereich im
Flash mit deinen Patterns, die PCM-Bank. Das gilt für den BLECHTRIBE-Satz auf Korgs Synth-Firmware. Mit Hacktribe darunter ändert sich
mehr (anderer Code, Sampler-Firmware auf blauer Hardware), aber auch dort schreibt das Update nur den Firmware-Bereich (Messung 26.10.:
"Rest des Flashs gleich"). Ob die Werks-Patterns und Oszillatoren der blauen nach Hacktribe und zurück alle wieder da sind, ist **offen**.

## Welche Firmware läuft gerade?

Die Seite Rettung im Editor fragt das für dich: `Rettung -> Ich will zurück zu Korgs Original`. Von Hand:

- **Rot, BLECHTRIBE:** Korgs rote Datei (Sampler) in `KORG/blechtribe/System/`.
- **Blau, BLECHTRIBE ohne Hacktribe** (im Patcher mit Korgs blauer Datei gebaut): Korgs blaue Datei, **unverändert**, in `KORG/blechtribe/System/`.
- **Blau, Hacktribe oder BLECHTRIBE mit Hacktribe:** Korgs blaue Datei **mit Sampler-Kopf**, in `KORG/hacktribe/System/` (läuft Hacktribe) oder
  `KORG/blechtribe/System/` (läuft BLECHTRIBE). Die Seite Rettung macht die Datei aus deiner eigenen von Korg.

Weißt du nicht, welche läuft: BLECHTRIBE zeigt sich im Menü (`Menü -> BLECH -> VERSION`); ohne dieses Menü läuft kein BLECHTRIBE.

## Schritt für Schritt (blaue, BLECHTRIBE ohne Hacktribe)

1. **Karte sichern.** Den ganzen Inhalt der SD-Karte auf den Rechner kopieren.
2. **Korgs Firmware holen.** Bei Korg das System Update 2.02 für die Electribe (blau, nicht Sampler) laden, die Lizenz akzeptieren, die ZIP auspacken.
   Du brauchst daraus die `SYSTEM.VSB`. Die App führt dich dorthin (Rettung), der Patcher zeigt denselben Link.
3. **Auf die Karte.** Die Datei muss genau `SYSTEM.VSB` heißen (nicht `SYSTEM (1).VSB`) und in `KORG/blechtribe/System/` liegen, fehlende Ordner anlegen.
   Leg sie dort **allein** hin: Korgs Update fragt in diesem Ordner auch nach `BOOT.VSB`, `USER.VSB` und `PCM.VSB`; was dann passiert, ist nicht gemessen.
   In `KORG/electribe/System/` sucht eine laufende BLECHTRIBE nicht, dort bekommst du "Error, No File".
4. **Netzteil anstecken.** Ohne Netzteil sagt die Electribe "Battery Low" und schreibt nichts.
5. **Update starten.** Electribe einschalten, `DATA UTILITY`, letzte Seite `SOFTWARE UPDATE`, ENTER (Taste MENU), "Are You Sure?" bestätigen,
   "Working..." abwarten (nicht ausschalten), bei "OK. Please Reboot." aus- und wieder einschalten.
6. **Danach.** Die Electribe läuft mit Korgs Original. Korgs Firmware liest `KORG/electribe/`, nicht `KORG/blechtribe/`. Wer seine Patterns, Samples
   und Exporte von BLECHTRIBE behalten will, kopiert sie von `KORG/blechtribe/` nach `KORG/electribe/` (auf der roten `KORG/electribe sampler/`).
   Die Patterns im Gerät bleiben (Emulator, am Gerät offen); die Sicherung aus Schritt 1 deckt den Rest ab.

## Blaue mit Hacktribe

Die Datei von Korg geht so nicht durch ("Invalid File"). Die Seite Rettung nimmt Korgs `SYSTEM.VSB` für die blaue, prüft sie gegen Korgs 2.02
(jede andere Datei wird abgelehnt), ändert genau die zwei Kopf-Bytes und speichert das Ergebnis als `SYSTEM.VSB`. Die Datei bleibt auf deinem
Rechner. Dann Schritte 1 und 3 bis 6 von oben, mit dem Ordner der laufenden Firmware. Gemessen im Emulator
([Messung 26.10.](messungen/2026-10-26-blech-hacktribe-blau.md)), am Gerät **offen**.

## Wenn es hängt

Fehlermeldungen und die Fälle "Startabfrage", "00" und "nichts" stehen in [Rettung](rettung.md) und im Editor unter Rettung.
Der Bootloader bleibt unberührt, deshalb endet ein Update, das nicht durchläuft, in der Regel in der Startabfrage von Korgs Firmware und nicht
im toten Gerät. Ganz ausschließen kann das niemand ([FAQ](faq.md)).

## Offen, braucht ein Gerät

- Den ganzen Weg auf einer echten blauen gehen: BLECHTRIBE ohne Hacktribe, dann Korgs Datei in `KORG/blechtribe/System/`.
- Dasselbe mit Hacktribe oder BLECHTRIBE mit Hacktribe und der Datei mit Sampler-Kopf.
- Ob ein Stromausfall mitten im Schreiben oder eine Karte mit `BOOT.VSB`, `USER.VSB` oder `PCM.VSB` im Ordner etwas anders macht.
