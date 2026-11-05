"""Link input and UI frame hooks with the native VM into an isolated FF area."""
from dataclasses import dataclass
import sys
from pathlib import Path
import struct
import hashlib
import re
from .arm import assemble
from .ramdecl import area, share
from .script_vm import build as build_vm

BLECHY_BLOCK = 0xC0184000
BLECHY_BLOCK_END = 0xC0188000
BLECHY_FILE = Path(getattr(sys, '_MEIPASS', '') or Path(__file__).resolve().parents[2]) / 'data' / 'script' / 'blechy-block.hex'   # frozen: unpacked next to the code
CODE_START = 0xC01A6000         # the first code area, now a reserve: only the menu copies at its end (MENU_TABLE) are written; on
                                # the Sampler the loading animation (tools/patch/load_bar.py:ANIM_SLOT) uses it up to MENU_TABLE
CODE_AT = CODE_START
INPUT = 0xC01F8000
CARD = 0xC01F7000
CODE_END = 0xC01AE000
MORE_START = 0xC018D000          # the second code area, now a reserve; free (FF) in all three images, behind the idle insert effect
MORE_END = 0xC018FF00
MORE2_START = 0xC0188A00         # the third code area, now a reserve; free (FF) in all three images, in the unused end of the page
MORE2_END = 0xC0188F00           # of the tap motion patch (its code ends at 0xC018852C, its state sits at 0xC0188F00)
SETTINGS_RAM = MORE2_START       # its start since 1.3.8: the two buffers of the settings file (SETTINGS_MAX each, 0x120) and the
SETTINGS_RAM_END = SETTINGS_RAM + 2 * 0x120 + 64 * 4   # checksum list of the BLECH menu (MENU_MAX_TRUST words); behind it
LIST_WORK = SETTINGS_RAM_END     # the work area of the list of MANAGE PLUGINS since 1.3.8: folder object, file info, long name, path,
LIST_WORK_END = LIST_WORK + 0x150   # the place of each listed file and the flag of a longer folder (script_menu.s:LIST_WORK_SIZE)
KNOB_HOLD = LIST_WORK_END        # korg.knobHold (script_hw.s:KH_FREE): the free knobs, the plugin that holds and its checksum; FF at power-on
KNOB_HOLD_END = KNOB_HOLD + 12   # is all knobs free and no owner
KEY_PASS = KNOB_HOLD_END         # korg.passKeys (script_hw.s:KP_PASS): the keys that reach the firmware while an app is open and
KEY_PASS_END = KEY_PASS + 16     # the keys whose press did; FF at power-on is the defaults
TOUCH_LOCK = KEY_PASS_END        # korg.touchLockX (script_hw.s:TL_RAW): the X written into touch messages, the plugin that locks and its
TOUCH_LOCK_END = TOUCH_LOCK + 12 # checksum; FF at power-on is no lock
KEY_HOLD = TOUCH_LOCK_END        # korg.keyHold (script_hw.s:KY_FREE): the free keys, the keys whose press was kept, the plugin that holds
KEY_HOLD_END = KEY_HOLD + 24     # and its checksum; FF at power-on is all keys free
PRESS_KEY = KEY_HOLD_END         # korg.pressKey (script_hw.s:PK_UP): the keys whose release goes out in the next frame, inverted, so
PRESS_KEY_END = PRESS_KEY + 8    # FF at power-on is none. The rest a reserve
MORE3_START = 0xC0150300         # the code area of the runtime: the VM and all our code; 0xC015027C to 0xC0170000 is FF in all three images,
MORE3_END = 0xC0170000           # no patch touches it and the emulator never writes it (measured 2026-10-28)
RUNTIME = 0xC01AE000
POOL = 0xC01D7000
END = 0xC01FFFF0
RAM_BASE = 0xC0000000
LITERALS = ((0xC0083710,0xC031BB2C),)
MENU_ITEMS = 0xC01D6C00
MENU_ITEMS_END = MENU_ITEMS + 12 * 40
MENU_STATE = 0xC01D6E00
MENU_TABLE = 0xC01ADF00         # the copies sit at the end of the code area: the table (Sampler 180 + 4, synth 148 + 4 bytes), then
MENU_VTABLE = 0xC01ADFB8        # the class table (72 bytes) up to RUNTIME; they were at 0xC01ADE00 and 0xC01ADF00, the code needed the room
MENU_TABLE_SOURCE = (0xC00F9CD8, 180, 'e1e06a3d074b86a6f2a1e9421671a802a6532c0e6448a4fd2d38925cf755a538')
MENU_VTABLE_SOURCE = (0xC00E3440, 72, '40898334ac0dd1700b7ae70e32534163b25bb80dd3737ad0a2062c10b4934823')
SITES = ((0xC002837C,0xE5D03018,'script_input_hook'),
         (0xC00836FC,0xE59F000C,'script_frame_hook'),
         (0xC0038D68,0xE28D0004,'script_card_hook'),
         (0xC004C1B4,0xE92D4070,'script_save_hook'),
         (0xC006E8D8,0xE351000A,'menu_toplevel'),
         (0xC006F094,0xE92D4038,'menu_write'),
         (0xC008A83C,0xE3A03000,'menu_counter_new'),
         (0xC008A8A8,0xE92D4010,'menu_counter_set'),
         (0xC0016C98,0xE92D4800,'bl_set_red'),
         (0xC0016CE0,0xE92D4800,'bl_set_green'),
         (0xC0016D28,0xE92D4800,'bl_set_blue'),
         (0xC00289F4,0xE92D4070,'bl_pwm_hook'),
         (0xC0088284,0xE5D03B98,'led_meter_hook'),
         (0xC00161A4,0xE51B3010,'lcd_invert_hook'),
         (0xC0064430,0xE92D4038,'menu_event_right'),
         (0xC0067754,0xE3A0000A,'menu_pattern_left'),
         (0xC0067720,0xE3A00007,'menu_pattern_right'),
         (0xC0065B8C,0xE3A00003,'menu_part_left'),
         (0xC0064C20,0xE3E01000,'menu_global_prev'),
         (0xC0064C28,0xE3A01001,'menu_global_next'),
         (0xC00623C0,0xE92D4010,'menu_du_prev'),
         (0xC0062448,0xE92D4010,'menu_du_next'),
         (0xC0038D34,0xE3A03000,'script_early_hook'),
         (0xC00289D8,0xE3500F49,'boot_light_hook'))
