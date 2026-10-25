"""Link input and UI frame hooks with the native VM into an isolated FF area."""
from dataclasses import dataclass
import sys
from pathlib import Path
import struct
import hashlib
from .arm import assemble
from .ramdecl import area, share
from .script_vm import build as build_vm

BLECHY_BLOCK = 0xC0184000
BLECHY_BLOCK_END = 0xC0188000
BLECHY_FILE = Path(getattr(sys, '_MEIPASS', '') or Path(__file__).resolve().parents[2]) / 'data' / 'script' / 'blechy-block.hex'   # frozen: unpacked next to the code
CODE_START = 0xC01A6000
CODE_AT = CODE_START
INPUT = 0xC01F8000
CARD = 0xC01F7000
CODE_END = 0xC01AE000
MORE_START = 0xC018D000          # a second code area for the runtime: display, store, hardware, events and apps go here, so the
MORE_END = 0xC018FF00            # menu has room in the first; free (FF) in all three images, behind the idle insert effect
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
         (0xC0038D34,0xE3A03000,'script_early_hook'))
# Words that change to a plain value instead of a branch: the screen factory's bound and its table literal.
WORDS = ((0xC006E664,0xE350002C,0xE350002D),
         (0xC006E68C,0xC00F9CD8,MENU_TABLE))
