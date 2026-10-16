// Writes test/helpers.mjs's made-up firmware (makeFirmware) to the file named on the command line, for make.py.
import { writeFileSync } from "node:fs";
import { makeFirmware } from "../../helpers.mjs";

writeFileSync(process.argv[2], await makeFirmware());