# Words that change to a plain value instead of a branch: the screen factory's bound and its table literal.
WORDS = ((0xC006E664,0xE350002C,0xE350002D),
         (0xC006E68C,0xC00F9CD8,MENU_TABLE))
# Vtable slots of the menu class that point into our code (offset in the table, symbol).
VTABLE_OVER = ((8,'menu_slot_exit'),(12,'menu_slot_keys'),(16,'menu_slot_prev'),(20,'menu_slot_next'),(24,'menu_slot_enter'),(40,'menu_slot_value'))

# korg.seq.setPatternValue (script_seq.s:pattern_setters): per build and PATTERN_FIELDS name (data/script/contract.mjs) the firmware
# function that sets the value as the device's own edit does, and the offset from the pattern object it gets in r0; r1 gets the
# byte (the value clamped to PATTERN_WRITES, from the units of korg.read.patternValue), r2 1. A third number is a lower top for
# the byte on this build: the synth's MFX TYPE page goes to 31, the Sampler's to 39. A field without an entry writes nothing. Measured in the emulator, the menu page or key that changes the field calls the function
# (docs/messungen/2026-11-03-live-schreibwege.md); red has the Sampler's addresses, the synth its own.
PATTERN_SETTER_FIELDS = ('tempo','swing','length','beat','key','scale','chordSet','level','mfxType','chainTo','chainRepeat','gateArp')
_SAMPLER_SETTERS = {'tempo': (0xC004A80C, 0), 'swing': (0xC004A594, 0), 'length': (0xC004A560, 0), 'beat': (0xC004A4F8, 0),
                    'key': (0xC004A6FC, 0), 'scale': (0xC004A77C, 0), 'chordSet': (0xC004A534, 0), 'level': (0xC004A698, 0),
                    'mfxType': (0xC0048A64, 0x4004), 'chainTo': (0xC004A5B0, 0), 'chainRepeat': (0xC004A5D4, 0),
                    'gateArp': (0xC004A5F8, 0)}
PATTERN_SETTERS = {
    'hacktribe': _SAMPLER_SETTERS,
    'stock': _SAMPLER_SETTERS,
    'synth': {'tempo': (0xC00448EC, 0), 'swing': (0xC0044674, 0), 'length': (0xC0044640, 0), 'beat': (0xC00445F8, 0),
              'key': (0xC00447DC, 0), 'scale': (0xC004485C, 0), 'chordSet': (0xC0044614, 0), 'level': (0xC0044778, 0),
              'mfxType': (0xC0042CBC, 0x4004, 31), 'chainTo': (0xC0044690, 0), 'chainRepeat': (0xC00446B4, 0),
              'gateArp': (0xC00446D8, 0)},
}


def pattern_setter_actions(build):
    """The .equ values of the setter table: PV_SET_i the function, PV_ARG_i the offset of its r0 from the pattern object, PV_TOP_i
    the byte's top on this build (0 for the field's own); 0, 0 and 0 for a field without a setter."""
    setters = PATTERN_SETTERS[build]
    unknown = set(setters) - set(PATTERN_SETTER_FIELDS)
    if unknown:
        raise ValueError(f'pattern setters for unknown fields: {sorted(unknown)}')
    out = {}
    for i, name in enumerate(PATTERN_SETTER_FIELDS):
        address, arg, top = (*setters.get(name, (0, 0)), 0)[:3]
        out[f'PV_SET_{i}'], out[f'PV_ARG_{i}'], out[f'PV_TOP_{i}'] = address, arg, top
    return out


@dataclass(frozen=True)
class RuntimeProfile:
    build: str
    sites: tuple
    words: tuple
    literals: tuple
    table: tuple
    vtable: tuple
    screen: int
    ring_first: int
    ring_total: int
    actions: dict

    def hooks(self, hooks):
        addresses = {name: address for address, _, name in self.sites}
        places = {address: addresses[name] for address, _, name in SITES if name in addresses}
        places.update({old[0]: new[0] for old, new in zip(WORDS, self.words)})
        return [{**hook, 'site': f'0x{places[int(hook["site"],16)]:08X}'}
                for hook in hooks if int(hook['site'],16) in places]