# Vtable slots of the menu class that point into our code (offset in the table, symbol).
VTABLE_OVER = ((8,'menu_slot_exit'),(12,'menu_slot_keys'),(16,'menu_slot_prev'),(20,'menu_slot_next'),(24,'menu_slot_enter'),(40,'menu_slot_value'))

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
                              45, 29, 29, dict(HW_PANEL_KEY=0xC0042BB8, HW_PART_SELECT=0xC0081BB4,
                                              HW_MUTE_OBJECT=0xC06CA798 if build == 'stock' else 0xC06CA760,
                                              POWER_HOLD_MASK=0x08000000, SHORTCUTS=1, REMOTE=1, HW_ENCODER=0xC00419B4,
                                              SC_LEDMGR=0xC0345A1C, SC_PLAYER=0xC002FAFC, SC_PATPTR=0xC033E6A4,
                                              SC_BANK=0xC08B2940, SC_LOAD=0xC004AB84, SC_LEDSEND=0xC00875F4,
                                              MG_WORK=0xC0190100, MG_MKDIR=0xC009EB00, MG_GETFREE=0xC009E85C, MG_ALLOC=0xC0028DCC, MG_FREE=0xC0028DD4,
                                              MG_VRAM=0xC031B310, MG_MARK=0xC001531C, SYNC_GROUP_AT=0x3B80,
                                              # the collection on the card (fx_card.s): which build it is for, and the modulation table this build reads
                                              FX_BUILD=2 if build == 'stock' else 1, FX_MODS=0xC00D81EC if build == 'stock' else 0xC019FFFC))
    from . import synthaddr
    sites = []
    for address, expected, name in SITES:
        if name == 'script_early_hook':
            continue
        if name == 'script_card_hook':
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
        37, 28, 28, dict(HW_PANEL_KEY=0xC003D158, HW_PART_SELECT=0xC0072338, HW_MUTE_OBJECT=0xC0596DF8,
        POWER_HOLD_MASK=0, SHORTCUTS=1, REMOTE=0, HW_ENCODER=0,
        SC_LEDMGR=synthaddr.tr(0xC0345A1C), SC_PLAYER=synthaddr.tr(0xC002FAFC), SC_PATPTR=synthaddr.tr(0xC033E6A4),
        SC_BANK=synthaddr.tr(0xC08B2940), SC_LOAD=synthaddr.tr(0xC004AB84), SC_LEDSEND=synthaddr.tr(0xC00875F4),
        MG_WORK=0, MG_MKDIR=0, MG_GETFREE=0, MG_ALLOC=0, MG_FREE=0, MG_VRAM=0, MG_MARK=0, SYNC_GROUP_AT=0x3B80))   # power hold is not measured on the synth; the EXIT shortcuts are (docs/messungen/2026-10-24-blau-shortcuts-akkorde.md)


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
            ('script_card_hook','script_card_wrapper_end','Start-Wrapper erhält Register und Flags, prüft den Notschalter vor Menü und Plugins und führt den verdrängten nativen Befehl aus.'),
            ('script_card_load','script_card_load_end','Kartenlader prüft Panel und EXIT, öffnet die Plugin-Datei und kehrt ohne Karte oder Datei zurück.'),
            ('fx_card_load','fx_card_load_end','Der Lader der Sammeldatei e2sFx.all prüft Panel und EXIT, liest die Datei erst ganz zur Prüfung und schreibt nur dann Presets und Modulationen ins RAM; ohne Karte, Datei oder bei einem Fehler kehrt er zurück, ohne etwas zu schreiben.'),
            ('menu_arm','menu_arm_end','Das Menü prüft Panel, EXIT und Panel-Update, bevor es seinen Zustand initialisiert und sich scharf schaltet.'),
            ('menu_arm_load','menu_arm_load_end','Schaltet das Menü scharf und liest die Einstellungen genau einmal.'),
            ('menu_settings_load','menu_settings_end','Die Einstellungsdatei wird vor den Plugins gelesen; fehlt sie oder ist sie beschädigt, gelten die Voreinstellungen.'),
            ('blechy_boot','blechy_boot_end','Blechy, die eingebaute App, wird vor dem Kartenlader geladen, startet und schaltet die Laufzeit scharf, auch ohne Karte; mit EXIT beim Einschalten ist das Menü unscharf und die Funktion kehrt sofort zurück.'),
            ('menu_needs_confirm','menu_confirm','Der Kartenlader fragt für jedes geladene Plugin, ob es erst auf eine Zustimmung wartet; ohne Plugins läuft das nicht.'),
            ('menu_recount','menu_recount_end','Nach dem Laden zählt das Menü die Plugins und stellt die Seitenzahl ein.'),
            ('led_meter_hook','look_hooks_end','Die Haken der Anpassung (untere LEDs, Hintergrundlicht, Software-PWM, Display umkehren) geben die Firmware sofort zurück, wenn das Menü nicht scharf ist oder die Firmware das Licht für Power Save dimmt.'),
            ('shortcut_input','shortcut_tick','Die EXIT-Shortcuts im Eingangsfilter: prüfen Panel und EXIT beim Einschalten, merken sich EXIT und lassen jede Meldung durch, solange EXIT nicht auf dem Hauptbildschirm gehalten wird.'),
            ('shortcut_pool','shortcut_end','Literale der EXIT-Shortcuts.'),
            ('remap_input','remap_input_end','korg.remapKey im Eingangsfilter: ohne umgelegte Taste kehrt es beim ersten Vergleich zurück, mit Blechy ist die Laufzeit schon beim Start scharf; samt Literalen.'),
            ('migrate_start','migrate_end','Die Übernahme des alten Kartenordners: vor dem Sample-Lader prüft sie Panel, EXIT und die Ordner der Karte; nur wenn es keinen blechtribe-Ordner, aber einen hacktribe- oder electribe-sampler-Ordner gibt, fragt sie auf dem Display (Eingangsfilter und Rahmenhaken lesen ihren Schalter) und kopiert auf MENU.'),
            ('menu_event_right','menu_hooks_end','Rücksprünge der Menüstellen: Nachbarn im Ring, Spitzenebene, WRITE und Seitenzähler laufen schon vor dem Hauptbildschirm vorbei und lassen die Firmware ohne scharfes Menü unverändert.'),
        ]:
            if start in self.symbols and end in self.symbols:
                spans.append((self.symbols[start],self.symbols[end],why))
        menu_hooks=[dict(site=f'{address:#010X}'.replace('0X','0x'),kind='instruction',chain=chain,position='before',swallow=swallow)
            for address,chain,swallow in [
            (0xC006E8D8,'menu-top-level',False),(0xC006F094,'menu-write',True),(0xC008A83C,'menu-counter',False),(0xC008A8A8,'menu-counter',False),
            (0xC0064430,'menu-ring',False),(0xC0067754,'menu-ring',False)]]
        menu_hooks+=[dict(site='0xC0088284',kind='instruction',chain='led-meter',position='before',swallow=True)]
        menu_hooks+=[dict(site=f'0x{address:08X}',kind='instruction',chain='backlight',position='before',swallow=False)
            for address in (0xC0016C98,0xC0016CE0,0xC0016D28,0xC00289F4)]
        menu_hooks+=[dict(site='0xC00161A4',kind='instruction',chain='lcd-invert',position='before',swallow=False)]
        menu_hooks+=[dict(site='0xC006E664',kind='instruction',chain='menu-ring',position='replace',swallow=False),
            dict(site='0xC006E68C',kind='literal',chain='menu-ring',position='replace',swallow=False)]
        menu_hooks+=[dict(site='0xC0038D34',kind='instruction',chain='start',position='before',swallow=False)]
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
            area(MENU_STATE,0x200,'state of the BLECH menu and its two settings file buffers','tools/patch/script_hooks.py:MENU_STATE'),
            area(layout['pool'],layout['poolEnd']-layout['pool'],'plugin pool, SCRIPT_POOL_BYTES','tools/patch/script_hooks.py:POOL'),
            area(layout['card'],layout['input']-layout['card'],'work area of the card loader: file object, state, plugin list of the import page, the key commands of KORG.press and the record of korg.remapKey','tools/patch/script_hooks.py:CARD'),
            area(layout['input'],END-layout['input'],'block buffer for file reads, the two store images lie in it','tools/patch/script_hooks.py:INPUT')]+(
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
        for start,end in [(CODE_START,CODE_END),(MORE_START,self.layout['moreEnd']),(RUNTIME,self.layout['runtimeEnd']),(self.layout['runtimeEnd'],POOL),(POOL,self.layout['poolEnd']),(CARD,END),(BLECHY_BLOCK,BLECHY_BLOCK+len(self.sections[-1][1]))]:
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

def build(include, glue=None, blechy=None, build='hacktribe'):
    profile = runtime_profile(build)
    block=blechy_block() if blechy is None else blechy
    if len(block)%4 or BLECHY_BLOCK+len(block)>BLECHY_BLOCK_END:
        raise ValueError('the block of Blechy does not fit its place in the image')
    vm=build_vm(include,origin=CODE_START,glue=glue)
    origin=(CODE_START+len(vm.bytes)+31)&~31
    constants=include.split('.align 4',1)[0]
    constants += '\n'+ '\n'.join(f'.equ {key}, {value}' for key,value in vm.symbols.items() if key.startswith('RT_'))
    constants += '\n'+ '\n'.join(f'.equ VM_{name.upper()}, {vm.symbols[name]}' for name in ['script_run_event','script_runtime_init','script_load_block','script_load_block_ex'])
    constants += f'\n.equ VM_CRC_UPDATE, {vm.symbols["crc_update"]}'
    constants += ''.join(f'\n.equ {name.upper()}, {vm.symbols[name]}' for name in ['script_font','script_error_names'])
    constants += f'\n.equ MENU_ITEMS, {MENU_ITEMS}\n.equ MENU_STATE, {MENU_STATE}\n.equ MENU_TABLE, {MENU_TABLE}\n.equ MENU_VTABLE, {MENU_VTABLE}\n.equ HOOK_RUNTIME, {RUNTIME}\n.equ HOOK_POOL, {POOL}\n.equ HOOK_CARD, {CARD}\n.equ HOOK_INPUT, {INPUT}\n.equ PANEL, 0xC033E6F8\n.equ SCREEN_MANAGER, 0xC03404C0\n.equ BLECHY_BLOCK, {BLECHY_BLOCK}\n.equ BLECHY_SIZE, {len(block)}\n'
    constants += f'\n.equ MENU_SCREEN, {profile.screen}\n'
    constants += f'.equ MENU_RING_FIRST, {profile.ring_first}\n.equ MENU_RING_TOTAL, {profile.ring_total}\n'
    files = ['script_hooks.s','script_led.s','script_card.s','script_builtin.s','script_menu.s']
    more = ['script_display.s','script_store.s','script_hw.s','script_events.s','script_app.s','script_shortcuts.s','script_remote.s','script_migrate.s','script_file.s','script_calibrate.s']
    if build != 'synth':
        more.append('fx_card.s')
    read = lambda names: '\n'.join(Path(__file__).with_name(name).read_text() for name in names)
    source = constants+f'\n.equ MORE_START, {MORE_START}\n'+read(files)+'\n.org MORE_START\n'+read(more)
    if build == 'synth':
        from . import synthaddr
        source = '\n'.join(line for line in source.splitlines() if not line.lstrip().startswith(';'))
        source = synthaddr.source(source, own=[(synthaddr.FREE_FROM,0xC0200000)], keep=[0xC07FFC00,0xC07FFFF8])
    variant = 'synth' if build == 'synth' else 'sampler'
    source = source.replace('@START_WRAPPER@', Path(__file__).with_name(f'script_start_{variant}.s').read_text())
    source = source.replace('@MENU_TOPLEVEL@', Path(__file__).with_name(f'script_toplevel_{variant}.s').read_text())
    actions = '\n'.join(f'.equ {name}, {value}' for name, value in profile.actions.items())
    hooks=assemble(actions+'\n'+source,origin=origin)
    linked_glue={**(glue or {}),'API_KORG_LED':hooks.symbols['script_led_glue'],'API_KORG_MILLIS':hooks.symbols['script_clock_millis_glue'],**{f'API_KORG_{name}':hooks.symbols[f'script_{name.lower()}_glue'] for name in ['PLAY','STOP','PATTERN','TEMPO','PART','MUTE','BACKLIGHT']},'API_KORG_LED_HOLD':hooks.symbols['script_led_hold_glue'],'API_KORG_MENU_ADD':hooks.symbols['script_menu_add_glue'],'API_KORG_APP':hooks.symbols['script_app_glue'],'API_KORG_FILE_FRAME':hooks.symbols['script_file_frame_glue'],**{f'API_KORG_READ_{name}':hooks.symbols[f'script_read_{name.lower()}_glue'] for name in ['TRANSPORT','TEMPO','PATTERN','PART','STEP','MUTE','KNOB']},'API_KORG_READ_CHAIN_MODE':hooks.symbols['script_read_chain_mode_glue'],'API_KORG_READ_PATTERN_VALUE':hooks.symbols['script_read_pattern_value_glue'],'API_KORG_REMAP_KEY':hooks.symbols['script_remap_key_glue'],**{f'API_KORG_STORE_{name}':hooks.symbols[f'script_store_{label}_glue'] for name,label in [('GET','get'),('SET','set'),('SAVE','save')]},**{f'API_KORG_DISPLAY_{name}':hooks.symbols[f'script_display_{label}_glue']
        for name,label in [('CLEAR','clear'),('TEXT','text'),('NUMBER','number'),('PIXEL','pixel'),('RECT','rect'),('CLEAR_RECT','clear_rect'),('TAKE','take'),('RELEASE','release'),('BITMAP','bitmap'),('TEXT_NUMBER','text_number')]}}
    vm=build_vm(include,origin=CODE_START,glue=linked_glue)
    runtime_end=RUNTIME+vm.symbols['SCRIPT_RUNTIME_SIZE']
    pool_end=POOL+vm.symbols['SCRIPT_POOL_BYTES']
    (first_at,first),(more_at,more_code)=hooks.sections
    if first_at!=origin or more_at!=MORE_START or more_at+len(more_code)>MORE_END:
        raise ValueError(f'the second code area runs over: {more_at:#x} + {len(more_code):#x} (limit {MORE_END:#x})')
    if origin+len(first)>MENU_TABLE or runtime_end>MENU_ITEMS or MENU_ITEMS_END>MENU_STATE or MENU_STATE+0x200>POOL or pool_end>CARD:
        raise ValueError(f'script code, runtime or pool exceeds its reserved area: hooks end {origin+len(first):#x} (limit {MENU_TABLE:#x}), runtime end {runtime_end:#x} (limit {MENU_ITEMS:#x}), pool end {pool_end:#x} (limit {CARD:#x})')
    s=hooks.symbols
    if s['STORE_IMAGE']+s['STORE_CAPACITY']>s['STORE_OTHER'] or s['STORE_OTHER']+s['STORE_CAPACITY']>END:
        raise ValueError('the store images run over the block buffer')
    if (s['LIST_NAMES']+s['LIST_MAX']*s['LIST_NAME_SIZE']>s['LIST_TITLES'] or s['LIST_TITLES']+s['LIST_MAX']*16>s['LIST_DESC']
            or s['LIST_DESC']+s['DESC_MAX_BYTES']+1>s['RM_AT'] or s['RM_AT']+s['RM_SIZE']>s['RP_AT'] or s['RP_AT']+s['RP_SIZE']>s.get('FX_STATE_AT',INPUT-CARD)):
        raise ValueError('the plugin list of the import page runs over the card work area')
    symbols={**vm.symbols,**hooks.symbols}
    layout=dict(code=CODE_START,codeEnd=origin+len(first),more=MORE_START,moreEnd=MORE_START+len(more_code),runtime=RUNTIME,
        runtimeEnd=runtime_end,runtimeSize=vm.symbols['SCRIPT_RUNTIME_SIZE'],pool=POOL,poolEnd=pool_end,card=CARD,input=INPUT)
    return BuiltHooks(vm,vm.sections+hooks.sections+[(BLECHY_BLOCK,block)],symbols,layout,profile)

def make_patch(image,include,glue=None,build_name='hacktribe'):
    built=build(include,glue=glue,build=build_name)
    return built.apply(image),built.manifest()
