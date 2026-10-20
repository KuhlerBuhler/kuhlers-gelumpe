# Idee 45: Blechy beim Ein- und Ausschalten

Stand: das Bild beim Ausschalten ist gebaut und im Emulator geprüft, am Gerät nichts; der Ton und der Ton beim Anschalten sind nicht gebaut. Baut auf Idee 35 und 40 auf. Zurück zu den [Ideen](../ideen.md).

Ein Ton beim Ausschalten (`blechy-sad`), optional auch beim Anschalten, beides per Menü abschaltbar. Dazu den Power-Off-Screen durch ein eigenes Blechy-Bild ersetzen.

Den Power-Off-Screen zeichnet die Firmware, wenn die Ein/Aus-Taste kommt (weißer Kasten, dann „Power Off“, [Bedienfeld](../messungen/2026-10-08-panel-bedienung.md)). Das Gerät bleibt die rund 2 s Haltezeit an, in dem Fenster wäre Platz für Ton und Bild. Der Bildersatz funktioniert wie beim Startbild (Idee 35) und ist ein Zeichen-Haken.

Offen: ob die Sound-Engine beim Aus- oder Anschalten noch oder schon läuft (für den Ton), und wo der Power-Off-Screen gezeichnet wird (für das Bild).

## Das Bild beim Ausschalten (gebaut)

Statt des Kastens "Power Off" zeigt die Firmware beim Ausschalten Blechy, der winkt (`assets/blechy/sprites/blechy-wave-1.png` und
`-2.png`), und drei Zeilen: "Haus'te" / "rin mein" / "Akh". Nach 700 ms blendet das Bild ab und geht wie eine alte Röhre aus
(Strich, Punkt, dunkel), alles in der einen Sekunde, die die Firmware ohnehin wartet. Der Patch `power-off` gehört zum
Satz BLECH, hängt sich in den Aufruf der Wartefunktion im Ausschalt-Handler (`0xC0038A74`) und lässt das Speichern der Firmware
unberührt. Der Ort des Power-Off-Screens, die Messungen, die Prüfungen und was am Gerät offen ist:
[Blechy beim Ausschalten](../messungen/2026-10-15-blechy-power-off.md). Ein Menüpunkt zum Abschalten des Bildes fehlt; EXIT beim
Einschalten hält wie bei jedem Patch alles heraus.

Gelöst ist damit die zweite offene Frage (wo der Power-Off-Screen gezeichnet wird). Offen bleibt die erste, ob die Sound-Engine
beim Aus- oder Anschalten noch oder schon läuft, und damit der Ton.