def runtime_profile(build):
    if build not in ('hacktribe', 'stock', 'synth'):
        raise ValueError(f'unknown runtime build: {build}')
    if build != 'synth':
        return RuntimeProfile(build, SITES, WORDS, LITERALS, MENU_TABLE_SOURCE, MENU_VTABLE_SOURCE,
                              45, 29, 29, dict(HW_PANEL_KEY=0xC0042BB8, HW_KNOB=0xC0040A50, HW_PART_SELECT=0xC0081BB4,
                                              # korg.seq.setPartValue: the part edit the knobs call, its object, the observers of the parameter window
                                              HW_PART_EDIT=0xC0048460, HW_PART_EDITOR=0xC034886C, HW_PARAM_WINDOW=0xC03487EC,
                                              HW_MUTE_OBJECT=0xC06CA798 if build == 'stock' else 0xC06CA760,
                                              POWER_HOLD_MASK=0x08000000, SHORTCUTS=1, REMOTE=1, HW_ENCODER=0xC00419B4,
                                              SC_LEDMGR=0xC0345A1C, SC_PLAYER=0xC002FAFC, SC_PATPTR=0xC033E6A4,
                                              SC_BANK=0xC08B2940, SC_LOAD=0xC004AB84, SC_LEDSEND=0xC00875F4,
                                              MG_WORK=0xC0190100, MG_MKDIR=0xC009EB00, FS_UNLINK=0xC009E9B8, MG_GETFREE=0xC009E85C, MG_ALLOC=0xC0028DCC, MG_FREE=0xC0028DD4,
                                              MG_VRAM=0xC031B310, MG_MARK=0xC001531C, MG_BLUE=0, MG_LCD=0, MG_FLUSH=0, SYNC_GROUP_AT=0x3B80,
                                              # the collection on the card (fx_card.s): which build it is for, and the modulation table this build reads
                                              FX_BUILD=2 if build == 'stock' else 1, FX_MODS=0xC00D81EC if build == 'stock' else 0xC019FFFC,
                                              BUILD_BASE=4 if build == 'stock' else 0,
                                              # DATA UTILITY's list: its functions (counter "n/14"), and the bits of our pages there the build has (script_menu.s, menu_du_mask)
                                              DU_PAGES=14, DU_BUILT=7, **pattern_setter_actions(build)))   # the value of BLECH > VERSION, an offset into base_names
    from . import synthaddr
    sites = []
    for address, expected, name in SITES:
        if name == 'script_early_hook':
            continue
        if name == 'boot_light_hook':
            address, expected = 0xC0025E48, 0xE1500003
        elif name == 'script_card_hook':
            address, expected = 0xC0028170, 0xE5D43004
        elif name == 'menu_toplevel':
            address, expected = 0xC0061DDC, 0xE594301C
        else:
            address = synthaddr.tr(address)
        sites.append((address, expected, name))
    return RuntimeProfile(build, tuple(sites),
        ((0xC0061B68,0xE3500024,0xE3500025), (0xC0061B90,0xC00DFA68,MENU_TABLE)),
        tuple((synthaddr.tr(address), synthaddr.tr(value)) for address, value in LITERALS),
        (0xC00DFA68,148,'a65f40522347f45bab9a10802914b4a69900ab66e455c279c57c8aa4f48368fd'),
        (0xC00C9BD8,72,'9890f118100188fed55d3f35b6cc98c22191484ac62c8e1b55fb0794c0089277'),
        37, 28, 28, dict(HW_PANEL_KEY=0xC003D158, HW_KNOB=0xC003B688, HW_PART_SELECT=0xC0072338, HW_MUTE_OBJECT=0xC0596DF8,
        HW_PART_EDIT=0, HW_PART_EDITOR=0, HW_PARAM_WINDOW=0,   # the part edit is not measured on the synth: setPartValue writes nothing
        POWER_HOLD_MASK=0, SHORTCUTS=1, REMOTE=1, HW_ENCODER=0,
        SC_LEDMGR=synthaddr.tr(0xC0345A1C), SC_PLAYER=synthaddr.tr(0xC002FAFC), SC_PATPTR=synthaddr.tr(0xC033E6A4),
        SC_BANK=synthaddr.tr(0xC08B2940), SC_LOAD=synthaddr.tr(0xC004AB84), SC_LEDSEND=synthaddr.tr(0xC00875F4),
        # the folder copy of the first start: f_mkdir, f_getfree, new, delete and the mark of a changed region are the Sampler's
        # functions, 16 masked words equal (fwmap); the frame buffer has the same address; MG_FLUSH (MG_LCD, 2 or 3, 0) sends the
        # frame buffer, as Korg's PCM loader does for its bar (docs/messungen/2026-10-29-blau-ordner-uebernehmen.md)
        MG_WORK=0xC0190100, MG_MKDIR=0xC008B510, FS_UNLINK=0, MG_GETFREE=0xC008B3B4, MG_ALLOC=0xC0026240, MG_FREE=0xC0026248,
        MG_VRAM=0xC031B310, MG_MARK=0xC0010BD8, MG_BLUE=1, MG_LCD=0xC031BB2C, MG_FLUSH=0xC001168C, SYNC_GROUP_AT=0x3B80, BUILD_BASE=8, DU_PAGES=11, DU_BUILT=3, **pattern_setter_actions(build)))   # power hold is not measured on the synth; the EXIT shortcuts are (docs/messungen/2026-10-24-blau-shortcuts-akkorde.md)


def blechy_block():
    """The compiled block of Blechy, the app built into BLECH (data/script/blechy-block.hex, made by tools/blechy-build.mjs)."""
    return bytes.fromhex(''.join(BLECHY_FILE.read_text().split()))

