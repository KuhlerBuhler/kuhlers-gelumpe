/**
 * spawnSync that does not block: the same fields (status, stdout, stderr, error), so the
 * checks around a call stay as they were, but the tests of one file can run side by side
 * (describe with concurrency). A run that outlives `timeout` is killed and comes back with
 * error.code ETIMEDOUT, as spawnSync reports it.
 */
import { spawn } from "node:child_process";
import { availableParallelism } from "node:os";
import { parentEnv, track } from "./lifetime.mjs";

/** Python runs per file; each run may also start its own worker pool. */
const jobs = Number(process.env.GELUMPE_JOBS);
export const slots = Number.isSafeInteger(jobs) && jobs > 0 ? jobs : Math.max(2, Math.floor(availableParallelism() / 2));

export function run(command, args, { timeout = 0, cwd, env, maxBuffer = 4 * 1024 * 1024 } = {}) {
  return new Promise(resolve => {
    const child = track(spawn(command, args, { cwd, env: parentEnv(env), stdio: ["ignore", "pipe", "pipe"] }));
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
    child.on("error", e => { clearTimeout(timer); resolve({ status: null, stdout, stderr, error: e }); });
    child.on("close", status => { clearTimeout(timer); resolve({ status, stdout, stderr, error }); });
  });
}
