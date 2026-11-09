/** Run a child asynchronously, collecting its output, exit status and terminating signal.
 * Timeouts and output overflows kill and reap the child before returning. */
import { spawn } from "node:child_process";
import { availableParallelism } from "node:os";
import { parentEnv, track } from "./lifetime.mjs";

/** Python runs per file; each run may also start its own worker pool. */
const jobs = Number(process.env.GELUMPE_JOBS);
export const slots = Number.isSafeInteger(jobs) && jobs > 0 ? jobs : Math.max(2, Math.floor(availableParallelism() / 2));

export function run(command, args, { input, timeout = 0, cwd, env, maxBuffer = 4 * 1024 * 1024 } = {}) {
  if (input !== undefined && typeof input !== "string" && !Buffer.isBuffer(input)) {
    return Promise.reject(new TypeError("input must be a string or Buffer"));
  }
  return new Promise(resolve => {
    const child = track(spawn(command, args, { cwd, env: parentEnv(env), stdio: [input === undefined ? "ignore" : "pipe", "pipe", "pipe"] }));
    let stdout = "";
    let stderr = "";
    let error;
    const fail = e => { error = error || e; child.kill("SIGKILL"); };
    const timer = timeout ? setTimeout(() => fail(Object.assign(new Error(`${command} ETIMEDOUT`), { code: "ETIMEDOUT" })), timeout) : null;
    const take = (which, chunk) => {
      if (which === "out") stdout += chunk; else stderr += chunk;
      if (stdout.length + stderr.length > maxBuffer) fail(Object.assign(new Error(`${command} ENOBUFS`), { code: "ENOBUFS" }));
    };
    child.stdout.setEncoding("utf8").on("data", d => take("out", d));
    child.stderr.setEncoding("utf8").on("data", d => take("err", d));
    child.on("error", e => { clearTimeout(timer); resolve({ status: null, signal: null, stdout, stderr, error: e }); });
    child.on("close", (status, signal) => { clearTimeout(timer); resolve({ status, signal, stdout, stderr, error }); });
    if (child.stdin) {
      child.stdin.on("error", e => { if (e.code !== "EPIPE" && e.code !== "ECONNRESET") fail(e); });
      child.stdin.end(input);
    }
  });
}