@dataclass
class BuiltHooks:
    vm: object
    sections: list
    symbols: dict
    layout: dict
    profile: RuntimeProfile

    def manifest(self):
        return dict(layout=self.layout.copy(),hooks=[dict(address=address,
            expected=expected,target=self.symbols[name],name=name) for address,expected,name in self.profile.sites],
            literals=[dict(address=address,expected=word) for address,word in self.profile.literals],
            regions=[dict(address=address,size=len(data)) for address,data in self.sections])

    def patch_manifest(self):
        changes=[dict(file=address-RAM_BASE+0x100,bytes=data.hex(),
            expect=hashlib.sha256(b'\xff'*len(data)).hexdigest()) for address,data in self.sections]
        for address,word,name in self.profile.sites:
            data=assemble(f'b {self.symbols[name]}',origin=address).bytes
            changes.append(dict(file=address-RAM_BASE+0x100,bytes=data.hex(),
                expect=hashlib.sha256(struct.pack('<I',word)).hexdigest()))
        for address,old,new in self.profile.words:
            changes.append(dict(file=address-RAM_BASE+0x100,bytes=struct.pack('<I',new).hex(),
                expect=hashlib.sha256(struct.pack('<I',old)).hexdigest()))
        changes.extend(self.menu_copy_changes())
        spans=[(address,address+4,'Eingangs-, Rahmen-, Karten- oder Menüstelle verzweigt in den gesicherten Rückweg.')
               for address,_,_ in self.profile.sites]
        spans+=[(address,address+4,'Grenze und Tabellenverweis der Bildschirmfabrik, jeder Bildschirmwechsel liest sie.')
                for address,_,_ in self.profile.words]
        spans.append((MENU_TABLE,MENU_TABLE+self.profile.table[1]+4,'Kopie der Bildschirmtabelle mit einem Eintrag mehr, die Fabrik liest sie schon für den Hauptbildschirm.'))
        block=self.sections[-1]
        spans.append((block[0],block[0]+len(block[1]),'Der Block von Blechy, der eingebauten App, liegt im Abbild: der Lader prüft ihn (Prüfsumme, Befehle) und liest seine Konstanten, sobald das Menü scharf ist.'))
        vm=self.sections[0]
        spans.append((vm[0],vm[0]+len(vm[1]),'Die VM (Laden, Prüfen, Befehle und ihre Tabellen) läuft beim Start: Blechy wird mit ihr geladen, geprüft und gestartet, und ein Plugin von der Karte läuft mit ihr genauso.'))
        for start,end,why in [
            ('script_input_hook','script_input_pass_end','Der Eingangsfilter erhält Register, prüft den Laufzeitschalter, sortiert (mit Blechy ist die Laufzeit schon beim Start scharf) die Panel-Nachrichten, legt Ereignisse in den Ring, führt den verdrängten Befehl aus und kehrt ins Original zurück.'),
            ('script_input_literals','script_input_literals_end','Eigene Literale für Laufzeitschalter und ursprünglichen Eingaberückweg.'),
            ('script_frame_hook','script_frame_wrapper_end','Rahmenhaken erhält Register und Flags und lädt den ursprünglichen Managerzeiger.'),
            ('script_ring_post','script_frame_hook','Der Ereignisring: Eingaben und Ereignisse einreihen und abholen.'),
            ('script_frame_run','frame_gate_open','Der Rahmenhaken prüft den Laufzeitschalter, die Zähler und das erste Hauptbild vor allen Plugin-Zugriffen; mit Blechy ist er schon beim Start scharf.'),
            ('script_clock_update','script_play_glue','Uhr und lesende Aufrufe (millis, Sequencerzustand): Blechys Rumpf und jeder Rahmen benutzen sie.'),
            ('script_app_glue','script_display_take_glue','korg.app: Blechys Rumpf meldet sich an, der Eintrag steht schon da.'),
            ('frame_return','script_frame_return_end','Rahmenrückweg samt eigenen Literalen im beobachteten Startblock.'),
            ('script_save_hook','script_save_hook_end','Speicher-Haken erhält Register, meldet das Ereignis und führt den verdrängten Befehl aus.'),
            ('script_early_hook','script_early_end','Der Haken vor dem Sample-Lader (erster Befehl des Ladebefehls) erhält Register und Flags, schaltet das Menü scharf und liest die Einstellungen, damit das Aussehen schon beim Laden gilt, und führt den verdrängten Befehl aus.'),
            ('boot_light_hook','boot_light_end','Die Farbe des Hintergrundlichts beim Einschalten: hinter dem ersten Lesen des Flash prüft der Haken Panel, EXIT und Panel-Update, liest 12 Byte der Globals im Flash (Marke GLED) und setzt nur die drei Pins des Lichts; die Haken der Lichtfunktionen lassen sie bis zum Scharfschalten so.'),
            ('script_card_hook','script_card_wrapper_end','Start-Wrapper erhält Register und Flags, prüft den Notschalter vor Menü und Plugins und führt den verdrängten nativen Befehl aus.'),
            ('script_card_load','script_card_load_end','Kartenlader prüft Panel und EXIT, öffnet die Plugin-Datei und kehrt ohne Karte oder Datei zurück.'),
            ('fx_card_load','fx_card_load_end','Der Lader der Sammeldatei e2sFx.all prüft Panel und EXIT, liest die Datei erst ganz zur Prüfung und schreibt nur dann Presets und Modulationen ins RAM; ohne Karte, Datei oder bei einem Fehler kehrt er zurück, ohne etwas zu schreiben.'),
            ('menu_arm','menu_arm_end','Das Menü prüft Panel, EXIT und Panel-Update, bevor es seinen Zustand initialisiert und sich scharf schaltet.'),
            ('menu_arm_load','menu_arm_load_end','Schaltet das Menü scharf und liest die Einstellungen genau einmal.'),
            ('menu_settings_load','menu_settings_end','Die Einstellungsdatei wird vor den Plugins gelesen; fehlt sie oder ist sie beschädigt, gelten die Voreinstellungen.'),
            ('objects_row','objects_end','Nach den Einstellungen prüft der Objektbaum jeden gespeicherten Wert gegen seinen Bereich und klemmt oder setzt ihn zurück (Tabelle, Zähler).'),
            ('blechy_boot','blechy_boot_end','Blechy, die eingebaute App, wird vor dem Kartenlader geladen, startet und schaltet die Laufzeit scharf, auch ohne Karte; mit EXIT beim Einschalten ist das Menü unscharf und die Funktion kehrt sofort zurück.'),
            ('menu_needs_confirm','menu_confirm','Der Kartenlader fragt für jedes geladene Plugin, ob es erst auf eine Zustimmung wartet; ohne Plugins läuft das nicht.'),
            ('menu_recount','menu_recount_end','Nach dem Laden zählt das Menü die Plugins und stellt die Seitenzahl ein.'),
            ('led_meter_hook','look_hooks_end','Die Haken der Anpassung (untere LEDs, Hintergrundlicht, Software-PWM, Display umkehren) geben die Firmware sofort zurück, wenn das Menü nicht scharf ist oder die Firmware das Licht für Power Save dimmt.'),
            ('shortcut_input','shortcut_tick','Die EXIT-Shortcuts im Eingangsfilter: prüfen Panel und EXIT beim Einschalten, merken sich EXIT und lassen jede Meldung durch, solange EXIT nicht auf dem Hauptbildschirm gehalten wird.'),
            ('shortcut_pool','shortcut_end','Literale der EXIT-Shortcuts.'),
            ('migrate_start','migrate_end','Die Übernahme des alten Kartenordners: vor dem Sample-Lader prüft sie Panel, EXIT und die Ordner der Karte; nur wenn es keinen blechtribe-Ordner, aber einen hacktribe- oder electribe-sampler-Ordner gibt (auf der blauen: keinen blechtribe-Ordner, aber einen electribe-Ordner), fragt sie auf dem Display (Eingangsfilter und Rahmenhaken lesen ihren Schalter) und kopiert auf MENU.'),
            ('remap_input','events_post','Die Tastenumleitung (korg.input.remap) im Eingangsfilter: jede Panel-Meldung geht an ihr vorbei; sie liest ihren Zustand im Arbeitsbereich der Karte und die Liste der Plugins und ändert höchstens den Tastencode einer Tastenmeldung, wenn ein laufendes Plugin eine Umleitung gesetzt hat.'),
            ('menu_event_right','menu_hooks_end','Rücksprünge der Menüstellen: Nachbarn im Ring, Spitzenebene, WRITE und Seitenzähler laufen schon vor dem Hauptbildschirm vorbei und lassen die Firmware ohne scharfes Menü unverändert.'),
        ]:
            if start in self.symbols and end in self.symbols:
                spans.append((self.symbols[start],self.symbols[end],why))
        menu_hooks=[dict(site=f'{address:#010X}'.replace('0X','0x'),kind='instruction',chain=chain,position='before',swallow=swallow)
            for address,chain,swallow in [
            (0xC006E8D8,'menu-top-level',False),(0xC006F094,'menu-write',True),(0xC008A83C,'menu-counter',False),(0xC008A8A8,'menu-counter',False),
            (0xC0064430,'menu-ring',False),(0xC0067754,'menu-ring',False),(0xC0067720,'menu-ring',False),(0xC0065B8C,'menu-ring',False),
            (0xC0064C20,'global-screen',False),(0xC0064C28,'global-screen',False),(0xC00623C0,'data-util-screen',False),(0xC0062448,'data-util-screen',False)]]
        menu_hooks+=[dict(site='0xC0088284',kind='instruction',chain='led-meter',position='before',swallow=True)]
        menu_hooks+=[dict(site=f'0x{address:08X}',kind='instruction',chain='backlight',position='before',swallow=False)
            for address in (0xC0016C98,0xC0016CE0,0xC0016D28,0xC00289F4)]
        menu_hooks+=[dict(site='0xC00161A4',kind='instruction',chain='lcd-invert',position='before',swallow=False)]
        menu_hooks+=[dict(site='0xC006E664',kind='instruction',chain='menu-ring',position='replace',swallow=False),
            dict(site='0xC006E68C',kind='literal',chain='menu-ring',position='replace',swallow=False)]
        menu_hooks+=[dict(site='0xC0038D34',kind='instruction',chain='start',position='before',swallow=False)]
        menu_hooks+=[dict(site='0xC00289D8',kind='instruction',chain='start',position='before',swallow=False)]
        return dict(format='gelumpe-patch',version=1,id='script-runtime',
            name='Plugin-Laufzeit mit Eingangsfilter und Rahmenhaken',builds=[self.profile.build],changes=changes,
            startPhase=[dict(file=start-RAM_BASE+0x100,length=end-start,why=why) for start,end,why in spans],
            ram=self.ram_areas(),shares=[share(self.symbols['PS_SETTING'],4,'pattern-switch',
                'the pattern switch setting word the BLECH menu writes, in the state of the pattern switch','tools/patch/script_menu.s:PS_SETTING'),
                share(self.symbols['TM_SETTING'],4,'tap-motion',
                'the TAP motion setting word the BLECH menu writes, in the state of the TAP motion patch','tools/patch/script_menu.s:TM_SETTING'),
                share(self.symbols['NA_SETTING'],4,'note-assistant',
                'the note assistant setting word the BLECH menu writes, in the state of the note assistant','tools/patch/script_menu.s:NA_SETTING')],
            hooks=self.profile.hooks([dict(site='0xC002837C',kind='instruction',chain=['key-dispatch','pattern-set'],
                position='before',swallow=True),dict(site='0xC00836FC',kind='instruction',
                chain='frame',position='after',swallow=False),dict(site='0xC0038D68',kind='instruction',
                chain='start',position='before',swallow=False),dict(site='0xC004C1B4',kind='instruction',
                chain='save',position='before',swallow=False)]+menu_hooks))

    def ram_areas(self):
        layout=self.layout
        return [area(layout['runtime'],layout['runtimeSize'],'runtime: control block, stacks, ring, LED, display buffer, knobs, app table (RT_* layout)','tools/patch/script_hooks.py:RUNTIME'),
            area(MENU_ITEMS,MENU_ITEMS_END-MENU_ITEMS,'pages of the plugins in the BLECH menu, 12 entries of 40 bytes','tools/patch/script_hooks.py:MENU_ITEMS'),
            area(MENU_ITEMS_END,MENU_STATE-MENU_ITEMS_END,'more state of the BLECH menu: intensity, save light, meter and overlap colours, the power save tables of the backlight; the last bytes are the EXIT shortcuts (EXIT held, save and reset asked for)','tools/patch/script_menu.s:MX_INTENS'),
            area(MENU_STATE,0x200,'state of the BLECH menu','tools/patch/script_hooks.py:MENU_STATE'),
            area(layout['pool'],layout['poolEnd']-layout['pool'],'plugin pool, SCRIPT_POOL_BYTES','tools/patch/script_hooks.py:POOL'),
            area(layout['card'],layout['input']-layout['card'],'work area of the card loader: file object, state, plugin list of the import page, the key commands of KORG.press, the record of korg.remapKey and the word korg.seq marks a written frame with','tools/patch/script_hooks.py:CARD'),
            area(layout['input'],END-layout['input'],'block buffer for file reads, the two store images lie in it','tools/patch/script_hooks.py:INPUT'),
            area(layout['codeEnd'],MORE3_END-layout['codeEnd'],'the rest of the code area, kept free for the code of the plugin API to grow into','tools/patch/script_hooks.py:MORE3_END'),
            *([area(CODE_START,MENU_TABLE-CODE_START,'the first code area of the runtime, empty since its code moved to MORE3_START, kept free as a reserve','tools/patch/script_hooks.py:CODE_START')]
              if self.profile.build == 'synth' else []),
            area(MORE_START,MORE_END-MORE_START,'the second code area of the runtime, empty since its code moved to MORE3_START, kept free as a reserve','tools/patch/script_hooks.py:MORE_START'),
            area(SETTINGS_RAM,SETTINGS_RAM_END-SETTINGS_RAM,'the two buffers of the settings file of the BLECH menu and its checksum list (allowed plugins, plugins switched off)','tools/patch/script_hooks.py:SETTINGS_RAM'),
            area(LIST_WORK,LIST_WORK_END-LIST_WORK,'work area of the list of MANAGE PLUGINS: folder object, file info, long name, path, the place of each listed file in the folder, the flag of more files than the list holds','tools/patch/script_menu.s:LIST_WORK'),
            area(KNOB_HOLD,KNOB_HOLD_END-KNOB_HOLD,'korg.knobHold: a bit per knob that reaches the firmware, the plugin that holds a knob and the checksum of its block','tools/patch/script_hw.s:KH_FREE'),
            area(KEY_PASS,KEY_PASS_END-KEY_PASS,'korg.passKeys: a bit per key that reaches the firmware while an app is open, and a bit per key whose press did','tools/patch/script_hw.s:KP_PASS'),
            area(TOUCH_LOCK,TOUCH_LOCK_END-TOUCH_LOCK,'korg.touchLockX: the X the input filter writes into touch messages, the plugin that locks it and the checksum of its block','tools/patch/script_hw.s:TL_RAW'),
            area(KEY_HOLD,KEY_HOLD_END-KEY_HOLD,'korg.keyHold: a bit per key that reaches the firmware, a bit per key whose press was kept, the plugin that holds and the checksum of its block','tools/patch/script_hw.s:KY_FREE'),
            area(PRESS_KEY,PRESS_KEY_END-PRESS_KEY,'korg.pressKey: a bit per key whose release goes to the firmware in the next frame','tools/patch/script_hw.s:PK_UP'),
            area(PRESS_KEY_END,MORE2_END-PRESS_KEY_END,'the rest of the third code area of the runtime, empty since its code moved to MORE3_START, kept free as a reserve','tools/patch/script_hooks.py:PRESS_KEY_END')]+(
            [area(self.profile.actions['MG_WORK'],0xF00,'work area of the folder copy at the first start: state, file and folder objects, paths','tools/patch/script_migrate.s:MG_ACTIVE')]
            if self.profile.actions.get('MG_WORK') else [])

    def menu_copy_changes(self):
        table_at,table_len,table_hash=self.profile.table
        vt_at,vt_len,vt_hash=self.profile.vtable
        ff=lambda n: hashlib.sha256(b'\xff'*n).hexdigest()
        over=[dict(at=at,bytes=struct.pack('<I',self.symbols[name]).hex()) for at,name in VTABLE_OVER]
        return [dict(file=MENU_TABLE-RAM_BASE+0x100,copy=dict(file=table_at-RAM_BASE+0x100,length=table_len,expect=table_hash),expect=ff(table_len)),
            dict(file=MENU_TABLE+table_len-RAM_BASE+0x100,bytes=struct.pack('<I',self.symbols['menu_factory']).hex(),expect=ff(4)),
            dict(file=MENU_VTABLE-RAM_BASE+0x100,copy=dict(file=vt_at-RAM_BASE+0x100,length=vt_len,expect=vt_hash),over=over,expect=ff(vt_len))]

    def apply(self, image):
        output = bytearray(image)
        for address,expected in [(address,word) for address,word,_ in self.profile.sites]+[(address,old) for address,old,_ in self.profile.words]+list(self.profile.literals):
            offset=address-RAM_BASE+0x100
            if offset+4>len(output) or struct.unpack_from('<I',output,offset)[0]!=expected:
                raise ValueError(f'original hook instruction differs at {address:#x}')
        for start,end in [(MENU_TABLE,CODE_END),(MORE_START,MORE_END),(MORE2_START,MORE2_END),(MORE3_START,self.layout['codeEnd']),(RUNTIME,self.layout['runtimeEnd']),(self.layout['runtimeEnd'],POOL),(POOL,self.layout['poolEnd']),(CARD,END),(BLECHY_BLOCK,BLECHY_BLOCK+len(self.sections[-1][1]))]:
            offset=start-RAM_BASE+0x100
            if offset<0 or offset+end-start>len(output) or any(value!=255 for value in output[offset:offset+end-start]):
                raise ValueError(f'script area is not FF at {start:#x}')
        for address,data in self.sections:
            offset=address-RAM_BASE+0x100
            output[offset:offset+len(data)]=data
        for address,_,name in self.profile.sites:
            instruction=assemble(f'b {self.symbols[name]}',origin=address).bytes
            offset=address-RAM_BASE+0x100
            output[offset:offset+4]=instruction
        for address,_,new in self.profile.words:
            offset=address-RAM_BASE+0x100
            output[offset:offset+4]=struct.pack('<I',new)
        table_at,table_len,_=self.profile.table
        vt_at,vt_len,_=self.profile.vtable
        offset=MENU_TABLE-RAM_BASE+0x100
        output[offset:offset+table_len]=image[table_at-RAM_BASE+0x100:table_at-RAM_BASE+0x100+table_len]
        output[offset+table_len:offset+table_len+4]=struct.pack('<I',self.symbols['menu_factory'])
        vtable=bytearray(image[vt_at-RAM_BASE+0x100:vt_at-RAM_BASE+0x100+vt_len])
        for at,name in VTABLE_OVER:
            vtable[at:at+4]=struct.pack('<I',self.symbols[name])
        offset=MENU_VTABLE-RAM_BASE+0x100
        output[offset:offset+vt_len]=vtable
        return bytes(output)

