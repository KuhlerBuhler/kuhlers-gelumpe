import { nativeTest } from "./support/native.mjs";

// Every test that boots Blechy runs about 5.4 million ARM instructions: this file takes about a minute alone, several on a busy machine.
nativeTest("native input and frame hooks preserve guards, queues, budget and continuation",
  ["test_script_hooks", "test_script_vm_optimizations", "test_script_vm_validator"], 900_000);
