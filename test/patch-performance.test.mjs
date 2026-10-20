import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { emuPython } from "./support/emu.mjs";

const python = emuPython();
const snippet = `import sys,json;sys.path.insert(0,'tools/emu');from patch_performance import validate_capture,compare; x=json.load(sys.stdin);validate_capture(x['baseline']);validate_capture(x['candidate']);print(json.dumps(compare(x['baseline'],x['candidate'],x.get('phase','baseline'))))`;
const loaderRun = () => ({ totalInstructions: 1000, plugins: Array.from({ length: 10 }, (_, i) => ({ plugin: `plugin${i}`, instructions: 100 })) });
const sample = () => ({ format: "blech-performance", version: 2, method: "fixture", repeats: 3, seconds: 2,
  appProtocol: { warmupFrames: 8, rngSeed: 0xB1EC, boundary: "frame_return" },
  programsSha256: "a".repeat(64), builds: Object.fromEntries(["hacktribe", "stock", "synth"].map(build => [build, {
    loader: { ...loaderRun(), maxInstructions: 1000, repeats: Array.from({ length: 3 }, loaderRun) },
    inputSha256: "b".repeat(64), outputSha256: "c".repeat(64), footprint: { codeDataBytes: 10, ramBytes: 20, occupiedBytes: 30 },
    original: Array.from({ length: 3 }, () => ({ scenarios: ["idle", "playing", "playing-keyboard", "sequencer-four-note-long-ties"].map(scenario => ({ scenario, instructions: 1000, deviceNs: 2e9, transport: scenario === "idle" ? 0 : 1, asserts: [], byPatch: {} })) })),
    patched: Array.from({ length: 3 }, () => ({ scenarios: ["idle", "playing", "playing-keyboard", "sequencer-four-note-long-ties", "blech-menu", "closed-apps", "app-mandelbrot", "app-life", "app-pong", "background-plugins"].map((scenario, i) => ({ scenario, instructions: 1000, deviceNs: 2e9, transport: i > 0 && i < 4 ? 1 : 0, asserts: [], byPatch: {}, ...(scenario.startsWith("app-") ? { semantic: { frames: 50, fault: 0, frameActive: 0, initialStateSha256: "1".repeat(64), stateSha256: "2".repeat(64), framebufferSha256: "d".repeat(64), progress: {} } } : {}) })) })),
  }])) });
const run = (baseline, candidate, phase) => spawnSync(python, ["-c", snippet], { input: JSON.stringify({ baseline, candidate, phase }), encoding: "utf8" });

test("profile validation requires three builds, three repeat runs and the intended transport", () => {
  const a = sample(); assert.equal(run(a, a).status, 0);
  for (const change of [x => delete x.builds.synth, x => x.builds.stock.patched.pop(),
    x => x.builds.hacktribe.original[0].scenarios.pop(),
    x => x.builds.synth.patched[0].scenarios[1].transport = 0,
    x => x.builds.stock.patched[0].scenarios[0].asserts.push("fault"),
    x => x.builds.stock.patched[0].scenarios[0].instructions = -1,
    x => x.builds.stock.patched.forEach(r => r.scenarios.pop()),
    x => delete x.builds.stock.loader,
    x => x.builds.stock.loader.repeats.pop(),
    x => x.builds.stock.loader.repeats[2].totalInstructions += 1]) {
    const bad = sample(); change(bad); assert.notEqual(run(a, bad).status, 0);
  }
});

test("a baseline cannot omit a required patched scene in every repeat", () => {
  const bad = sample();
  bad.builds.stock.patched.forEach(r => r.scenarios.pop());
  assert.notEqual(run(bad, bad).status, 0);
});

test("app captures require completed frames and an explicit reproducible input protocol", () => {
  for (const change of [x => delete x.appProtocol,
    x => x.version = 1,
    x => x.appProtocol = { warmupFrames: 8, rngSeed: 2, boundary: "frame_return" },
    x => x.builds.synth.patched.forEach(r => r.scenarios[6].semantic.frameActive = 1),
    x => x.builds.synth.patched.forEach(r => delete r.scenarios[6].semantic.stateSha256)]) {
    const a = sample(), bad = sample(); change(bad);
    assert.notEqual(run(a, bad).status, 0);
  }
});

test("comparison rejects unlike inputs, workloads, durations and non-reproducible runs", () => {
  const a = sample();
  for (const change of [x => x.method = "different", x => x.programsSha256 = "d".repeat(64),
    x => x.builds.synth.inputSha256 = "e".repeat(64), x => x.seconds = 1,
    x => x.builds.stock.patched[0].scenarios[0].deviceNs = 1e9,
    x => x.builds.stock.patched[2].scenarios[0].instructions += 1,
    x => x.builds.stock.patched[1].scenarios[0].byPatch.own = 1,
    x => x.builds.stock.original.forEach(r => r.scenarios[0].instructions += 1)]) {
    const bad = sample(); change(bad); assert.notEqual(run(a, bad).status, 0);
  }
});

test("pad targets use original ties and enforce ordinary, code and RAM budgets", () => {
  const a = sample(); assert.equal(run(a, a, "pad").status, 0);
  for (const change of [x => x.builds.stock.patched.forEach(r => r.scenarios[3].instructions = 1051),
    x => x.builds.synth.patched.forEach(r => r.scenarios[0].instructions = 1011),
    x => x.builds.stock.footprint.ramBytes += 1025,
    x => x.builds.hacktribe.footprint.codeDataBytes += 769]) {
    const bad = sample(); change(bad); assert.notEqual(run(a, bad, "pad").status, 0);
  }
});

