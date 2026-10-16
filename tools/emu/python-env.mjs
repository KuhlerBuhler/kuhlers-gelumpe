/**
 * Which Python the emulator tools use. Normally the venv in tools/emu/.venv.
 * For the Intel app on an Apple Silicon Mac (target x86_64-apple-darwin) it is
 * a second venv, .venv-x64, made from an x86_64 Python that GELUMPE_X64_PYTHON
 * points at and run through Rosetta (`arch -x86_64`), so PyInstaller freezes an
 * Intel binary.
 */
import { fileURLToPath } from "node:url";

const here = new URL("./", import.meta.url);
const win = process.platform === "win32";

export const targetTriple = () => process.env.TAURI_ENV_TARGET_TRIPLE || process.env.TAURI_TARGET_TRIPLE || "";

export function pythonEnv(triple = targetTriple()) {
  const intelOnArm = triple === "x86_64-apple-darwin" && process.platform === "darwin" && process.arch === "arm64";
  const dir = fileURLToPath(new URL(intelOnArm ? ".venv-x64" : ".venv", here));
  const python = `${dir}/${win ? "Scripts/python.exe" : "bin/python"}`;
  const basePython = intelOnArm ? process.env.GELUMPE_X64_PYTHON : null;
  if (intelOnArm && !basePython) {
    throw new Error("Intel-Build auf Apple Silicon: GELUMPE_X64_PYTHON auf ein x86_64-Python (3.10+) setzen, siehe README (Die App).");
  }
  /** [command, args] that runs `exe` the way this environment needs. */
  const command = (exe, args) => (intelOnArm ? ["arch", ["-x86_64", exe, ...args]] : [exe, args]);
  return { dir, python, basePython, command };
}
