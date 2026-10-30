# Plugins for the Electribe

[Deutsche Version](plugins.md) | English version

As of 2026-10-15. This page is the English edition of [plugins.md](plugins.md). The German page is the
reference: it carries every measurement detail. This one keeps the facts a user needs and links to the
German page where a detail only matters to developers. The editor itself is in German, so its button
and menu labels appear here in German with a translation.

A plugin gives the Electribe a new function, such as a running light, a game on the display or a menu
page of your own. You put it on the device through the SD card, much like a plugin in music software. If
you want, you write your own: the plugin code is a subset of JavaScript.

The editor compiles a plugin into a block of bytecode that a small VM in the firmware runs. An error
switches the plugin off and shows a message in the BLECH menu. The Electribe keeps running.

All plugins are loaded at start and run at once: a plugin that only sets LEDs or remaps keys needs no
menu step. The **display** belongs to the device. A plugin with a screen of its own is an **app**: it
appears in the BLECH menu under GAMES or TOOLS, ENTER opens it and EXIT always closes it. If you really
want to draw on the display directly, take it with `korg.display.take()` and give it back with EXIT.
Loading a plugin never draws anything (section "Apps and the display").

The page has five parts: the language reference (structure, apps and display, language, events,
functions, limits), the card with its file format, the BLECH menu on the device, the Plugins page in the
editor, and the status section. What the language reference says holds for the language and its checks in
the browser and in the emulator. On the device the BLECH menu and the plugins of the card run; what
exactly is tested there is in "Status".

## Language reference

### Structure

The statements at the very top are the body of the plugin. It runs once at start: create variables, set
values, register handlers. After that only the handlers run, each when its event happens.

```js
korg.app("Zaehler", "TOOLS");
let count = 0;

function show() {
  korg.display.clear();
  korg.display.number(count, 0, 16);
}

korg.onEvent("open", () => show());
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) { count += 1; show(); }
});
```

`korg.onEvent("event", handler)` is allowed only at the top, one handler per event and plugin. The
handler is an arrow function or the name of a function. It may take fewer values than the event
delivers. Handlers become active once the body has run to its end without an error.

### Apps and the display

The display belongs to the firmware. A plugin draws into it only when it owns the display, which can
happen in two ways. Both end with EXIT: the firmware handles EXIT in its input filter before a plugin
sees the key, so a plugin can neither catch nor swallow EXIT. A plugin that does not own the display and
draws anyway is ignored: the calls do nothing and report nothing. Loading or importing a plugin never
takes the display.

**Way 1, the app in the menu (the normal case).** The plugin registers itself at the very top of its code
with `korg.app("Name", "Group")`. The name has 1 to 15 characters (ASCII), the group is `"GAMES"` or
`"TOOLS"`, and the registration stands once, not inside a function. The plugin runs from start, the app
too: its handlers for keys, pads, tempo and everything else always run, only `frame` arrives while the
app is open. In the BLECH menu the app is listed under GAMES or TOOLS. ENTER (the MENU key) opens it: the
display is cleared, the firmware shows its main screen, the app gets `open` and from then on `frame` and
the display. While it is open it owns the keys: the firmware does not see them (encoders, knobs, pads and
touchpad stay with the firmware, so playing goes on). One exception: **PLAY, STOP and REC** also reach the
firmware while the app is open (the sequencer starts and stops), and the app gets `buttonPress` and
`buttonRelease` for them as well. All other keys, the Part keys included, change nothing in the firmware.
EXIT closes the app, it gets `close`, and the display is the firmware's again. If the firmware leaves the
main screen for another reason, the app closes in the same way.

```js
// Snake as an app: opens in the menu under GAMES, starts over each time it is opened.
korg.app("Snake", "GAMES");
// ... game state and functions as in the example plugin Snake ...
korg.onEvent("open", () => { reset(); frames = 0; draw(); });
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PART_LEFT) dir = (dir + 3) % 4;
  if (key == korg.key.PART_RIGHT) dir = (dir + 1) % 4;
});
korg.onEvent("frame", () => { frames += 1; if (frames >= 3) { frames = 0; step(); } draw(); });
```

**Way 2, taking the display (use sparingly).** A plugin that is not an app can call
`korg.display.take()` in an event, as long as the firmware shows its main screen and nobody owns the
display. The function returns 1 on success, otherwise 0. Then the plugin draws until it calls
`korg.display.release()` or the user presses EXIT (the plugin then gets `close`). An app does not take the
display, it is opened from the menu. Not in the body: there is no display there.

```js
// A note on the display while PLAY is held.
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.PLAY && korg.display.take()) korg.display.text("PLAY aktiv", 0, 0);
});
korg.onEvent("buttonRelease", (key) => {
  if (key == korg.key.PLAY) korg.display.release();
});
```

**Margin.** Text and hints keep away from the edge of the display, as the firmware's menus do: 4 pixels left and right,
2 pixels top and bottom (a line of text at the top at `y = 2`, at the bottom at `y = 55`, right-aligned it ends at `x = 123`).
A playing field or a picture may go up to the edge. The plugins in the catalog keep to this.

Use way 2 only when a menu entry does not fit: the display is then taken until someone presses EXIT, and
the keys belong to the plugin as long as it owns the display. A plugin that only needs LEDs or keys never
takes the display.

### Language

- **Values:** whole 32-bit numbers (`-2147483648` to `2147483647`, hex up to `0xFFFFFFFF`) and short text.
  `true` is 1, `false` is 0.
- **Text:** only a literal in quotes (ASCII and ä, ö, ü, at most 31 characters) or a variable that holds one. You can
  compare with `==` and `!=` and pass it to `korg.*`, nothing more: no joining, no splitting. Numbers are
  shown with `korg.display.number`.
- **Variables:** `let` and `const`. A `const` with a fixed value is a constant and takes no space. Every
  variable has a fixed slot (4 bytes) in the plugin's variable area. The area is as large as the plugin
  declares variables and arrays, so a plugin without arrays needs little. The block format allows up to
  65536 slots per plugin. On the device, blocks, variables and plugin entries share 128 KiB, see
  "Limits".
- **Arrays:** `const a = new Array(16);` or `const a = [1, 2, 3];`, only at the top, a fixed 1 to 65535
  slots, numbers. `a[i]`, `a[i] = x`, `a[i] += x`, `a.length`. An index outside the array ends the plugin
  with an error.
  An array literal with only values from 0 to 255 (a picture for `korg.display.bitmap`, say) is stored as
  bytes in the block and costs no code; otherwise the code stores every value except 0 one by one.
- **Arithmetic:** `+ - * / %`, `& | ^ << >> ~`, comparisons `== != === !== < <= > >=`, `&& || !`, `? :`.
  Everything computes in 32 bits and wraps around. `/` divides whole numbers and truncates toward zero
  (unlike JavaScript), `%` takes the sign of the dividend, a shift count uses its lower 5 bits, `>>` keeps
  the sign. `&&` and `||` return one of the two values, as in JavaScript.
- **Statements:** assignment (`= += -= *= /= %= &= |= ^= <<= >>=`), `++` and `--` as a statement of their
  own, `if` / `else`, `while`, `for`, `break`, `continue`, `return`, blocks. Every statement ends with `;`.
- **Functions:** `function name(a, b) { ... }` at the top, with numbers as arguments and result (`return;`
  or the end gives 0). A function sees the variables at the top and its own, nothing else: there are no
  closures. A function must not call itself, not even through others (recursion), because every variable
  has a fixed slot.
- **Not included:** fractions, objects of your own (the Electribe itself comes as objects, see
  "The Electribe as objects"), `var`, `switch`, `do`, exceptions, template strings, `null`,
  assignment inside an expression.

A compile error names line and column and says what to do. The wording is German for now.

### Events

| Event | Values | When |
|---|---|---|
| `ready` | | once, in the first frame after start |
| `frame` | | 25 times a second; an app gets it only while it is open |
| `buttonPress`, `buttonRelease` | `key` | key pressed, released; compare `key` with a name such as `korg.key.TAP`, see "Names for keys and LEDs" |
| `knob` | `index`, `value` | knob moved (0 to 1023) |
| `encoder` | `index`, `delta` | encoder turned |
| `pad` | `index`, `down`, `velocity` | pad pressed or released |
| `touch` | `x`, `y`, `first` | touchpad touched, or the finger on it moved. `x` and `y` are the values of the panel message (0 to 1023, `y` pointing up, not tested on the device). `first` is 1 at the first position of a touch, where the finger lands, otherwise 0. `buttonPress` with `korg.key.TOUCHPAD` carries no position; the position comes with the `touch` right after, and that one carries `first`. A handler that takes only `x` and `y` stays version 1; taking `first` needs API version 6 |
| `step` | `step` | sequencer step (16th note) |
| `beat` | | quarter note |
| `play`, `stop`, `rec` | | transport |
| `patternChange` | `index` | pattern changed |
| `partChange` | `part` | part changed |
| `mute` | `part`, `muted` | part muted or not |
| `tempo` | `tenthsBpm` | tempo changed |
| `save` | | WRITE in Global, power off |
| `menu` | `id`, `value` | someone turned a page that the plugin created with `korg.menu.add` on the main dial |
| `open`, `close` | | only for apps and for a plugin that took the display: `open` when the user opens the app in the menu, `close` when EXIT closes it (or the firmware leaves the main screen). They go only to this plugin and never come from outside |