# The Global menu's setters, by the byte of the Global block they write: (Sampler = Hacktribe and red, synth). The object tree
# (script_objects.s) calls the one of a leaf with apply "setter" as (the Global object, the value, 1), as the menu does. Measured
# in docs/messungen/2026-11-03-live-schreibwege.md and listed per field in data/map/global.mjs (`live.setter`); a test holds the two equal.
GLOBAL_SETTERS = {
    16: (0xC00471B0, 0xC004147C), 17: (0xC00471C0, 0xC004148C), 18: (0xC00471F8, 0xC00414C4), 19: (0xC00475BC, 0xC0041888),
    20: (0xC0047230, 0xC00414FC), 27: (0xC00472D8, 0xC00415A4), 28: (0xC00472E8, 0xC00415B4), 29: (0xC0047380, 0xC004164C),
    30: (0xC0047584, 0xC0041850), 31: (0xC00475CC, 0xC0041898), 32: (0xC00472F8, 0xC00415C4), 33: (0xC0047308, 0xC00415D4),
    36: (0xC0047788, 0xC0041A54), 37: (0xC0047348, 0xC0041614), 38: (0xC004754C, 0xC0041818), 40: (0xC00473D4, 0xC00416A0),
    41: (0xC0047454, 0xC0041720), 42: (0xC004748C, 0xC0041758), 43: (0xC00474E0, 0xC00417AC),
}
OBJECT_BASE_GLOBAL = 2

