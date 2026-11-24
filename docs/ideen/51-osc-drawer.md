# Idee 51: OSC Drawer

Status: offen, nichts gebaut. Kandidat für ein [Plugin](../glossary.md#plugin). Zurück zu den [Ideen](../ideen.md).

Einen eigenen Oszillator mit dem Finger auf dem Touchpad malen (X ist die Phase eines Zyklus, Y die Auslenkung) und als User-Sample speichern (ab Slot 501). Der Loop-Punkt wird automatisch gesetzt (ein ganzer Zyklus). Vorhören über die Pads: links oben spielt die Grundnote C4, jedes andere Pad eine andere Note. Der Grundton eines Einzelzyklus ist C4.

Offen: wie die Firmware ein Sample in einen Slot schreibt (einen Resample- oder Aufnahme-Weg suchen). Im Emulator landet eine WAV-Datei von der virtuellen Karte über DATA UTILITY in Slot 501 ([Virtuelle SD-Karte](../hintergrund/virtuelle-sd.md)), aber die Plugin-Schnittstelle kann Samples nur lesen (`korg.read.sampleName`, `korg.read.sampleInfo`), nicht schreiben.

Ein Plugin dafür braucht Touchpad, Pads, Display und einen Aufruf zum Sample-Schreiben ([Plugins](../plugins.md)).
