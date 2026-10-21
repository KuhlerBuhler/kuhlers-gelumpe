# Display-Kalibrierung über den vorhandenen Kontrastregler

Stand 21.10.2026. Neue Darstellung auf der vorhandenen Seite **Global, LCD CONTRAST**
(Seite 13, Index 12). Sie zeigt **CALIBRATE DISPLAY**, den Kontrastwert und drei Bälle,
die sich mit unterschiedlicher Geschwindigkeit bewegen. Das VALUE-Rad stellt weiterhin
den ursprünglichen Kontrast ein. Die Darstellung ist eine Einstellhilfe; sie ermittelt
keinen automatischen Messwert für das physische LCD.

## Aufbau

`tools/patch/script_calibrate.s` wird im vorhandenen Rahmenhaken der Laufzeit aufgerufen.
Nur auf dem Global-Bildschirm 9 mit Seitenindex 12 und ohne offenes Fenster zeichnet es
in die mittleren sechs Seiten des Displaypuffers. Kopfzeile und unterste Zeile bleiben
bei der Firmware. Andere Bildschirme und Dialoge werden nicht überzeichnet. Der
EXIT-Notschalter beim Start umgeht weiterhin die Laufzeit und damit auch diese Darstellung.

Es gibt keinen neuen Eingabe-, Speicher- oder Kontrastschreiber. VALUE, WRITE und EXIT
bleiben im Originalcode. Das Darstellen liest den Kontrast aus dem bestehenden Global-Block.
Der Bereich bleibt Byte 18 bis 42, auf dem Display 1 bis 25, wie in der
[Global-Messung](2026-10-14-global-felder.md) nachgewiesen.

Die Bälle laufen auf getrennten Zeilen mit dem Geschwindigkeitsverhältnis 1:2:4. Ihre
Position stammt aus dem vorhandenen Rahmenzähler. Es werden keine weiteren dauerhaften
RAM-Bereiche reserviert. Die eigene Schrift der Laufzeit wird wiederverwendet. Einschließlich
des zusätzlichen Aufrufs beansprucht die Darstellung 516 Byte Code und Daten, rund 0,5 KiB.
Zusammen mit den 12 eingesparten Byte der [Plugin-Prüfung](2026-10-21-plugin-pruefung.md)
wächst der Code gegenüber dem bisherigen Stand um 504 Byte.

## Adressnachweis

Die Kalibrierung liest den Global-Objektzeiger an `0xC033E6A0`. Die Datenadresse ist bei
Sampler und Synth identisch. `tools/patch/fwmap.py` ordnet den zugehörigen Ladebefehl
`0xC0064728` des Samplers `0xC005ABC4` im Synth zu und bestätigt gleichen Code.
Die Literale an `0xC0064834` und `0xC005ACD0` enthalten beide den genannten Objektzeiger.
Die Zuordnung steht in `data/synth-map/display-calibrate.json`. Der Displaypuffer und
Bildschirmmanager verwenden die bereits vorhandenen Zuordnungen der Laufzeit.

## Prüfungen und Grenze

Sechs native Tests auf selbst erzeugtem RAM prüfen drei Geschwindigkeiten, alle 256
Phasen und den Zählerüberlauf, die 25 Kontrastwerte, Schreibgrenzen sowie Register und
Stack. Der geprüfte Aufruf braucht 2247 ARM-Befehle; die Prüfung begrenzt ihn auf weniger als 4000. Ungültige Zeiger, andere
Seiten und offene Fenster lassen das Display unverändert.

Die zusätzlichen Firmwarefälle in `tools/emu/calibrate_cases.py` prüfen den normalen
Bedienweg, die Animation, den unveränderten Global-Block beim Zeichnen, die ursprünglichen
Wertebereiche, WRITE, EXIT und den Notschalter. Sie gehören zum vollständigen Emulatorcheck.

Der vollständige Patch-Satz besteht am 21.10.2026 auf Synth 347 von 347, auf Hacktribe
443 von 443 und auf Korg rot 468 von 468 Prüfungen. Darin sind jeweils neun Fälle zur
Kalibrierung enthalten. Die genau geprüften Ein- und Ausgaben stehen als Prüfsummen in
`data/patches/verified.json`; Firmwaredateien werden nicht mitgeliefert.

**Am Gerät offen:** Welche Kontrasteinstellung die drei Bewegungen am lesbarsten zeigt.
Der Emulator kann das individuelle Nachleuchten eines echten LCDs nicht bestätigen.
[Anleitung für den Gerätetest](../geraetetests/blech-1.3.md).
