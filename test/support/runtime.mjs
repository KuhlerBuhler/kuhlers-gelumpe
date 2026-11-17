/**
 * The runtime patches are built, not committed (tools/patch/ensure-runtime.mjs). tools/test-runner.mjs builds them
 * before a suite starts; a test file that reads them imports this so `node --test test/load-bar.test.mjs` works too.
 */
import { ensureRuntimePatches } from "../../tools/patch/ensure-runtime.mjs";

ensureRuntimePatches({ log: message => process.stderr.write(message + "\n") });