How the sequencer events arise: once per frame the firmware hook compares the firmware's state words
(transport, tempo, pattern, part, step of part 0, mutes) with those of the previous frame and queues one
event for each change. The grid is therefore 40 ms. At the top tempo (300 BPM, 20 steps a second) every
step still arrives. If something changes several times between two frames, a plugin sees one change. The
first reading after the runtime is armed counts as the starting state and triggers nothing. `step` carries
the step counter of part 0 (0 to 63), `beat` comes with every fourth step (with BEAT 8 every half note of the real tempo), `play` with transport 1, `stop`
with 0 or 2, `rec` on the change to 3 or 4, `mute` once per changed part with its new state. A plugin also
sees what it triggered itself (`korg.tempo` triggers `tempo`). A pattern change sets the tempo of the new
pattern, and `tempo` follows. `save` comes from a hook at the entry of the firmware's settings-write
function. When the device powers off, the runtime keeps running for about a second, but `korg.store` no
longer writes then, because the "Power Off" window is open. Details of the hooks:
[German page](plugins.md#ereignisse).

All events except `ready` and `frame` travel through a ring with 64 places. When it is full, the new event
is lost and counted. A knob that is turned again at once keeps only its last value. The handlers of one
frame may run 5 ms in total; a plugin that goes over is switched off. A single handler over 0.5 ms is a
warning. Only the plugin that runs over is switched off: the other plugins, the remaining inputs and the
frame handler carry on in the next frame, and events already delivered are not repeated. Handlers that
have not started yet when the time runs out are postponed and stay on.

One cycle delivers `ready` once per plugin first, then collects the waiting inputs, and delivers `frame`
last. Inputs that arrive later wait in the ring for the next cycle. New plugins get `ready` when the rest of
the previous cycle is done.

### The Electribe as objects

A plugin reads and sets what the Electribe is doing like a variable: `korg.tempo` is the tempo,
`korg.tempo = 1280;` changes it, `korg.parts[3].muted = 1;` mutes part 4. These are no objects of the
language that a variable could hold. The compiler turns every read and every assignment into the call
listed next to it in the table below, and the block is the same. A plugin written this way therefore runs
on every device those calls run on, BLECHTRIBE 1.2 included. The limits and events of the call apply:
like `korg.tempo(…)`, `korg.tempo = …` is not allowed in the body.

| Property | Read | Set | Same as |
|---|---|---|---|
| `korg.tempo` | tempo in tenths of a BPM, 1280 is 128.0 | 100 to 3000 | `korg.read.tempo()`, `korg.tempo(x)` |
| `korg.transport` | 0 stop, 1 play, 2 pause, 3 REC armed, 4 recording | no, use `korg.play()` and `korg.stop()` | `korg.read.transport()` |
| `korg.selectedPattern` | selected pattern, 0 to 249 | selects another one | `korg.read.pattern()`, `korg.pattern(x)` |
| `korg.selectedPart` | selected part, 0 to 15, 16 for all | 0 to 15 | `korg.read.part()`, `korg.part(x)` |
| `korg.millis` | milliseconds since the first call | no | `korg.millis()` |
| `korg.parts[i].step` | step counter of the part, 0 to 63 | no | `korg.read.step(i)` |
| `korg.parts[i].muted` | 1 when the part is muted | 1 muted, 0 playing | `korg.read.mute(i)`, `korg.mute(i, x)` |
| `korg.knobs.LEVEL`, `korg.knobs[i]` | last value of the knob, 0 until it moved | no | `korg.read.knob(i)` |
| `korg.store[i]` | stored value of slot 0 to 15, otherwise 0 | yes, to the card with `korg.store.save()` | `korg.store.get(i, 0)`, `korg.store.set(i, x)` |
| `korg.led.TAP`, `korg.leds[i]` | no | brightness 0 to 255 | `korg.led(i, x)` |
| `korg.chainMode` | 1 when CHAIN MODE is on in the Global menu (only then does the firmware chain) | no | `korg.read.chainMode()` |
| `korg.current.tempo` and the other values below | the pattern that plays, with its unsaved changes | no | `korg.read.patternValue(-1, -1, value)` |
| `korg.patterns[i].tempo` and the other values below | pattern `i` (0 to 249) as stored | no | `korg.read.patternValue(i, -1, value)` |
| `korg.parts[i].cutoff` and the other part values below | part `i` (0 to 15) in the pattern that plays | no | `korg.read.patternValue(-1, i, value)` |

**Values of a pattern** (`korg.current.…`, `korg.patterns[i].…`): `tempo` (tenths of BPM), `swing` (-48 to 48), `length`
(bars, 1 to 4), `beat` (0 16ths, 1 32nds, 2 8th triplets, 3 16th triplets, 4 8ths with BLECH), `key` (0 C to 11 B), `scale`, `chordSet`,
`level`, `mfxType`, `chainTo` (the next pattern, 0 to 249, -1 without a chain), `chainRepeat` (at least 1).
**Values of a part** (`korg.parts[i].…`): `sample` (slot), `filterType`, `cutoff`, `resonance`, `egInt` (-63 to 63),
`modType`, `modSpeed`, `modDepth`, `attack`, `decay`, `level`, `pan` (-63 left to 63 right), `ifxOn`, `ifxType`,
`ifxEdit`, `pitch` (-63 to 63), `glide`, `voiceAssign`, `oscEdit`, `mfxSend`. All values are read only, in the device's
units (mostly 0 to 127). The list and where each value comes from is in `data/script/contract.mjs` (`PATTERN_FIELDS`,
`PART_FIELDS`); the places are measured in the device map `data/map/pattern.mjs`. From API version 8.

`+=`, `-=` and the other compound assignments work on everything that can be read and set, and so do
`++` and `--`: `korg.tempo += 10;` reads the tempo and sets it 1.0 BPM higher. The index in the brackets
must not contain a function call there. `korg.led.TAP` on its own is still the number of the LED, as in
`korg.led(korg.led.TAP, 255)`; only on the left of an assignment does it set the LED.

The knobs carry the names of the panel table: `LEVEL`, `PAN`, `PITCH`, `RESONANCE`, `EG_INT`,
`MOD_DEPTH`, `ATTACK`, `IFX_EDIT`, `DECAY`, `OSC_EDIT` and `MOD_SPEED`, numbers 0 to 10 in this order.

```js
// From step 16 of part 1 on, part 4 is muted, anew in every bar.
korg.onEvent("step", (step) => {
  korg.parts[3].muted = korg.parts[0].step >= 15 ? 1 : 0;
});
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) korg.tempo += 10;
  korg.led.TAP = korg.transport == 1 ? 255 : 0;
});
```

The calls in the table below stay valid, older plugins keep running unchanged. What is an action stays
a call: drawing, pressing PLAY, registering an app, saving.

### The Electribe as an object tree (API 10, BLECHTRIBE 1.3.8)

From API 10 on, the settings of the Electribe and of the BLECH menu hang on long paths. A path reads and sets
like a property above; the compiler turns it into `korg.get` or `korg.set` with the number of the leaf, so long
names cost nothing on the device. A plugin that uses a path needs API 10 and does not run on older firmware
(it refuses the block).

A value outside the range is clamped to the nearest limit and counted (`korg.system.repairs`), the plugin keeps
running. When the value is known at compile time, the compiler reports it as an error. A misspelled path is a
compile error, the message names what exists at that point. The runtime checks the stored values at start,
wherever an invalid value comes from, and clamps it or resets it to the factory value; that counts in
`korg.system.repairs` as well.

| Path | Read | Set | Range |
|---|---|---|---|
| `korg.menu.blech.customizations.display.intensity` | brightness of the display light, like the page INTENSITY | yes, at once; WRITE in the menu keeps it | 0 (off) to 15 (full) |
| `korg.system.repairs` | how many values were clamped or reset since start | no | 0 to 2147483647 |
| `korg.system.testMode` | whether the test mode is on: display, light and every LED dark, Auto Power Off held | no, over USB only; RAM only, off after a restart | 0 (off) to 1 (on) |
| `korg.system.keepAwake()` | (a call, not a value) | starts the 4 hours of Auto Power Off again, as a key on the device does | |

```js
// Light off while the app is open, back as it was afterwards.
let light = 15;
korg.app("Dark", "TOOLS");
korg.onEvent("open", () => {
  light = korg.menu.blech.customizations.display.intensity;
  korg.menu.blech.customizations.display.intensity = 0;
});
korg.onEvent("close", () => {
  korg.menu.blech.customizations.display.intensity = light;
});
```

The test mode makes the device look switched off while it runs: display off, display light off, every LED at 0,
also when the firmware, Blechy or another plugin sets them, and Auto Power Off does not switch it off. The device
still takes keys, knobs and pads, and its picture can be read over USB. Only the computer switches it, over USB
([test mode](test-modus.md), German); a plugin only reads `korg.system.testMode`, so none can leave the device dark at
every start. When it ends, the light and the LEDs come back as they would be without the test mode; an LED a plugin
set meanwhile shows that plugin's value.

More branches (`korg.global`, `korg.patterns`, `korg.parts`, the other pages of BLECH) come with the next
versions; the old names stay valid.

### Timers (API 11, BLECHTRIBE 1.3.8)

A plugin cannot wait: all handlers of a frame have 5 ms together, a `wait(ms)` would stop the device. Timers do it
instead. You hand over a function, the runtime calls it later:

| Call | Effect |
|---|---|
| `korg.after(ms, fn)` | calls `fn` once, as soon as `ms` milliseconds have passed (0 to 86400000) |
| `korg.every(ms, fn)` | calls `fn` every `ms` milliseconds (1 to 86400000) until `korg.cancel` stops the timer |
| `korg.afterSteps(n, fn)` | calls `fn` once when the sequencer is `n` steps (16ths, 1 to 65535) further |
| `korg.cancel(number)` | stops the timer with this number |

`fn` is the name of a function without parameters or an arrow without values, `() => { ... }`. Like every function it
sees the global variables only, not the local ones of the place that set the timer. The three calls return the number
of the timer, which `korg.cancel` takes. Each plugin has 8 slots; when all are taken, -1 comes back and nothing
happens. A one-off timer frees its slot as soon as it ran. An old number whose timer already ran does not stop the timer
that has the slot by now, and `korg.cancel(-1)` does nothing, so the -1 of a full `korg.after` can be passed on safely.

The runtime checks the timers at the start of each frame, every 40 ms. A timer runs after `ms` at the earliest and one
frame later at the latest: `korg.after(1000, fn)` comes after 1000 to 1040 ms. `korg.every` keeps its grid, a late frame
does not move the next time. Setting `korg.after` again inside `fn` counts from the frame `fn` ran in instead, and moves
by up to 40 ms each round. Timers run for a closed app too, and they go only to the plugin that set them. They are
allowed everywhere except in `save`, the body included.

`korg.afterSteps` counts the `step` events while the sequencer runs: on STOP the count stands, on PLAY it goes on, and it
follows the tempo. The timer runs in the same frame as the `step` event that sets it off, right after it. When two steps
come in one frame at a very high tempo, the runtime sees only one (at 300 BPM steps are 50 ms apart, frames 40 ms).

```js
// The TAP LED blinks every 500 ms, after 2 seconds the display shows a message.
let on = 0;
function blink() {
  on = 1 - on;
  korg.led(korg.led.TAP, on * 255);
}
korg.onEvent("ready", () => {
  korg.every(500, blink);
  korg.after(2000, () => { korg.display.take(); korg.display.text("HELLO", 0, 0); });
});
```

```js
// One bar (16 steps) after PLAY part 1 goes mute; STOP before that and nothing happens.
let timer = -1;
korg.onEvent("play", () => { timer = korg.afterSteps(16, () => { korg.mute(0, 1); }); });
korg.onEvent("stop", () => { korg.cancel(timer); });
```

The clock behind the timers and `korg.millis()` is Timer3 (150 MHz), which the firmware lets wrap every second. The
runtime brings it up to date every frame; whole seconds lost between two calls (before the first frame after power-on)
it takes from the operating system's tick count, one per millisecond. Measured in the emulator
([measurement](messungen/2026-10-29-plugin-timer.md), German): after the start a frame comes every 40 ms, 46 ms at most,
also across a pattern change; the firmware loads the samples before the first frame, and a plugin on the card starts
only after that, so a timer from the body comes on time. Not yet checked on the device.

### Functions of the Electribe

All names begin with `korg.`. Numbers outside the range end the plugin with an error. "Allowed in" names
the places a call may be made from. "Like `korg.led`" means: in all events except the body and `save`.

| Call | Effect | Allowed in |
|---|---|---|
| `korg.led(index, level)` | queue an LED job, `index` 0 to 87 (best a name such as `korg.led.TAP`), `level` 0 to 255 | all events except the body and `save` |
| `korg.millis()` | milliseconds since the first call, from Timer3 (150 MHz), which wraps every 150 million ticks; whole seconds between two calls from the operating system's tick count | everywhere |
| `korg.after(ms, fn)`, `korg.every(ms, fn)`, `korg.afterSteps(n, fn)`, `korg.cancel(number)` | timers, see above. From API version 11 | everywhere except `save` |
| `korg.app(name, group)` | registers the plugin as an app: `name` 1 to 15 characters, `group` `"GAMES"` or `"TOOLS"`. Returns the number of the app, -1 if all 8 places are taken. As a statement of its own at the top, once per plugin (the compiler checks this) | body only |
| `korg.file.frame(array, file, index)` | reads frame `index` (0 to 65535) of the file `GIFnn.E2G` (`file` 0 to 99 is nn) in `KORG/blechtribe/Gif/` into the array, one byte to a slot, which is exactly what `korg.display.bitmap(array, 0, 0, 128)` draws. The array needs at least 1024 slots. Returns the frame's delay in ms (at least 1), 0 past the last frame, -1 without a file, for a wrong or cut file and outside the main screen; after -1 the device may have changed the last quarter of the array. From API version 7 | like `korg.led` |
| `korg.display.take()` | take the display (way 2, see above); 1 on success, 0 if not (an app, another owner, not the main screen) | like `korg.led` |
| `korg.display.release()` | give the display back | like `korg.led` |
| `korg.display.clear()` | clear the display; the drawing calls only work for the owner of the display (the open app, or whoever took it) | like `korg.led` |
| `korg.display.text(text, x, y)` | text with its top left corner at `x`, `y` (0 to 127, 0 to 63) | like `korg.led` |
| `korg.display.number(value, x, y)` | a number | like `korg.led` |
| `korg.display.pixel(x, y, on)` | one pixel, `on` 0 or 1 | like `korg.led` |
| `korg.display.textNumber(text, value, x, y)` | text and right behind it the number, without the plugin counting digits; like `text` followed by `number`, the number starts at the character after the text (6 pixels per character). From API version 6 | like `korg.led` |
| `korg.display.bitmap(array, x, y, width)` | draws an image from a global array, top left at `x` (-128 to 127), `y` (-64 to 63); whatever reaches past the edge is cut off. Layout and cost below. From API version 6 | like `korg.led` |
| `korg.display.rect(x, y, width, height)` | filled rectangle | like `korg.led` |
| `korg.display.clearRect(x, y, width, height)` | clear a rectangle | like `korg.led` |
| `korg.store.get(slot, default)` | the stored value of slot `slot` (0 to 15) of this plugin, or `default` if none was ever stored there | everywhere, also in the body |
| `korg.store.set(slot, value)` | set a value in RAM, not on the card yet | everywhere |
| `korg.store.save()` | queue a save | like `korg.led` |
| `korg.read.transport()` | transport state: 0 stop, 1 play, 2 pause, 3 REC ready, 4 recording | everywhere |
| `korg.read.tempo()` | tempo in tenths of a BPM (1600 is 160.0) | everywhere |
| `korg.read.pattern()` | selected pattern, 0 to 249 | everywhere |
| `korg.read.part()` | selected part 0 to 15, 16 for all | everywhere |
| `korg.read.step(part)` | step counter of the part, 0 to 63 | everywhere |
| `korg.read.mute(part)` | 1 if the part is muted | everywhere |
| `korg.read.knob(index)` | last raw value of knob `index` (0 to 19) that the runtime has seen, 0 until then | everywhere |
| `korg.read.chainMode()` | 1 when CHAIN MODE is on in the Global menu. From API version 8 | everywhere |
| `korg.read.patternValue(pattern, part, value)` | a value of a pattern: `pattern` -1 the one that plays, 0 to 249 a stored one; `part` -1 a value of the pattern, 0 to 15 one of the part; `value` the number in `PATTERN_FIELDS` or `PART_FIELDS`. Easier to read with the names above (`korg.current.tempo`). From API version 8 | everywhere |
| `korg.play()` | press and release PLAY, through the firmware's key path | like `korg.led` |
| `korg.stop()` | press and release STOP | like `korg.led` |
| `korg.pattern(index)` | select a pattern, 0 to 249 | like `korg.led` |
| `korg.tempo(tenthsBpm)` | set the tempo, 100 to 3000 | like `korg.led` |
| `korg.part(part)` | select a part, 0 to 15 | like `korg.led` |
| `korg.mute(part, muted)` | mute a part (1) or let it play (0); the firmware only knows toggling, so the runtime presses the pad only if the state is not already right | like `korg.led` |
| `korg.backlight(red, green, blue)` | switch the three colours of the display light on (1) or off (0), through the firmware's GPIO function; on battery with Power Save "Auto" the firmware's dimming routine keeps overwriting the colour; if the user chose a mixed colour with levels between 1 and 14 in the menu, its PWM overwrites the colour as well | like `korg.led` |
| `korg.menu.add(name, min, max, value)` | creates a page in the BLECH menu on the device and returns its number (-1 if all 12 places are taken). `name` at most 15 characters, the page shows `value` (clamped to `min` to `max`, magnitude below 100 million) and the plugin name. When the main dial is turned, the plugin gets `menu`(number, value). The same name from the same plugin is the same page. `min` above `max` is an argument error | body and `ready` only |
| `korg.ledHold(on)` | 1 stops the firmware from rewriting the panel LEDs (pads, keys and lower RGB LEDs then show what the plugin set), 0 gives them back and makes the firmware resend all LEDs; if the last running plugin fails, the runtime gives them back itself | like `korg.led` |
| `korg.padHold(on)` | 1 keeps pad presses from the firmware: no sound, no change to the step, while the plugin still gets `pad`. The runtime sets the pad bit of the mask the input filter reads before the firmware. 0 gives the pads back; the runtime does that itself as well when an app closes and when no plugin is left running. A release always follows its press: when the press was kept from the firmware, so is the release, otherwise it reaches the firmware. From API version 12 | like `korg.led` |
| `korg.remapKey(from, to)` | the key `from` reaches the firmware and the plugins as the key `to` (both 0 to 33, best names like `korg.key.PART_ERASE`) while the plugin runs: the input filter rewrites the code in the panel message before the firmware reads it, so the firmware does exactly what it does with `to`. One remap holds for all plugins, the last one counts; the same key twice takes it back. EXIT cannot be remapped. From API version 8 | only in the body and in `ready` |
| `korg.seq.setStep(part, step, note, velocity)` | writes step `step` (0 to 63) of part `part` (0 to 15) in the pattern that plays: `note` 0 to 127 with `velocity` 1 to 127 turns it on, with that note in the first note place (the other three empty) and the trigger on; `note` -1 or `velocity` 0 turns it off. The gate stays as it is. From API version 9 | like `korg.led` |
| `korg.seq.setGate(part, step, gate)` | sets the gate of the step, 0 to 127; 96 is a whole step, 127 ties into the next note. From API version 9 | like `korg.led` |
| `korg.seq.clearPart(part)` | turns all 64 steps of the part off; notes, gates and velocities stay. From API version 9 | like `korg.led` |

**Writing steps** (`tools/patch/script_seq.s`, from API version 9): `korg.seq.*` writes into the pattern in RAM, the
one that plays or is being edited, just like the dice roll with SHIFT + PART ERASE
([dice](messungen/2026-10-16-wuerfeln.md), German): the same bytes of the step, no detour through the panel. The sequencer
plays a written step on its next pass, also while it runs (measured in the emulator, see below). The pattern in RAM then differs
from its stored place and counts as unsaved, as after an edit by hand: only WRITE stores it, and without WRITE the change is
gone once another pattern is loaded. Flash and card stay untouched, and SHIFT + EDIT< undoes nothing. The pads show the steps of
the selected bar section; when a plugin wrote steps in a frame, the runtime tells the firmware once at the end of the frame and
the pads draw again (on the main screen only, otherwise in the next frame there). A step behind the length of the pattern or
behind the part's LAST STEP is written but not played. Notes are MIDI notes, as with the dice: 48 is the root C that the
pattern's key (`korg.current.key`) is added to.

```js
// TAP writes an arpeggio into the selected part: root, third, fifth and octave
// in the pattern's key, on every second 16th, as long as the pattern.
const chord = [0, 4, 7, 12];
korg.onEvent("buttonPress", (key) => {
  if (key != korg.key.TAP) return;
  let part = korg.selectedPart;
  if (part > 15) return;
  korg.seq.clearPart(part);
  for (let step = 0; step < korg.current.length * 16; step += 2) {
    let note = 48 + korg.current.key + chord[(step / 2) % 4];
    korg.seq.setStep(part, step, note, step % 8 == 0 ? 110 : 80);
    korg.seq.setGate(part, step, 40);
  }
});
```

An arpeggiator that follows along writes the step that comes next in the `step` event. A call costs little (`setStep` 6,
`setGate` 4, `clearPart` 30 units); a whole pattern of 64 steps fits easily into one frame.

**Display on the device:** the runtime keeps its own image of 1024 bytes (8 pages of 128 columns, bit 0 is
the top row) and draws only into that. Coordinates past the edge are cut off, never wrapped. Only the owner
of the display may draw (the open app, or a plugin that took it): the calls of any other plugin do
nothing. While there is an owner, the frame hook copies the image over the firmware's display RAM every
frame, after the firmware has drawn its widgets, but only while the main screen is open. Without an owner
the runtime does not touch the display. Menus and windows are shown by the firmware as usual, a plugin
does not see them. The font is a 5 by 7 font of our own with 6 pixels per character; the same table is used
in the browser and on the device, and the output matches the browser model pixel for pixel (70 cases
compared in the emulator). Text is at most 31 characters, numbers are drawn in decimal.

**Images from arrays** (`korg.display.bitmap`): one slot of the array holds the 8 pixels of a column, the
lowest bit is the top pixel (only the lower 8 bits count). This is the layout of the display RAM and of the
usual bitmaps for OLED displays. A strip is `width` slots, from left to right, and the strips follow from
top to bottom. The height is 8 times the number of whole strips (array length divided by `width`, any
remainder is ignored); the width goes up to 128. Only set pixels are drawn and nothing is cleared, so use
`clearRect` first if you need that. `y` does not have to be a multiple of 8; each slot then spreads over two
pages of the display RAM. Example, a smiley of 8 by 8 pixels:

    const gesicht = [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C];
    korg.display.bitmap(gesicht, 10, 5, 8);

Only the name of a global array can be passed (`const picture = [...]` or `new Array(n)`). If `width` is a
fixed number, the compiler checks that at least one strip fits into the array; the VM checks on every
call that the array lies inside the variable area (otherwise `BAD_VAR`). Zeros in an array literal cost no
code, because the runtime clears every variable slot on load. A call costs 14 units plus 3 for each slot
of the array (an image of 41 by 56 pixels with 287 slots costs 875). The value is based on ARM instruction
counts measured in the emulator. Empty slots and slots outside the display cost less than counted.
`textNumber` is counted like `text`, with the upper bound of 250: the real effort is higher (about 4900
instructions for 5 characters and 3 digits), and the 5 ms of the frame stay the limit.

**Touch with position:** the panel sends the position as two 16-bit values; the input filter takes them as
they are, without clamping (measured in the emulator with the firmware). Key 34 (`0x22`) comes on its own,
without a position, and triggers no `touch`. The filter remembers for each touch whether the first position
has arrived: landing (key 34 pressed) resets it, the first position after that is `first` = 1, even without
a key press before it, and lifting the finger resets it. If the ring runs full, a first `touch` can be lost
too. How the pad lines up with the display is not measured: the editor and the emulator send 0 to 1023
across the whole pad, `y` pointing up; Blechy assumes `x / 8` as the display column. **Open on the
device.**

**Error message on the display:** if an error switches off the plugin that owns the display (the open app),
the runtime replaces the image with three lines: the plugin name, `Line` with the source line, and
the name of the error (`DIV_ZERO`). The error of any other plugin appears in the BLECH menu on its page
(`DIV_ZERO L3`), and the display stays untouched. The firmware stays usable and other plugins keep running.

Nothing may be drawn in the body yet: the firmware overwrites LEDs at start, and there is no display there.
Output belongs in `ready`, `frame`, `open` or the input handlers.

**LED jobs:** the last request for each LED counts, and the value zero is an explicit request too. Equal
jobs within the same frame are merged. At most 16 packets per frame are accepted. A packet needs five
bytes, and after accepting it at least 256 bytes must remain free in the firmware's queue. The limit is a
derived default: 16 packets at 25 Hz make at most 400 plugin packets a second, not a throughput measured
on the device. The firmware may keep changing LEDs. A new frame therefore forgets what was last sent,
without resending old requests on its own. A plugin that wants a value in every frame requests it again in
`frame`. Detail: [German page](plugins.md#funktionen-der-electribe).

### Names for keys and LEDs

Instead of `key == 11` or `korg.led(20, 255)` you write what you mean:

```js
korg.onEvent("buttonPress", (key) => {
  if (key == korg.key.TAP) korg.led(korg.led.TAP, 255);
  if (key == korg.key.PART_LEFT) korg.led(korg.led.PAD_1_RED, 255);
});
```

`korg.key.NAME` is the key code that `buttonPress` and `buttonRelease` deliver as `key`. `korg.led.NAME` is
the LED number for the first argument of `korg.led`. The names are constants of the language: the compiler
writes the number where the name stands. A block with names is therefore byte for byte the same as one with
numbers (`test/script-names.test.mjs` checks this on all example plugins), nothing changes on the device or
in the block size, and the block version stays. Numbers remain allowed. A name can be used like a number in
`const` and in expressions (`const BASE = korg.led.PAD_1_RED;`, `BASE + 2`). A name that does not exist is a
compile error and lists similar names. That `korg.led` is also the function does no harm: with parentheses
it is the call, with `.NAME` it is the constant.

The name is the label on the device in CAPITAL LETTERS with underscores: `GATE ARP` is `GATE_ARP`,
`◄ Part` and `Part ►` are `PART_LEFT` and `PART_RIGHT`, `◄ Edit` and `Edit ►` are `EDIT_LEFT` and
`EDIT_RIGHT`, the keys `1` to `4` are `BAR_1` to `BAR_4`. A second LED of the same key carries its colour in
the name (`PLAY_BLUE`, `BAR_1_BLUE`), and so do the pads: `PAD_1_RED`, `PAD_1_BLUE` up to `PAD_16_BLUE`.
The blue pad LED shows the selected part. The red pad LEDs are 2 apart, `PAD_1_RED + 2` is `PAD_2_RED`.
Where the numbers come from (measured, or derived from Freetribe) is noted in `data/panel.mjs`.

**Keys** (`korg.key`):

| Name | Number | Key |
|---|---|---|
| `korg.key.REC` | 0 | REC |
| `korg.key.STOP` | 1 | STOP |
| `korg.key.PLAY` | 2 | PLAY |
| `korg.key.TAP` | 3 | TAP |
| `korg.key.GATE_ARP` | 4 | GATE ARP |
| `korg.key.TOUCH_SCALE` | 5 | TOUCH SCALE |
| `korg.key.MASTER_FX` | 6 | MASTER FX |
| `korg.key.MFX_HOLD` | 7 | MFX HOLD |
| `korg.key.EDIT_LEFT` | 8 | ◄ Edit |
| `korg.key.MENU` | 9 | MENU |
| `korg.key.SHIFT` | 10 | SHIFT |
| `korg.key.PART_LEFT` | 11 | ◄ Part |
| `korg.key.EDIT_RIGHT` | 12 | Edit ► |
| `korg.key.EXIT` | 13 | EXIT |
| `korg.key.WRITE` | 14 | WRITE |
| `korg.key.PART_RIGHT` | 15 | Part ► |
| `korg.key.PART_MUTE` | 16 | PART MUTE |
| `korg.key.PART_ERASE` | 17 | PART ERASE |
| `korg.key.LPF` | 18 | LPF |
| `korg.key.TRIGGER` | 19 | TRIGGER |
| `korg.key.HPF` | 20 | HPF |
| `korg.key.SEQUENCER` | 21 | SEQUENCER |
| `korg.key.BPF` | 22 | BPF |
| `korg.key.KEYBOARD` | 23 | KEYBOARD |
| `korg.key.CHORD` | 24 | CHORD |
| `korg.key.STEP_JUMP` | 25 | STEP JUMP |
| `korg.key.MFX_SEND` | 26 | MFX SEND |
| `korg.key.PATTERN_SET` | 27 | PATTERN SET |
| `korg.key.BAR_1` | 28 | key 1 |
| `korg.key.BAR_2` | 29 | key 2 |
| `korg.key.BAR_3` | 30 | key 3 |
| `korg.key.BAR_4` | 31 | key 4 |
| `korg.key.AMP_EG` | 32 | AMP EG |
| `korg.key.IFX_ON` | 33 | IFX ON |
| `korg.key.TOUCHPAD` | 34 | touchpad touched |

The keys `1` to `4` and `TOUCHPAD` (touching the touchpad, with `touch` for the position) arrive as
`buttonPress` like any key. An encoder, a knob or a pad sends no `buttonPress`, but `encoder`, `knob` and
`pad` with their `index`.

**Knobs** (`index` of `knob`, `korg.read.knob(index)`, `korg.knobs.NAME`):

| Index | Name | Knob |
|---|---|---|
| 0 | `korg.knobs.LEVEL` | LEVEL |
| 1 | `korg.knobs.PAN` | PAN |
| 2 | `korg.knobs.PITCH` | PITCH / GLIDE |
| 3 | `korg.knobs.RESONANCE` | RESONANCE |
| 4 | `korg.knobs.EG_INT` | EG INT. |
| 5 | `korg.knobs.MOD_DEPTH` | MOD. DEPTH |
| 6 | `korg.knobs.ATTACK` | ATTACK |
| 7 | `korg.knobs.IFX_EDIT` | IFX EDIT |
| 8 | `korg.knobs.DECAY` | DECAY / RELEASE |
| 9 | `korg.knobs.OSC_EDIT` | OSC EDIT |
| 10 | `korg.knobs.MOD_SPEED` | MOD. SPEED |

Indices 11 to 19 belong to no knob and stay 0. CUTOFF is not a knob but an encoder.

**Encoders** (`index` of `encoder`):

| Index | Encoder |
|---|---|
| 0 | VALUE / PATTERN (the big wheel) |
| 1 | SAMPLE / OSC |
| 2 | CUTOFF |
| 3 | MOD. TYPE |
| 4 | IFX TYPE |

**Pads** (`index` of `pad`): 0 to 15 are pads 1 to 16.

The numbers come from `data/panel.mjs` (measured on the panel there).

**LEDs** (`korg.led`):

| Name | Number | LED |
|---|---|---|
| `korg.led.REC` | 18 | REC |
| `korg.led.STOP` | 19 | STOP |
| `korg.led.PLAY` | 9 | PLAY |
| `korg.led.PLAY_BLUE` | 21 | PLAY, blue LED |
| `korg.led.TAP` | 20 | TAP |
| `korg.led.GATE_ARP` | 26 | GATE ARP |
| `korg.led.TOUCH_SCALE` | 27 | TOUCH SCALE |
| `korg.led.MASTER_FX` | 28 | MASTER FX |
| `korg.led.MFX_HOLD` | 29 | MFX HOLD |
| `korg.led.EDIT_LEFT` | 5 | ◄ Edit |
| `korg.led.MENU` | 7 | MENU |
| `korg.led.SHIFT` | 10 | SHIFT |
| `korg.led.PART_LEFT` | 30 | ◄ Part |
| `korg.led.EDIT_RIGHT` | 6 | Edit ► |
| `korg.led.EXIT` | 8 | EXIT |
| `korg.led.WRITE` | 11 | WRITE |
| `korg.led.PART_RIGHT` | 31 | Part ► |
| `korg.led.PART_MUTE` | 32 | PART MUTE |
| `korg.led.PART_ERASE` | 33 | PART ERASE |
| `korg.led.LPF` | 12 | LPF |
| `korg.led.TRIGGER` | 34 | TRIGGER |
| `korg.led.HPF` | 13 | HPF |
| `korg.led.SEQUENCER` | 35 | SEQUENCER |
| `korg.led.BPF` | 14 | BPF |
| `korg.led.KEYBOARD` | 36 | KEYBOARD |
| `korg.led.CHORD` | 37 | CHORD |
| `korg.led.STEP_JUMP` | 38 | STEP JUMP |
| `korg.led.MFX_SEND` | 15 | MFX SEND |
| `korg.led.PATTERN_SET` | 39 | PATTERN SET |
| `korg.led.BAR_1` | 40 | key 1 |
| `korg.led.BAR_1_BLUE` | 22 | key 1, blue LED |
| `korg.led.BAR_2` | 41 | key 2 |
| `korg.led.BAR_2_BLUE` | 23 | key 2, blue LED |
| `korg.led.BAR_3` | 42 | key 3 |
| `korg.led.BAR_3_BLUE` | 24 | key 3, blue LED |
| `korg.led.BAR_4` | 43 | key 4 |
| `korg.led.BAR_4_BLUE` | 25 | key 4, blue LED |
| `korg.led.AMP_EG` | 16 | AMP EG |
| `korg.led.IFX_ON` | 17 | IFX ON |
| `korg.led.VALUE_PATTERN` | 0 | VALUE / PATTERN |
| `korg.led.SAMPLE_OSC` | 1 | SAMPLE / OSC |
| `korg.led.CUTOFF` | 2 | CUTOFF |
| `korg.led.MOD_TYPE` | 3 | MOD. TYPE |
| `korg.led.IFX_TYPE` | 4 | IFX TYPE |
| `korg.led.PAD_n_RED` | 44 + 2 (n - 1) | pad n, red LED (n = 1 to 16) |
| `korg.led.PAD_n_BLUE` | 45 + 2 (n - 1) | pad n, blue LED, shows the selected part (n = 1 to 16) |

The editor shows the same list below the code ("Namen der Tasten und LEDs", with a filter; a click inserts
the name at the cursor). If the cursor is in a number that looks like a key or an LED (`key == 11`,
`korg.led(20, ...)`), a line below the code says which key or LED it is, and after `korg.key.` or
`korg.led.` the editor's completion offers all names (see "The Plugins page in the editor").

### Limits

| | Limit |
|---|---|
| Variable area of one plugin | up to 65536 slots (4 bytes each), as large as declared |
| Blocks, variables and plugin entries together | 128 KiB |
| Number of plugins | no fixed limit, as long as the shared memory lasts |
| One array | 1 to 65535 slots |
| Different texts | 64, 31 characters each |
| Different numbers above 255 or negative | 256 |
| Code | 16 KiB |
| Stack (expressions) | 32 values |
| Nested calls | 8 |
| Compute budget per run | 20000 cost units |

Each plugin counts its block size (rounded up to 4 bytes), four bytes per variable slot and one plugin
entry. The entry currently takes 292 bytes. The stack, check buffers, global status and event ring lie
outside the shared pool. Plugins that were switched off keep their memory and their error state.

If the shared memory is not enough, the runtime rejects the block before creating its variables and before
running its body (message "Plugin-Budget aller Plugins reicht nicht", code `POOL_BUDGET`). Memory in use
and loaded plugins stay unchanged. The compiler only pre-checks the number of variables at their
declaration, with a default of 32768 slots (derived from 128 KiB divided by four). A block that compiled
successfully can therefore still trigger `POOL_BUDGET` on load. The 65536 slots and 65535 array slots are
format limits for the checker and the VM, not a promise that areas that large fit into the pool on the
device.

The pool lies in the free FF area of the image, from `0xC01D7000` to `0xC01F7000` (131072 bytes). Measured
offline on our own images: the area is FF there. That proves a free area in the image, not that the device
never uses it ([measurement](messungen/2026-10-14-skript-haken.md), German). The block of Blechy lies outside it,
at `0xC0184000` (12668 bytes), in the FF run `0xC01720B0` to `0xC01A0000` that also holds the pattern switch
and the loading bar; nothing is checked on the device there yet. Memory layout of the area and
cost of the block format 2 (16-bit operands, roughly 9 percent more ARM instructions per operation,
derived and not measured): [German page](plugins.md#format-2-und-die-kosten).

### When something goes wrong

The block is checked before loading: jump targets, constants, variables, calls, stack height, call depth
and the functions allowed in each event. At run time the VM ends a plugin on an endless loop (compute
budget or time), an array index outside the array, division by zero and an argument outside its range.
The plugin is then off, the message names plugin, line and kind of error, and other plugins keep running.
The error codes are in `data/script/contract.mjs`.

## The card and the file format

### Files for the card

Plugins reach the device only through the SD card, never inside the VSB. The folder is
`KORG/blechtribe/Plugin/` (singular, not "Plugins"; the same on the red and the blue Electribe), which the
firmware does not create itself. You create it. With the device connected, the Plugins page also writes a
plugin there over USB (button "Aufs Gerät", BLECH SysEx command `0x67` PLUGIN BEGIN, a name of letters,
digits, `_` and `-`, at most 16 characters); then on the device BLECH, PLUGINS, MANAGE PLUGINS.

- `e2sPlugin.all` is the collection file that the device reads at start. Header, 16 bytes, little endian:
  the tag `GSAL`, file version 1 (u16), number of blocks (u16), total size (u32), CRC-32 over everything
  from byte 16 (u32). Then the blocks in format 2, unchanged, one after the other (each has its own size and
  CRC; a block size is divisible by 4, there is no padding). One block may have at most 32752 bytes (the
  loader's buffer).
- `<name>.blech` is one block with a description and the source text attached: after the block the tag
  `GDSC`, the length (u32) and the description in ASCII, lines of at most 20 characters ending in `\n` (at most
  2047 bytes); then the tag `GSRC`, the length (u32) and the text in UTF-8. The description is the `//` lines at
  the very top of the plugin code (an empty `//` line starts a new paragraph, umlauts become ae, oe, ue, ss);
  without such lines there is no `GDSC`. The device loads the block and shows the description on the plugin's page DESCRIPTION,
  the editor reads the source to open the plugin again.

The loader runs once at start, right after the device has loaded `e2sSample.all`. With EXIT held at
power-on, without a card or without the file it does nothing, and the Electribe starts as it would without
it. A file with a wrong header, wrong checksum or truncated content is rejected as a whole. A single block
that does not load (checksum, budget, invalid code) is skipped, the others run. Then the body (`start`) of
every loaded plugin runs, and the runtime is armed; `ready` arrives with the first frame after the main
screen. What the loader did is in the runtime's control block (`cardStatus`, `cardLoaded`, `cardRejected`,
`cardFirstError`).

The editor writes the files (`src/script/archive.mjs`). A plugin that only lies on the card runs at the next
start; in MANAGE PLUGINS on the device (see below) it is listed as OFF and runs as soon as it is switched on there.

**The "probed" flag.** The header of a block has a `flags` field (byte 34, u16). Bit 0 is PROBED: the editor
sets it on export, after it has tried the text out (`markProbed` in `src/script/blob.mjs`, the checksum is
recomputed). All other bits are forbidden, and browser and device reject the block if one is set. A block
without the bit is foreign: the device loads it but starts it only after someone has agreed on the device
once (see "The BLECH menu on the device"). The bit is a hint, not protection, anyone can set it.

**Picture files** (`korg.file.frame`): `KORG/blechtribe/Gif/GIF00.E2G` to `GIF99.E2G`, little endian: tag `GGIF`,
version 1 (u16), number of frames (u16), then per frame its delay in ms (u16), two zero bytes and 1024 bytes of display
memory (byte `(y / 8) * 128 + x`, bit `y % 8`). `tools/gif/gif2e2g.py` makes one from a GIF (Pillow), `src/script/gif.mjs`
reads it in the browser. A call opens the file, seeks to the frame, reads it and closes the file again, through the
firmware's FatFs functions (also `f_lseek`, `0xC009E404`, on blue `0xC008AF5C`) with the card loader's file object. It
reads only while the main screen is open. How long 1 KiB takes on the device is not
measured; the 5 ms of a frame stay the limit.

### Persistent values

Each plugin has 16 whole numbers as persistent slots, kept apart by plugin name. `korg.store.get` reads a
slot (in the body, before all handlers, the stored values are already there), `korg.store.set` changes it
in RAM. Only what `korg.store.save()` requests goes to the card; the runtime never writes on its own, not
even at power-off. A plugin that uses the functions carries API version 2 in its block; a plugin without
them stays at version 1.

The values live in `KORG/blechtribe/Plugin/store.a.bin` and `store.b.bin`. They take turns: each write puts
the next generation into the other file. At start the newer valid one counts; a damaged or missing file
falls back to the other, and without a file the defaults of `get` apply. File layout: 16 bytes of header,
then 84 bytes per plugin (name, mask of used slots, 16 values), at most 194 entries; entries of plugins
that are not on the card at the moment are kept when writing ([German page](plugins.md#dauerhafte-werte)).

Writing happens at the earliest 50 frames (2 seconds) after the last write and only while the main screen
or the BLECH menu is open (where the pages of `korg.menu.add` are); another `save()` before that stays queued. A failure (no card, card full) is counted in the control
block (`storeErrors`) and is not repeated on its own. When running in the browser, the values last until the
page is reloaded.

## The BLECH menu on the device

With the BLECH patch the Electribe has a screen of its own, "BLECH", at the end of the EDIT ring
after Event (screen 0x2D). It has three levels and looks like Data Util: same font, same places, the same
line `press  [ Enter ]`.

- **In the ring** BLECH is a single page ("BLECH 31/32") after Event, followed as the last page by
  [Blechy](#blechy-the-last-page-of-the-ring) (32/32), then the Pattern menu again. A third page of the patch sits in the
  middle of the ring: SYNC GROUP (16/32, a setting of the pattern, see below) right behind CHAIN REPEAT, the last page of
  the Pattern menu, and before the first page of the Part menu, which now starts at 17. That is why the ring counts to 32
  instead of 29; on the blue one to 31 instead of 28 (SYNC GROUP 16/31, BLECH 30/31, Blechy 31/31, the blue one has no
  Sample menu). EDIT left and right page through the ring. With EXIT held at power-on the screen is not there and the
  ring is the firmware's own.
- **In GLOBAL PARAMETERS** the page PLUGIN RUNTIME ("Global 21/21") follows the firmware's last page (XY CALIBRATION);
  **in DATA UTILITY** EXPORT ALL CUSTOMIZATIONS, EXPORT ALL PLUGINS, EXPORT ALL EFFECTS and SET INIT PATTERN follow the
  last function (SOFTWARE UPDATE) ("Data Util 15/18" to "18/18"; on the blue one, which has 11 functions and no collection
  file, without EXPORT ALL EFFECTS: 12/14 to 14/14). They look like the firmware's pages and
  belong to the BLECH screen: EDIT pages between them and the firmware's pages both ways, EXIT goes where it goes from the
  firmware's pages (Global, Data Util), and the firmware's counters count them. Adding pages inside the firmware's menus
  would mean changing their tables and state machines; this way both stay untouched (decided on 29 October).
- **ENTER on the page BLECH** opens the list on the group last left, also after a trip through the other
  menus.
- **ENTER**, the MENU key, opens the list of groups. The tag at the top left says BLECH, the counter counts
  only the groups ("BLECH 2/3", up to 5 with apps), and EDIT pages through them in a circle.
- **ENTER on a group** shows its pages. The tag names the group ("Plugins 3/5"), the counter counts only its
  pages, EDIT pages through them in a circle, the main dial changes the value, WRITE executes or saves.
- **EXIT** always goes one level back (page of a group, list of groups, ring) and from the ring page to the
  main screen. MENU on the main screen returns to where you left the menu, also into a group.
- While the screen is open, plugins see no inputs, so that a plugin that catches keys cannot lock the menu.

The list of the first level holds groups, in this order: the built-in switches first, then the
plugins, then the customization, then the groups that plugins register themselves (`korg.app`), and as the last
page VERSION, which is no group:

| Entry | What is behind it |
|---|---|
| FEATURES | the switches of the built-in functions: MFX 2, PATTERN CONFIRM, TAP MOTION, NOTE ASSIST and, where the set has the patch last-pattern, LAST PATTERN, and where it has the patch stereo-pad (red), STEREO 1 PAD (table below) |
| PLUGINS | one page, MANAGE PLUGINS; see below |
| CUSTOMIZATION | DISPLAY, LED, then PAD COLOR, POWER SAVE and SPLASH where the set has them; see below |
| GAMES | one page per app; appears only if a plugin has registered an app in the group |
| TOOLS | like GAMES |
| VERSION | no group: on top the version of the set the firmware was patched with (`BLECH 1.3.7`, from the patch `blech-version`), below it the firmware the menu is built for (HACKTRIBE, KORG RED, KORG BLUE). ENTER, WRITE and the dial change nothing |

The pages of FEATURES (the tag names the group "Feature"), each with the value ON or OFF, the main dial changes it:

| Page | Value |
|---|---|
| MFX 2 | ON, OFF: MFX 2 on TOUCH SCALE, applies from the next start (the value then shows "ON, RESTART") |
| PATTERN CONFIRM | ON, OFF (see below) |
| TAP MOTION | OFF, ON, ONCE (see below) |
| NOTE ASSIST | ON, OFF (see below) |
| LAST PATTERN | ON, OFF (see below) |
| STEREO 1 PAD | ON, OFF (see below, red only) |

There is no ABOUT group any more: it only showed the number of loaded plugins and confused people.

The pages of the groups:

| Group, page | Value | Effect |
|---|---|---|
| GLOBAL PARAMETERS, PLUGIN RUNTIME | ON, OFF | the plugins of the card on or off, applies from the next start ("OFF, RESTART" shows that it does not apply yet); Blechy is no plugin of the card and stays. Page 21/21 of GLOBAL PARAMETERS, WRITE saves the settings of the BLECH menu |
| PLUGINS, MANAGE PLUGINS | `press  [ Enter ]`, "No Plugin" after ENTER when there is nothing to show | ENTER reads the folder `KORG/blechtribe/Plugin/` (up to 64 plugin files; with more, the page LIST FULL with "64 files shown" follows the last plugin, [measurement](messungen/2026-10-30-plugin-liste-64-entfernen.md)) and opens the list of all plugins, one page per plugin (the tag stays "Plugins", the counter counts them, EDIT pages through them in a circle like every other menu), on the plugin shown last; EXIT leads back to MANAGE PLUGINS. The loaded plugins come first, then those of the `*.blech` files that are not loaded, each plugin once (the same name in the file's header and in the loaded block means: the same plugin). A plugin that is only in `e2sPlugin.all` and has no file is listed as loaded and has no description. Parts of the firmware (Blechy and what BLECH brings itself) are no plugins and are never listed here, their switches are under FEATURES |
| a plugin of the list | its name on top, under it ON, OFF, `DIV_ZERO L3`, WRITE=ALLOW | the main dial switches it: down pauses it, up resumes it; WRITE keeps the state over a restart (a plugin switched off does not start then, switched on it runs its start); on an error the error shows with its line; a foreign plugin waits with WRITE=ALLOW for approval (only WRITE allows it, the dial does not). A plugin that is not loaded shows OFF like one switched off: the main dial up loads it from its file and starts it (a foreign one then waits for WRITE=ALLOW, a broken block reports "rejected", with the plugins of the runtime off "runtime off"), down does nothing. A plugin loaded like this runs until power-off; it stays over restarts only with EXPORT ALL PLUGINS, which puts it into `e2sPlugin.all`. ENTER opens the plugin's pages: DESCRIPTION, its own pages, OFF and REMOVE (one that is not loaded has DESCRIPTION and REMOVE); EXIT leads back to the plugin in the list |
| Plugin, DESCRIPTION | the plugin's state under the description | the description from the plugin's `*.blech` file (the `//` lines at the very top of the code), as a picture over the whole screen: the name on top, the lines below, the state at the bottom. The main dial scrolls line by line, `^` and `v` show that there is more; ENTER does nothing here. Without a file or without a description it says "no description" |
| Plugin, one page per `korg.menu.add` | the number | the settings of this plugin: the main dial changes it, the plugin gets `menu` |
| Plugin, OFF | `press  [ Enter ]` | ENTER asks ("Enter = off"), a second ENTER takes it out: the plugin stops, `e2sPlugin.all` is written again without it (also empty when it was the last one), MANAGE PLUGINS reports "off, file kept"; the `*.blech` in the folder stays, and the plugin is listed as OFF at the next ENTER on MANAGE PLUGINS and can be loaded |
| Plugin, REMOVE | `press  [ Enter ]` | ENTER asks ("Enter = remove"), a second ENTER does what OFF does and then deletes the plugin's `*.blech` from the card (the firmware's `f_unlink`): it is no longer listed, MANAGE PLUGINS reports "removed". For a plugin that is only a file only the file is deleted, for one only in `e2sPlugin.all` only that file is written again. The blue Electribe has no `f_unlink`: there the file stays and MANAGE PLUGINS reports "file stays on card". When the folder changed since the list was opened, nothing is deleted ("folder changed") ([measurement](messungen/2026-10-30-plugin-liste-64-entfernen.md)) |
| DATA UTILITY, EXPORT ALL CUSTOMIZATIONS | (empty, `press  [ Enter ]`; the title reads "EXPORT ALL CUSTOM", the whole name does not fit the row) | ENTER or WRITE writes the customization as `KORG/blechtribe/e2sCustom.all`: the same record as the settings file, without the list of plugin checksums, and reports "exported". Nothing reads this file at start yet; copied over `settings.a.bin` the settings loader reads it and the customization is back |
| DATA UTILITY, EXPORT ALL EFFECTS | (empty, `press  [ Enter ]`) | ENTER or WRITE writes the presets and modulation types as the firmware holds them in RAM now back into the collection `KORG/blechtribe/Presets/e2sFx.all` (IFX, MFX and modulation from the Baukasten): every entry stays in its place with its `.e2fx` text, which the editor reads back; an entry without text stays as it is; the checksum is made new. Only the file loaded at power-on: "no e2sFx.all" without a loaded file, "bad e2sFx.all" when it is another one since, and then nothing is written. Red only (the blue one has no collection file) |
| DATA UTILITY, EXPORT ALL PLUGINS | (empty, `press  [ Enter ]`) | ENTER or WRITE writes all loaded plugins as `e2sPlugin.all`, byte for byte as the browser packs them, then saves the settings too (plugins switched off stay off) |
| GAMES or TOOLS, one app per page | ENTER=OPEN | ENTER or WRITE opens the app ("Apps and the display"); if the plugin is OFF or has failed, the value shows OFF or FAULT |
| CUSTOMIZATION, DISPLAY | ENTER | opens the pages of the display light; EXIT goes back to DISPLAY |
| DISPLAY, BACKLIGHT HUE, SAT, BRIGHT | HUE 0 to 95, SAT and BRIGHT 0 to 15 | colour of the display light: HUE goes once round the colour wheel (16 steps to each of red, yellow, green, cyan, blue, magenta and the way between), SAT is the saturation, BRIGHT the brightness; what is stored stays red, green, blue at 0 to 15 each, so an older file reads as before; with nothing set it shows STOCK (the firmware's white), full brightness without saturation is STOCK again; a step that would give the same colour jumps to the next one that changes it; applies at once; after WRITE the display lights in the channels of the colour at power-on, on the red unit before the start image, on the blue one shortly after it appears, the steps in between once the menu has loaded ([measurement](messungen/2026-10-29-hintergrundlicht-beim-start.md)) |
| DISPLAY, INTENSITY | 0 to 15 | brightness of the display light over all three colours, the mix stays; 0 is no light, 15 the full colour; applies at once |
| DISPLAY, DISPLAY INVERT | OFF, ON | inverts the display: light dots dark and dark dots light (command `0xA7` to the display chip, `0xA6` restores); applies at once; ON is the default (a light trail on a dark screen smears less than a dark one), a settings file from 1.2 without it keeps OFF |
| CUSTOMIZATION, POWER SAVE | ENTER | opens the pages for power save (on battery only); EXIT goes back to POWER SAVE |
| POWER SAVE, DISPLAY LIGHT | STOCK, 1 to 15 | the display light in power save: STOCK is the firmware's dimming, 1 to 15 the own colour, 1 lights at 3 of 15, 15 full |
| POWER SAVE, LED DIMMING | 0 to 100 % | how much power save dims the pad, key and knob LEDs: 0 % not at all, 100 % off, 75 % (the default) a quarter of the brightness; the knob LEDs go out except at 0 %; applies at once, WRITE keeps it |
| CUSTOMIZATION, LED | ENTER | opens the pages of the lower LEDs; EXIT goes back to LED |
| LED, BOTTOM LEDS | METER, COLOR, OFF | the four lower RGB LEDs: METER is the level meter, COLOR a fixed colour, OFF dark; applies at once |
| LED, LED HUE, SAT, BRIGHT | HUE 0 to 95, SAT and BRIGHT 0 to 15 | colour of the lower LEDs for COLOR, set like the display light; with METER the level sets the brightness of this colour while no meter colour is set; STOCK means the firmware's colours; applies at once |
| LED, METER STILL, LOW, MID, LOUD | STOCK, WHITE, RED, GREEN, BLUE, YELLOW, CYAN, PINK (STILL and LOUD: RAINBOW, STILL also OFF) | the colour of the level meter per zone, split as in the firmware: STILL without level, LOW, MID, LOUD; STOCK is the firmware's colour (white, blue, green, red); STILL and LOUD also have RAINBOW, the colour turns smoothly through red, green and blue: STILL once round in about 3.5 s, LOUD once a bar at the tempo of the pattern (about 1.9 s at 128 BPM); STILL OFF keeps the still meter dark |
| CUSTOMIZATION, PAD COLOR | ENTER | opens the pages of the pad colours; only where the set has the patch pad-colors |
| PAD COLOR, PAD COLOR | RED, BLUE, PINK | the colour the pads use for what the firmware shows in red (a part plays, a pad is held, a step); applies at once, WRITE keeps it; RED is the default. Only where the set has the patch pad-colors In SEQUENCER mode a step that holds on the note of the step before it through TIE shows a tail in pink that fades out over the length of the note; where tied notes overlap their brightness adds up. |
| PAD COLOR, SELECT COLOR | RED, BLUE, PINK | the colour of the selected part, never the one of PAD COLOR; when both light, the pad shows the third colour; BLUE is the default |
| PAD COLOR, OVERLAP | AUTO, RED, BLUE, PINK | the colour of a pad that is lit and selected at once; AUTO is the third colour, neither PAD COLOR nor SELECT COLOR |
| CUSTOMIZATION, SPLASH | ENTER | opens the three pages of the start image; EXIT goes back to SPLASH. Only where the set has the splash editor |
| SPLASH, SPLASH IMPORT | ENTER | reads `KORG/blechtribe/splash.bmp` (128 x 64 pixels, 1 bit per pixel, not compressed; the darker colour is drawn) and stores it as the start image like WRITE in the splash editor; shown from the next start. Says "loaded", "no splash.bmp" or "not 128x64 1 bit" (then nothing changes). Only where the set has the splash editor, so not on the blue one |
| SPLASH, SPLASH DRAW | ENTER | opens the splash editor (a page of the Global screen that only this page reaches): the dial moves the cursor left and right, with SHIFT held up and down, MENU flips the pixel and, held, paints its new colour wherever the cursor goes, WRITE saves, EXIT leaves the editor. Only where the set has the splash editor |
| SPLASH, SPLASH RESET | ENTER | drops the stored start image (import or editor); from now on and at every later start the firmware's own start image comes back, the page says "original back". Only where the set has the splash editor |
| FEATURES, PATTERN CONFIRM | ON, OFF | ON: a pattern chosen with the dial while playing waits for MENU (ENTER) and starts at the end of the sequence; OFF: the firmware as without the pattern switch patch; applies at once, ON is the default (also without a file); OFF is bit 2 of the flags in the settings file The MENU key shows where to press: it blinks while a pattern is only viewed (VIEW:, also stopped with unsaved changes) and is lit once it is confirmed (NEXT:), up to the switch; then it is as the firmware had it. While a pattern is viewed or confirmed, the pads and, after EDIT, the info texts (OSC, Pitch and so on) show that pattern ([measurement](messungen/2026-10-25-pattern-ansicht.md)). The pads then belong to that pattern and have their own colour: PART MUTE switches its mutes, which it takes along at the switch, and the playing pattern cannot be switched with the pads ([measurement](messungen/2026-10-29-vorschau-pads.md)). |
| Ring, SYNC GROUP | OFF, 1 to 999 | a page of its own in the ring (16/32), right behind CHAIN REPEAT, the last page of the Pattern menu, and before the Part menu (EDIT right from there, EDIT left from the first page of the Part menu; the tag says "Pattern"), on both Electribes (on the blue one since 24.10., [measurement](messungen/2026-10-24-blau-sync-group.md)): the sync group of the pattern in RAM; the main dial changes it, WRITE opens the pattern write as on the Pattern menu's pages, it is saved with the pattern. While a pattern plays, another pattern of the same group chosen with the dial starts at the end of the sequence without MENU (NEXT: below), one outside the group waits for MENU as always; stopped, the dial loads a pattern of the group at once even when the pattern has unsaved changes ([measurement](messungen/2026-10-25-sync-ungespeichert.md)); switching between two patterns of one group carries the state of the pattern that played, changed or not: part mutes and part sound (sample, filter, modulation, pitch, amp, IFX and the other part values), tempo, swing, level, the MFX pad with HOLD, also back; the effect types MFX 1 and MFX 2 stay the new pattern's; the patterns of a group play as one (in RAM only). Steps, motion, length, beat, key, scale and chord set stay the new pattern's. OFF (0) is no group, nothing carried |
| Pattern menu, BEAT | 16, 32, 8 Tri, 16 Tri, 8 | the fifth value `8` makes every step an eighth note: the pattern runs twice as long, at 160 BPM like BEAT 16 at 80 BPM, MIDI clock and the TAP LED stay at the real tempo, with an external clock 12 pulses per step; it is saved with the pattern; Gate Arp, export and slices follow the step; on Korg's firmware without BLECH such a pattern runs one step every 2 ms; red and blue ([measurement](messungen/2026-10-29-beat-achtel.md)) |
| FEATURES, TAP MOTION | OFF, ON, ONCE | ON: TAP switches the recorded motion sequence of the selected part on and off, TAP held longer than 0.3 s switches only while held and back on letting go; ONCE: a motion TAP switched on plays to the end of the pattern and goes off; OFF: TAP is the firmware's tap tempo again; applies at once, ON is the default (also without a file); OFF is bit 3, ONCE bit 5 of the flags in the settings file (bit 3 wins) |
| FEATURES, NOTE ASSIST | ON, OFF | ON: in KEYBOARD mode the pads of the notes that fit light up faintly pink after a note, the better they fit the brighter (unison and fifth, then thirds, fourth and a step of the scale, then sixths); stopped or paused they stay, while the pattern plays they fade, the dim ones first; in CHORD mode (scales of seven notes) the pads show the same way which chords follow well; OFF: the pads as in the firmware; applies at once, ON is the default (also without a file); OFF is bit 4 of the flags in the settings file |
| FEATURES, LAST PATTERN | ON, OFF | ON: at power-on the Electribe opens the pattern that was selected before switching off; OFF: it starts with 001 as in the firmware, the kept number stays for a start with ON; applies from the next power-on, WRITE keeps it (bit 3 of byte 5 of the settings file means OFF); without a file ON; EXIT at power-on: 001; red and blue, where the set has the patch last-pattern |
| FEATURES, STEREO 1 PAD | ON, OFF | ON: a stereo sample takes only its own pad and plays there on one voice, the pad next to it plays its own sample; OFF: as in the firmware, a stereo sample on pad 1, 3, ... also takes the next pad; applies at once, WRITE keeps it (bit 2 of byte 5 of the settings file means OFF); ON without a file; EXIT held at power-on: as in the firmware; only where the set has the patch stereo-pad (red) ([measurement](messungen/2026-10-29-stereo-ein-pad.md)) |
| DATA UTILITY, SET INIT PATTERN | FACTORY, 1 to 250 | the pattern DATA UTILITY > INITIALIZE PATTERN takes as its template; FACTORY is the firmware's template; applies at once and stays after switching off (Global byte 247, no WRITE needed); only where the set has the patch init-pattern (red) ([measurement](messungen/2026-10-28-init-pattern.md)) |

Feedback ("saved", "no card", "imported", "2 exported" and so on) replaces the value of the page until you
turn the main dial or change the page. The firmware's third line (the unit behind a value) starts in
column 28 of the value line on every screen, so any value wider than one or two characters runs into it.
The menu therefore never uses it. What a page says goes into the value, which holds about 14 characters;
the title holds about 18.

On the page PLUGIN RUNTIME, the pages of FEATURES, the pages of CUSTOMIZATION, and for the approval of foreign plugins, WRITE saves the
settings to `KORG/blechtribe/settings.a.bin` and `settings.b.bin`, which take turns with a generation
number (24 to 280 bytes, tag `GSET`, version 3, then a byte with METER LOUD RAINBOW in bit 0, which a BLECH before 1.3 rejects; at most 64 entries (version 2 up to 1.3.7 held at most 16; a BLECH up to 1.3.7 does not read version 3, it takes an older version 2 file still on the card or the defaults); files of version 2 and 1 are still read and written as version 3 at the next WRITE; the same list holds the inverted checksum of every plugin switched off, which an older BLECH reads as a checksum that never matches; when the list is full, the oldest entry that belongs to no loaded plugin drops out first (a plugin no longer on the card, or an older build of one), otherwise an approval drops the oldest entry of all; a marker that finds no room is missing and the plugin runs again after a restart).
Without a file, without a card or with a damaged file the defaults apply (everything on, customization at
the firmware's values). The page reports "saved", "no card", "card protected", "folder missing" or "write
error". Nothing is written to the flash.

**Customization:** what is visible on the device applies as soon as you turn the dial, so the menu is the
preview; only WRITE remembers it for the next start. The firmware keeps its own switches: Power Save (lower
LEDs off, display light dimmed) stays as the firmware does it, a plugin that holds the LEDs (`korg.ledHold`)
keeps them, and with EXIT held at power-on everything is as in the original. The firmware's colours are the
default (all levels 0). Measurements and limits: [customization](messungen/2026-10-14-blech-anpassung.md)
(German).

The splash screen switch is missing on purpose: the splash screen is drawn for about 290 ms before the card
is readable, so a setting from the card can no longer change it.

## Blechy, the last page of the ring

Blechy, the run-down nose creature, is no plugin. He is built into BLECH and has the **last page of the
firmware's EDIT ring**: after Event and BLECH, before the Pattern menu ("32/32"; on the blue one
"31/31"). From the Pattern menu you reach him with EDIT left on its first page. On the page he stands there at once, live: no submenu, no `press  [ Enter ]`,
the whole display is his (the page number is not visible).

- **Like any page of the ring:** EDIT left goes to BLECH, EDIT right to the Pattern menu, EXIT to the main
  screen. The main dial, MENU and WRITE change nothing on his page (the main dial does not page through the
  firmware's own ring pages either). Measured in the emulator ([measurement](messungen/2026-10-15-blechy.md),
  German).
- **He waves.** When you land on the page he stands there. About a second later he waves once: the hand swings
  back and forth every 220 ms for 1.76 s (four full swings), then he stands again. Once per landing: page away and
  back and he greets you again. The second is a choice, not a measurement on the device: short enough to read as
  a greeting, long enough that he is not already in mid-motion when the screen changes and you see him as a
  standing picture first. If you tap him during the wait, the anger comes first and the greeting after it. The two
  wave pictures (`blechy-wave-1.png`, `blechy-wave-2.png`) are derived from the calm pose, only the right arm and
  the hand differ (`tools/art/make_blechy.py`).
- **He walks.** After the wave he walks slowly across the display, one pixel every 120 ms (about 10 s from one edge to the
  other) and back, with the walking picture (`blechy-walk.png`); he stands for a second at each edge and turns round. While
  walking he sinks one row every two pixels, the one walking picture allows no more of a step. Where he stands, a tap
  (angry) and stroking (happy) work too, and he walks on afterwards.
- **He talks.** Now and then, when he has reached an edge, he stops for 3.5 s and says something in a speech bubble, on the side
  that has room: at the left edge to his right, at the right edge to his left. The first bubble comes after a little over
  12 s, then every 20 s or 30 s (8 s plus 0 to 8 s of chance after the last, plus the walk to the next edge). The lines come in
  turn: "yo, na du?", the favourite tempo (the most played one, counted per beat; until something was played, the fixed line
  "mein Tempo ist 150 bpm"), how long it has been going ("Spielt seit n min" since the first PLAY, otherwise "Läuft seit"
  since power-on, seconds under a minute), "Blech ist mein Ding", "bisschen mehr Bass?", "nicht so doll
  tippen", "Schranz ist Liebe". All in the own font (5 by 7, ASCII and ä, ö, ü). The waits, the walking speed
  and the texts are a choice, not tried on the device.
- **PLAY.** When you press PLAY he walks briskly (two pixels every 70 ms) to the middle, a little left of it so that there is room
  beside him for the bubble, says "ich hör mir das kurz an" (2.8 s), stands a moment and then dances as long as the pattern
  plays, one picture per eighth. The wait of 12 s before the dance is gone. STOP ends the dance and he walks again; the question
  "wat machst'n du da atze?" is gone, it only fitted the main screen.
- **Otherwise as before:** a tap on the touchpad near him makes him angry, stroking makes him happy. The numbers (tempo, play
  time) live in RAM only and start again with every start.
- **No plugin of the card:** he is neither under GAMES nor under PLUGINS, not counted, not written by EXPORT ALL PLUGINS,
  and cannot be switched off. He needs no card and no `e2sPlugin.all`, and runs with the setting PLUGIN RUNTIME on OFF too.
  With EXIT held at power-on he is absent (and the page with him): the ring is the firmware's own.
- **Inputs:** on his page the plugins of the card see only the touchpad (the key and the position), everything else
  goes to the firmware alone, and a plugin cannot catch a key there: EDIT and EXIT always work.
- **Built in means:** his block (15476 bytes, an ordinary API 6 plugin block, compiled by the editor and checked in
  the browser, `tools/blechy-build.mjs`) lies in the firmware image at `0xC0184000` and stays there. The loader
  puts only his entry and his variables into the pool (15904 bytes of 128 KiB), not the block. At start BLECH loads
  him before the card, registers him as a hidden app (entry 0 of the table, in a group no menu lists) and runs his
  body. Opening and closing follow the page: as soon as the firmware shows it he gets `open` and the display, when
  it shows anything else, `close`. The source stays `data/script/blechy-source.mjs`, even though he is no example
  plugin any more. The start costs about 5.4 million instructions (counted in the emulator; on the device an
  estimated few tens of milliseconds), 70 % of it the byte-wise zeroing of the runtime and the check tables
  (`mem_fill`), 8 % the checksum of the block.

## The example plugins

All nine apps are in the catalog of the Plugins page and in `data/script/presets.mjs`. They have run in the emulator of
the plugin runtime (browser VM), nothing of them is checked on the device. `test/script-plugins.test.mjs` plays each one
with input. The cost is the most expensive handler in cost units, counted in a run with input; the time next to it is
**derived**: the Snake frame with 542 units took 0.103 ms in the emulator, so the 0.5 ms warning line is about 2630
units. Every app stays below it, the tests check that. On the device the time per unit may differ.

| App | Group | Controls | Block | Most expensive handler |
|---|---|---|---|---|
| BLECH Clicker | GAMES | every pad press adds one, the crystal shakes; the count is kept with `korg.store` | 1720 bytes | 1041 units, 0.20 ms |
| Set-Timer | TOOLS | big mm:ss, h:mm:ss from one hour; key 1 starts, key 4 resets (press twice) | 1996 bytes | 2434 units, 0.46 ms (drawing the digits); 201 with no change, nothing per frame while closed |
| Snake | GAMES | Part left and right turn | 1180 bytes | 2215 units (opening), frame 537 |
| Tetris | GAMES | Part left and right move, Edit right turns, Edit left held drops faster, any key restarts after game over | 3772 bytes | 2305 units, 0.44 ms |
| Game of Life | GAMES | the touchpad sets cells, key 1 starts and pauses (LED), key 2 one step, key 3 clears, key 4 fills at random | 2184 bytes | 2484 units, 0.47 ms |
| Pong | GAMES | paddle by touchpad (height of the finger), Part left up, Part right down, encoder; first to 9 wins; ball and bot move on every second frame only, otherwise the slow display hardly shows the ball | 2120 bytes | 1221 units, 0.23 ms |
| Simon | GAMES | the 16 pads light a sequence (a step 0.72 s, a little shorter every fourth round, never below 0.4 s), you play it back, one more step each round; the display shows the round, the step and what to do; a wrong pad ends the game, TAP or a pad restarts | 2268 bytes | frame at most 1673 units (game over), opening 1644 |
| Mandelbrot | GAMES | a finger on the touchpad pans, Part right and the encoder zoom in, Part left out, keys 1 and 2 set the iterations (8 to 64), TAP resets | 2436 bytes | 2135 units, 0.41 ms |
| GIF Player | TOOLS | plays `GIF00.E2G` to `GIF99.E2G` from the card: the encoder picks the file, Part left and right halve and double the speed (25 to 400 %), TAP pauses; a missing file is said. For trying animations on the display, a frame stays at least one runtime frame (40 ms) | 972 bytes | frame 3762 units, about 0.72 ms (the picture alone 3086), above the warning line of 0.5 ms |

**Set-Timer** is meant for use in a set. Its clock is `korg.millis()`, which the runtime keeps current every frame,
also while the app is closed. It subscribes only to `play`, the keys, `open` and `close`: closed it costs a few
operations per key and nothing per frame (an app only gets `frame` while it is open), open it redraws only the digits
that changed. The first PLAY (the transport going to play) starts it, after that it just counts: PLAY and STOP change
nothing, it never calls `korg.play`, `korg.stop` or `korg.led` and does not read the pads. Keys 1 and 4 only count while
the app is open. After a reset it waits for a PLAY again, which needs a STOP before it (the event comes with the
transition). It has no storage: it does not count while switched off or set to OFF in the menu, a restart begins at 0.

**Game of Life** keeps a row of the grid (32 cells) as one 32-bit number and computes the next generation of all 32 cells
of a row at once with bit operations. The picture is caught up cell by cell, the next generation only starts when it has
caught up, so every frame stays small. **Mandelbrot** uses 14 fractional bits (1.0 is 16384), the integer arithmetic of the
VM is enough, no floats needed; the picture comes in four passes of blocks 8, 4, 2 and 1 pixel wide, and a pixel that
needs more than the rest of a frame is continued in the next one. The first pictures are up after one to three seconds,
the full picture takes about 3400 frames (a little over two minutes, counted in the emulator); every input starts again at
the coarse pass. Zoom goes up to 7, deeper than that the 14 bits do not reach.

**BPM Glide** (idea: [KrImZoR](https://www.instagram.com/krimzor_live)) is no app, it runs in the background. While
the playing pattern chains on (Chain To, CHAIN MODE on), the tempo glides from the tempo at the start to the stored tempo of
the next pattern, spread over length times Chain Repeat; the last step reaches the new tempo, so the switch does not jump.
It reads the chain at the first step after PLAY or a pattern change, because only then does the firmware have the new
pattern in RAM. STOP sets back the tempo the pattern started with. The page BPM GLIDE in the BLECH menu switches it on (1)
and off (0), `korg.store` keeps the setting. Because `korg.tempo` sets the tempo of the pattern in RAM, it counts as an
unsaved change until STOP. Checked in the simulator (`test/script-bpm-glide.test.mjs`), not on the device.

## The Plugins page in the editor

The Plugins entry has four pages: Katalog (catalog), Meine Plugins (my plugins), Editor and Dokumentation
(documentation). The title in the breadcrumb always leads back to the catalog.

**Catalog:** the plugins of the app as cards (the apps BLECH Clicker, Snake, Tetris, Game of Life, Pong, Simon
and Mandelbrot under GAMES, Set-Timer and GIF Player under TOOLS, plus Lauflicht, Pulsieren and Takt-Blinker; source
`data/script/presets.mjs`). Each card shows the plugin's display after a few frames, below it title, category,
description and maker. The whole card leads to the plugin's page: the picture top left, beside it title, description and details (category, maker, date, controls), with
download, to the device and "Als eigenes Plugin öffnen" (open as your own). Below, "Vorschau" (preview) and
"Code" switch between the plugin running on the drawing of the Electribe and its source. A new plugin enters
the catalog by pull request on GitHub, with its entry in `data/script/presets.mjs`.

**My plugins:** the plugins of this browser as cards like in the catalog, with Neues Plugin (new), Öffnen
(open) and Alle speichern (save all). A card opens the plugin in the editor.

**Editor:** the editor over the whole page, with line numbers and the result of compiling (errors with line
and column, a click puts the cursor there). Öffnen (open) and Speichern (save) sit top right in the bar; below
the editor are Vorschau, download and to the device. The preview lies over the darkened editor; a click beside
it or the X closes it. The console is an entry of its own under Gerät. Your own plugins
are kept in the browser (`localStorage`) and never leave it. A plugin name is the block name: ASCII, a
letter first, at most 15 characters.

**New plugin** ("Neues Plugin"): asks for the name and then for the kind. "App in GAMES" and "App in
TOOLS" create an app with `korg.app(name, group)`, "Hintergrund" (background) a plugin without display and
without a menu entry. The chosen name is also the name of the app in the BLECH menu. Each template is a
short, working plugin with the handlers `frame` and `buttonPress` (the apps also with `open`), names such
as `korg.key.TAP` and a few comments in German. The source is `data/script/templates.mjs`;
`test/script-templates.test.mjs` compiles every template, lets it pass the probe and checks that it
registers the name and the group.

**The editor** is CodeMirror 6 (`site/app/script-editor.mjs`). The bundle ships built in
`site/vendor/codemirror.mjs`; the page loads nothing from the network and also works offline in the app. To
rebuild it: `npm install`, then `npm run build:codemirror`. It offers:

- **Colours and line numbers:** JavaScript words, strings, numbers and comments, with `korg` and the names
  after `korg.key.` and `korg.led.` set apart. The line numbers show the probe: green ran, yellow never ran,
  red error. An example plugin is read-only: you can select and copy in it, and "Als eigenes Plugin öffnen"
  (open as own plugin) makes an editable copy.
- **Completion:** type `korg.disp` and the editor offers all functions that start so, each with its
  parameters, a sentence (in German), the allowed ranges and where it may be called. Enter inserts the call
  with its parameters as fields, Tab jumps to the next. After `korg.key.` and `korg.led.` it offers all
  names with number and label, inside `korg.onEvent("` all events with the values of their handler (Enter
  inserts the handler too), and in the second argument of `korg.app` the groups. In the object tree each dot
  offers the names that go on there: after `korg.menu.blech.` the branches below, at a leaf its range, whether
  it can be set and from which API version it exists. The timers (`korg.after`, `korg.every`,
  `korg.afterSteps`) insert an arrow `() => { }` to write into. Ctrl+Space opens the list by hand, Escape
  closes it.
- **Parameter hint and hover:** with the cursor inside a call, a hint above the cursor shows the syntax and
  the parameter you are typing, with its range. Hovering over a name, an event name or a handler value
  shows the same description; over a number that looks like a key or an LED it shows its name.
- **Errors in the text:** the compiler's error is underlined in the text (line and column), and below the
  editor it stays as a list; a click puts the cursor there. While typing this holds for the object tree too:
  a misspelt path, a leaf that cannot be set and a fixed value out of range (`...display.intensity = 300`)
  are red, with the same message as on compiling.
- **Keyboard:** Tab leaves the editor (it does not trap Tab, so nobody gets stuck in it), indent with Ctrl+]
  and Ctrl+[ (Cmd instead of Ctrl on a Mac), undo with Ctrl+Z. The editor is labelled "Plugin-Code", and the
  completion is a list that screen readers read out.

**Where the texts come from:** the functions, events and values are in `data/script/contract.mjs`, their
descriptions in `data/script/describe.mjs` (German), the names of keys and LEDs in `data/script/names.mjs`, the
object tree in `data/script/objects.mjs`.
`src/script/editor-model.mjs` turns them into completion, hint and hover. A test fails if a function or an
event of the contract has no description. A new leaf of the object tree is in the completion without more
work; a test walks every leaf dot by dot.

**Preview** ("Vorschau", `src/script/sim.mjs`): a simulated device on the reference VM with a display (128 by 64,
preview font, not the firmware's), an LED book and a millisecond clock, one frame every 40 ms. Keys, pads,
knobs, encoders and the touchpad send their events to the runtime. The display shows what the device would
show: the picture of the open app or of the plugin that took the display, otherwise nothing (on the device
the firmware's main screen is there). If the plugin has an app, the preview opens it as ENTER does in the menu;
below the display the apps are listed as in the BLECH menu ("GAMES > Snake: öffnen", that is "open"), with
an EXIT key that closes the app as on the device, before the plugin sees the key. This is not the firmware:
the preview does not show its timing (in the browser only the compute budget applies, no time limit). The
runtime inside the firmware runs in the emulator, see "Status".

**Inputs and probe:** "Eingaben aufnehmen" (record inputs) stores the inputs with their frame in the plugin.
"Proben" (probe) loads the block into a fresh simulated device, plays the recorded inputs back (at least 100
frames) and tells you which lines of code never ran. If the plugin has an app, the probe opens it first.
Without inputs only `ready`, `open` and `frame` run.

**Export:** "Als .blech speichern" (a plugin with its source) and "Alle speichern (e2sPlugin.all)" (all your
plugins) are available only after a probe of exactly this text (`src/script/gate.mjs`). Any change to the
text discards the probe. If lines remain that never ran, the page asks once and names them. An error in the
probe blocks the export.

**Console:** `run("name")` starts one of your plugins or one of the catalog in the preview. A line that
starts with `korg.` (for example `korg.display.text("Hi", 0, 0)`) runs there as plugin code at once, once,
as an app "einzeiler" in TOOLS that the preview opens. Anything else is plain JavaScript with `KORG` for the
emulator.

## Status

Markers as in the measurements: measured, derived, open.

### In the emulator

All of this ran in the real firmware (2.02 with Hacktribe) in the emulator with a virtual card, or in
Unicorn without firmware, **not on the device**.

- Compiler, checker and reference VM in JavaScript (`src/script/`), the Plugins page with run, probe and
  export, tests in `test/script-*.test.mjs`. Block format 2, API version 9.
- ARM VM (`tools/patch/script_vm.s`): all 34 opcodes, 506 comparison cases against the JS VM agree
  ([measurement](messungen/2026-10-14-skript-arm-vm.md)).
- Input filter and frame hook (`tools/patch/script_hooks.s`): ring of 64 places, 25 Hz, a shared budget of
  5 ms, an error switches off only the triggering plugin, the firmware stays usable
  ([measurement](messungen/2026-10-14-skript-haken.md)).
- `korg.led`: in the firmware run `ready` sends the zero value once, a key press sends 255 and 0, one packet
  each, all 88 LEDs at once make 88 packets ([measurement](messungen/2026-10-14-skript-led.md)).
- Display: 70 cases byte for byte equal to the browser model, the error picture too, firmware menus stay
  visible ([measurement](messungen/2026-10-14-skript-display.md)).
- Card loader: a file with two blocks loads and runs, a single broken block is skipped. A wrong checksum, a
  wrong tag, a truncated file and EXIT at power-on all leave the firmware starting as the original
  ([measurement](messungen/2026-10-14-skript-karte.md)).
- Persistent values: a counter survives power off and on through the virtual card
  ([measurement](messungen/2026-10-14-skript-speicher.md)).
- Writing steps (`tools/patch/script_seq.s`): a plugin writes steps into part 1 while the pattern plays and the sequencer
  plays them (the emulator's MIDI output: the notes in the order of the steps), the bytes in the pattern are those of the
  browser model, the pads show the written steps afterwards; not heard on the device
  ([measurement](messungen/2026-10-26-plugin-steps.md), German).
- Clock, reading, acting, sequencer events, backlight and LED hold. Finding: the firmware only knows
  toggling for mute, so `korg.mute` reads the state first
  ([measurement](messungen/2026-10-14-skript-hardware.md)).
- Snake runs as an app from the menu: 150 frames in the firmware, the display RAM afterwards is byte for
  byte equal to the browser model, `frame` takes at most 0.103 ms
  ([measurement](messungen/2026-10-14-skript-snake.md), [apps](messungen/2026-10-14-plugin-apps.md)).
- Apps and display ([measurement](messungen/2026-10-14-plugin-apps.md)): loading does not change the
  display, an app opens in the menu under GAMES or TOOLS and draws only then, EXIT closes it and the main
  screen is afterwards pixel for pixel that of a device without an app, EXIT cannot be caught (app and
  `korg.display.take()`), a plugin without the display draws nothing.
- Blechy is built into BLECH, the last page of the ring: loaded without a card in the emulator, waves after about
  a second once per landing, tapping, stroking, dancing while playing, the speech bubble at STOP, EDIT and EXIT page
  away, absent with EXIT held at power-on; the most expensive frame takes 0.28 ms
  ([measurement](messungen/2026-10-15-blechy.md)).
- BLECH menu: two levels with groups, counter and tag per group, EXIT goes one level back, WRITE, MENU as
  ENTER, settings, plugin pages, apps, EXPORT ALL PLUGINS and SET INIT PATTERN in DATA UTILITY, PLUGIN RUNTIME in GLOBAL
  PARAMETERS, SYNC GROUP behind CHAIN REPEAT, the list in MANAGE PLUGINS, foreign plugins, `korg.menu.add`; every
  page is drawn without a third line, and one case checks all of them for overlap
  ([measurement](messungen/2026-10-14-blech-menue.md)).
- Firmware file: the patch set `data/patches/blech.json` (start image editor, MFX 2, plugin runtime with
  menu, card folder `blechtribe`, BLECH start image) is built and checked in the emulator
  ([device file](geraetetests/blech-datei.md), German).

### On the device

The firmware file with the runtime runs on the own device. The BLECH menu, loading from PLUGIN EDIT, EXPORT ALL (named so
and under PLUGINS up to 1.3.7, since 1.3.8 MANAGE PLUGINS and EXPORT ALL PLUGINS in DATA UTILITY; the new layout has not been
used on the device yet) and
`korg.store` read and wrote files on the card there (`e2sPlugin.all`, `store.a.bin`, `store.b.bin`); the
customization, the FEATURES pages and SPLASH IMPORT and DRAW were used on the device. The wishes from
these tests are in the measurements from 18 October on
([plugin stays off](messungen/2026-10-18-plugin-bleibt-aus.md),
[import list](messungen/2026-10-19-plugin-import-liste.md),
[sync and menus](messungen/2026-10-22-sync-und-menues.md), German). What a measurement only played in the
emulator, it says itself. Step lists for an own test: [card test](geraetetests/karte.md) and
[firmware file](geraetetests/blech-datei.md) (German).

### Open

- **Not measured on its own on the device:** the time per frame against the 5 ms budget (derived: about
  0.17 ms for a Snake frame), a listening test for dropouts with music and Snake, the backlight on battery
  with Power Save "Auto", the LED hold.
- **Timer3:** the period of one second is measured in the emulator, not read on the device.
- **`save` hook:** hooked in the emulator but not triggered there (WRITE in Global writes flash). Its effect
  is tested only in a unit test.
- **Card:** a write on a real card can take longer than a frame; this is not measured. Only the open main
  screen protects against simultaneous card access by the firmware. What the firmware does when
  `KORG/blechtribe/` is missing on the card was not played in the emulator.
- **A real `e2sSample.all`:** the card loader is not tested with a real file, because no Korg data may live
  in the repository. The hook sits at the place that an earlier prototype measured with a real file
  ([research on the virtual SD](hintergrund/virtuelle-sd.md), German).
- **LEDs:** the limit of 400 packets a second holds only at about 25 Hz frame calls, an index that is
  rejected for good blocks the other LEDs without a message, and disabling interrupts presupposes a
  privileged mode ([measurement](messungen/2026-10-14-skript-led.md)).
- **Menu:** no switch for the splash screen, long names are cut off, the list of MANAGE PLUGINS shows at
  most 64 plugin files and says so with LIST FULL when there are more ([measurement](messungen/2026-10-14-blech-menue.md),
  [64 files](messungen/2026-10-30-plugin-liste-64-entfernen.md)); how long opening it with many files takes on the device is untested (0.9 s for 64 in the emulator).
- **Pages in GLOBAL PARAMETERS and DATA UTILITY:** they are pages of the BLECH screen that EDIT reaches at the edges of
  the firmware's pages (hooks on the EDIT left and right slots of screens 9 and 15). DATA UTILITY's function list itself is
  a state machine with a jump table of 40 states in a single function (`0xC0061A24`); pages inside it would be states of
  their own, a job of its own ([measurement](messungen/2026-10-14-blech-menue.md), section "DATA UTILITY").
  Nothing reads the `e2sCustom.all` of EXPORT ALL CUSTOMIZATIONS at start yet; there is no loader for it.
- **Apps on the device:** opening and closing, the redraw of the main screen and the keys of the open app
  were played only in the emulator.
- **Format 2:** the extra cost of the 16-bit operands is derived, not measured separately.

### Source code

In the source and in the tests the whole thing is still called `script`: `src/script/`, `data/script/`,
`site/app/scripts.mjs`, `tools/patch/script_*.s`. `korg.*` is the interface. Measurements carry `skript` in
the file name (`docs/messungen/2026-10-14-skript-*.md`). On the device, in the editor and in the docs it
is called plugin.
