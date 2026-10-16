// The card tests of emulator-card.test.mjs with Korg's original firmware (E2_STOCK_VSB) instead of Hacktribe's:
// its files live in KORG/electribe sampler/ and not in KORG/hacktribe/. Skipped without the file.
process.env.E2_VSB = process.env.E2_STOCK_VSB ?? "";
await import("./emulator-card.test.mjs");
