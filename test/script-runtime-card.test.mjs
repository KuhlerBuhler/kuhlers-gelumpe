import { nativeTest } from "./support/native.mjs";

nativeTest("native card loader reads the collection, isolates bad blocks and refuses damaged files", ["test_script_card"], 900_000);