def object_rows(constants, build='hacktribe'):
    """The rows of the object table in script_objects.s, from the OBJ_ constants the include carries (data/script/objects.mjs).
    A leaf on the Global settings gets the setter of its byte on this build, 0 when it has none."""
    count=int(re.search(r'^\.equ OBJ_COUNT, (\S+)',constants,re.M).group(1),0)
    value=lambda i,name: int(re.search(rf'^\.equ OBJ_{i}_{name}, (\S+)',constants,re.M).group(1),0)
    def setter(i):
        if value(i,'BASE')!=OBJECT_BASE_GLOBAL or value(i,'APPLY')!=3: return 0
        pair=GLOBAL_SETTERS.get(value(i,'OFFSET'))
        return pair[1 if build=='synth' else 0] if pair else 0
    row=lambda i: f'    .word OBJ_{i}_OFFSET, OBJ_{i}_MIN, OBJ_{i}_MAX, OBJ_{i}_FACTORY, {setter(i):#x}\n    .byte OBJ_{i}_BASE, OBJ_{i}_TYPE, OBJ_{i}_APPLY, OBJ_{i}_FLAGS'
    return '\n'.join(row(i) for i in range(count))

def build(include, glue=None, blechy=None, build='hacktribe'):
    profile = runtime_profile(build)
    block=blechy_block() if blechy is None else blechy
    if len(block)%4 or BLECHY_BLOCK+len(block)>BLECHY_BLOCK_END:
        raise ValueError('the block of Blechy does not fit its place in the image')
    vm=build_vm(include,origin=MORE3_START,glue=glue)
    origin=(MORE3_START+len(vm.bytes)+31)&~31
    constants=include.split('.align 4',1)[0]
    constants += '\n'+ '\n'.join(f'.equ {key}, {value}' for key,value in vm.symbols.items() if key.startswith('RT_'))
    constants += '\n'+ '\n'.join(f'.equ VM_{name.upper()}, {vm.symbols[name]}' for name in ['script_run_event','script_runtime_init','script_load_block','script_load_block_ex'])
    constants += f'\n.equ VM_CRC_UPDATE, {vm.symbols["crc_update"]}'
    constants += ''.join(f'\n.equ {name.upper()}, {vm.symbols[name]}' for name in ['script_font','script_error_names'])
    constants += f'\n.equ MENU_ITEMS, {MENU_ITEMS}\n.equ MENU_STATE, {MENU_STATE}\n.equ MENU_FILE_A, {SETTINGS_RAM}\n.equ MENU_FILE_B, {SETTINGS_RAM+0x120}\n.equ MENU_TRUST, {SETTINGS_RAM+0x240}\n.equ LIST_WORK, {LIST_WORK}\n.equ KNOB_HOLD, {KNOB_HOLD}\n.equ KEY_PASS, {KEY_PASS}\n.equ TOUCH_LOCK, {TOUCH_LOCK}\n.equ KEY_HOLD, {KEY_HOLD}\n.equ PRESS_KEY, {PRESS_KEY}\n.equ MENU_TABLE, {MENU_TABLE}\n.equ MENU_VTABLE, {MENU_VTABLE}\n.equ HOOK_RUNTIME, {RUNTIME}\n.equ HOOK_POOL, {POOL}\n.equ HOOK_CARD, {CARD}\n.equ HOOK_INPUT, {INPUT}\n.equ PANEL, 0xC033E6F8\n.equ SCREEN_MANAGER, 0xC03404C0\n.equ BLECHY_BLOCK, {BLECHY_BLOCK}\n.equ BLECHY_SIZE, {len(block)}\n'
    constants += f'\n.equ MENU_SCREEN, {profile.screen}\n'
    constants += f'.equ MENU_RING_FIRST, {profile.ring_first}\n.equ MENU_RING_TOTAL, {profile.ring_total}\n'
    files = ['script_hooks.s','script_card.s','script_builtin.s','script_menu.s',
             'script_display.s','script_store.s','script_hw.s','script_events.s','script_app.s','script_shortcuts.s','script_remote.s','script_migrate.s','script_file.s','script_calibrate.s']
    if build != 'synth':
        files.append('fx_card.s')
    else:
        files.append('script_fx_none.s')
    files += ['script_hsv.s','script_seq.s','script_init.s','script_objects.s','script_timer.s','script_led.s']
    read = lambda names: '\n'.join(Path(__file__).with_name(name).read_text() for name in names)
    source = constants+'\n'+read(files)
    if build == 'synth':
        from . import synthaddr
        source = '\n'.join(line for line in source.splitlines() if not line.lstrip().startswith(';'))
        source = synthaddr.source(source, own=[(synthaddr.FREE_FROM,0xC0200000)], keep=[0xC07FFC00,0xC07FFFF8])
    variant = 'synth' if build == 'synth' else 'sampler'
    source = source.replace('@OBJECT_ROWS@', object_rows(constants, build))
    source = source.replace('@START_WRAPPER@', read([f'script_start_{variant}.s', 'script_boot_light.s']))
    source = source.replace('@MENU_TOPLEVEL@', Path(__file__).with_name(f'script_toplevel_{variant}.s').read_text())
    actions = '\n'.join(f'.equ {name}, {value}' for name, value in profile.actions.items())
    hooks=assemble(actions+'\n'+source,origin=origin)
    linked_glue={**(glue or {}),'API_KORG_LED':hooks.symbols['script_led_glue'],'API_KORG_MILLIS':hooks.symbols['script_clock_millis_glue'],**{f'API_KORG_{name}':hooks.symbols[f'script_{name.lower()}_glue'] for name in ['PLAY','STOP','PATTERN','TEMPO','PART','MUTE','BACKLIGHT']},'API_KORG_LED_HOLD':hooks.symbols['script_led_hold_glue'],'API_KORG_PAD_HOLD':hooks.symbols['script_pad_hold_glue'],'API_KORG_KNOB_HOLD':hooks.symbols['script_knob_hold_glue'],'API_KORG_KNOB':hooks.symbols['script_knob_glue'],'API_KORG_PASS_KEYS':hooks.symbols['script_pass_keys_glue'],'API_KORG_TOUCH_LOCK_X':hooks.symbols['script_touch_lock_x_glue'],'API_KORG_KEY_HOLD':hooks.symbols['script_key_hold_glue'],'API_KORG_PRESS_KEY':hooks.symbols['script_press_key_glue'],'API_KORG_READ_PATTERN_BYTES':hooks.symbols['script_read_pattern_bytes_glue'],'API_KORG_MENU_ADD':hooks.symbols['script_menu_add_glue'],'API_KORG_APP':hooks.symbols['script_app_glue'],'API_KORG_FILE_FRAME':hooks.symbols['script_file_frame_glue'],'API_KORG_GET':hooks.symbols['script_object_get_glue'],'API_KORG_SET':hooks.symbols['script_object_set_glue'],**{f'API_KORG_{name}':hooks.symbols[f'script_timer_{name.lower()}_glue'] for name in ['AFTER','EVERY','AFTER_STEPS','CANCEL']},**{f'API_KORG_READ_{name}':hooks.symbols[f'script_read_{name.lower()}_glue'] for name in ['TRANSPORT','TEMPO','PATTERN','PART','STEP','MUTE','KNOB']},'API_KORG_READ_CHAIN_MODE':hooks.symbols['script_read_chain_mode_glue'],'API_KORG_READ_PATTERN_VALUE':hooks.symbols['script_read_pattern_value_glue'],'API_KORG_REMAP_KEY':hooks.symbols['script_remap_key_glue'],**{f'API_KORG_SEQ_{name}':hooks.symbols[f'script_seq_{name.lower()}_glue'] for name in ['SET_STEP','SET_GATE','CLEAR_PART','SET_PART_VALUE','WRITE_STEPS','SET_PATTERN_VALUE']},**{f'API_KORG_STORE_{name}':hooks.symbols[f'script_store_{label}_glue'] for name,label in [('GET','get'),('SET','set'),('SAVE','save')]},**{f'API_KORG_DISPLAY_{name}':hooks.symbols[f'script_display_{label}_glue']
        for name,label in [('CLEAR','clear'),('TEXT','text'),('NUMBER','number'),('PIXEL','pixel'),('RECT','rect'),('CLEAR_RECT','clear_rect'),('TAKE','take'),('RELEASE','release'),('BITMAP','bitmap'),('TEXT_NUMBER','text_number')]}}
    vm=build_vm(include,origin=MORE3_START,glue=linked_glue)
    runtime_end=RUNTIME+vm.symbols['SCRIPT_RUNTIME_SIZE']
    pool_end=POOL+vm.symbols['SCRIPT_POOL_BYTES']
    (first_at,first),=hooks.sections
    if first_at!=origin or origin+len(first)>MORE3_END:
        raise ValueError(f'the code area runs over: {first_at:#x} + {len(first):#x} (limit {MORE3_END:#x})')
    if runtime_end>MENU_ITEMS or MENU_ITEMS_END>MENU_STATE or MENU_STATE+0x200>POOL or pool_end>CARD:
        raise ValueError(f'script code, runtime or pool exceeds its reserved area: runtime end {runtime_end:#x} (limit {MENU_ITEMS:#x}), pool end {pool_end:#x} (limit {CARD:#x})')
    s=hooks.symbols
    if s['SETTINGS_MAX']>0x120 or SETTINGS_RAM+0x240+4*s['MENU_MAX_TRUST']>SETTINGS_RAM_END:
        raise ValueError('the settings buffers or the checksum list run over their area')
    if s['STORE_IMAGE']+s['STORE_CAPACITY']>s['STORE_OTHER'] or s['STORE_OTHER']+s['STORE_CAPACITY']>END:
        raise ValueError('the store images run over the block buffer')
    if s['LIST_WORK_SIZE']>LIST_WORK_END-LIST_WORK or s['LIST_ORD']+s['LIST_MAX']>s['LIST_MORE']:
        raise ValueError('the work area of the plugin list runs over')
    if (s['LIST_TITLES']+s['LIST_MAX']*16>s['LIST_DESC']
            or s['LIST_DESC']+s['DESC_MAX_BYTES']+1>s['RM_MSG_AT'] or s['RM_INIT_AT']+4>s['RM_AT'] or s['RM_AT']+s['RM_SIZE']>s['RP_AT'] or s['RP_AT']+s['RP_SIZE']>s['SQ_AT'] or s['SQ_AT']+s['SQ_SIZE']>s.get('FX_STATE_AT',INPUT-CARD)):
        raise ValueError('the plugin list of the import page runs over the card work area')
    symbols={**vm.symbols,**hooks.symbols}
    layout=dict(code=MORE3_START,codeEnd=origin+len(first),runtime=RUNTIME,
        runtimeEnd=runtime_end,runtimeSize=vm.symbols['SCRIPT_RUNTIME_SIZE'],pool=POOL,poolEnd=pool_end,card=CARD,input=INPUT)
    return BuiltHooks(vm,vm.sections+hooks.sections+[(BLECHY_BLOCK,block)],symbols,layout,profile)

def make_patch(image,include,glue=None,build_name='hacktribe'):
    built=build(include,glue=glue,build=build_name)
    return built.apply(image),built.manifest()