test("missing phase evidence cannot turn into a passing optimization", () => {
  for (const phase of ["loader", "decoder", "mul", "sysex", "combined", "unknown"]) {
    assert.notEqual(run(sample(), sample(), phase).status, 0, phase);
  }
});

test("MUL acceptance uses the agreed reduction and still requires matching verified vectors", () => {
  const a = sample(), b = sample();
  const evidence = { pairs: 2225, vectorsSha256: "e".repeat(64), resultsMatch: true };
  for (const build of Object.keys(a.builds)) {
    a.builds[build].mul = { ...evidence, meanInstructions: 100000 };
    b.builds[build].mul = { ...evidence, meanInstructions: 80170 };
  }
  const accepted = run(a, b, "mul");
  assert.equal(accepted.status, 0, accepted.stderr);
  assert.equal(JSON.parse(accepted.stdout).mulMinimumReductionPercent, 19.83);
  for (const change of [x => x.builds.stock.mul.meanInstructions = 80171,
    x => x.builds.stock.mul.meanInstructions = -1,
    x => x.builds.stock.mul.resultsMatch = false,
    x => x.builds.stock.mul.pairs = 2224,
    x => x.builds.stock.mul.vectorsSha256 = "f".repeat(64),
    x => x.builds.stock.footprint.codeDataBytes += 1,
    x => x.builds.stock.patched.forEach(r => r.scenarios[6].semantic.fault = 1)]) {
    const bad = structuredClone(b); change(bad);
    assert.notEqual(run(a, bad, "mul").status, 0);
  }
});

test("CLI fails on absent input instead of skipping or creating a success report", () => {
  const dir = mkdtempSync(join(tmpdir(), "blech-profile-"));
  try {
    const report = join(dir, "report.json");
    writeFileSync(join(dir, "bad.json"), "{}");
    const child = spawnSync(python, ["tools/emu/patch_performance.py", "--baseline", dir, "--candidate", dir, "--out", report, "--phase", "baseline"], { encoding: "utf8" });
    assert.notEqual(child.status, 0);
  } finally { rmSync(dir, { recursive: true, force: true }); }
});


test("native counter includes blocks translated before the hook", { skip: spawnSync(python, ["-c", "import unicorn"]).status !== 0 && process.env.E2_ARM_REQUIRED !== "1" }, () => {
  const code = `import sys,json;sys.path[:0]=['tools/emu','tools/patch'];import arm;from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM;from unicorn.arm_const import UC_ARM_REG_LR;from patch_performance import BlockCounter
code=arm.assemble("""mov r0, #32
loop:
subs r0, r0, #1
bne loop
bx lr""",origin=0x10000)
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x10000,4096);u.mem_map(0x20000,4096);u.mem_write(0x10000,code.bytes)
def run():
 u.reg_write(UC_ARM_REG_LR,0x20000);u.emu_start(0x10000,0x20000)
run();counter=BlockCounter(u);_,count=counter.measure(run);print(json.dumps(count))`;
  const result = spawnSync(python, ["-c", code], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout), 66);
});

test("frame measurement waits for completed drawing and excludes a repeated boundary", { skip: spawnSync(python, ["-c", "import unicorn"]).status !== 0 && process.env.E2_ARM_REQUIRED !== "1" }, () => {
  const code = `import sys,json,struct
sys.path[:0]=['tools/emu','tools/patch']
from types import SimpleNamespace
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM
from unicorn import arm_const as A
from patch_performance import run_completed_frames
import arm
code=arm.assemble('''ldr r0, =0x20000
frame:
ldr r1, [r0]
add r1, r1, #1
str r1, [r0]
mov r1, #1
str r1, [r0, #4]
mov r2, #20
work:
subs r2, r2, #1
bne work
ldr r1, [r0, #8]
add r1, r1, #1
str r1, [r0, #8]
mov r1, #0
str r1, [r0, #4]
frame_return:
b frame''',origin=0x10000)
class Machine:
 def __init__(self):
  self.uc=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.A=A;self.ENTRIES=();self.time_ns=0;self.asserts=[]
  self.uc.mem_map(0x10000,4096);self.uc.mem_map(0x20000,4096);self.uc.mem_write(code.origin,code.bytes)
  self.uc.reg_write(A.UC_ARM_REG_PC,code.origin);self.uc.ctl_exits_enabled(True)
 def u32(self,at):return struct.unpack('<I',self.uc.mem_read(at,4))[0]
 def run_slice(self,limit):
  self.uc.emu_start(self.uc.reg_read(A.UC_ARM_REG_PC),0,count=3);self.time_ns+=1000
 def step_over(self,pc):
  self.uc.ctl_exits_enabled(False)
  try:self.uc.emu_start(pc,pc+4,count=1)
  finally:self.uc.ctl_exits_enabled(True)
 def lines(self):pass
 def irq(self):pass
m=Machine();dev=SimpleNamespace(m=m)
built=SimpleNamespace(layout={'runtime':0x20000},symbols={'SCRIPT_CONTROL_FRAMES':0,'SCRIPT_CONTROL_FRAME_ACTIVE':4,'frame_return':code.symbols['frame_return']})
while m.u32(0x20000)<1:m.run_slice(1e9)
assert m.u32(0x20004)==1 and m.u32(0x20008)==0
run_completed_frames(dev,built,1)
assert [m.u32(0x20000+i*4) for i in range(3)]==[2,0,2]
run_completed_frames(dev,built,3)
assert [m.u32(0x20000+i*4) for i in range(3)]==[5,0,5]
assert m.uc.reg_read(A.UC_ARM_REG_PC)==code.symbols['frame_return']
print(json.dumps(True))`;
  const result = spawnSync(python, ["-c", code], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout), true);
});
