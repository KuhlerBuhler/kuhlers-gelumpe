/**
 * Plain German names for the building blocks (DSP units of data/units.json) and their parameters, for the Baukasten.
 * The unit's own name stays visible beside it for anyone who knows it. A unit missing here shows its own name.
 */
export const GROUPS = ["Hall", "Echo", "Filter", "Bewegung", "Verzerrung", "Dynamik", "Klang", "Spezial"];

export const UNITS = {
  ifx: {
    0x01: ["Kompressor (MKP2)", "Dynamik"], 0x02: ["Kompressor (SR1)", "Dynamik"], 0x03: ["Einfacher Kompressor", "Dynamik"],
    0x04: ["Punch", "Dynamik"], 0x05: ["Limiter", "Dynamik"], 0x06: ["EQ, 2 Bänder", "Klang"], 0x07: ["EQ, 4 Bänder", "Klang"],
    0x08: ["Exciter", "Klang"], 0x09: ["Lo-Fi (Decimator)", "Verzerrung"], 0x0a: ["Filter", "Filter"], 0x0f: ["Verzerrung", "Verzerrung"],
    0x10: ["Acid Drive", "Verzerrung"], 0x11: ["Chorus", "Bewegung"], 0x12: ["Flanger", "Bewegung"], 0x13: ["Phaser", "Bewegung"],
    0x14: ["Tremolo", "Bewegung"], 0x15: ["Lautstärke-Modulation", "Bewegung"], 0x16: ["Ringmodulator", "Bewegung"], 0x18: ["Kurzes Echo", "Echo"],
  },
  mfx: {
    0x28: ["Kompressor (MKP2)", "Dynamik"], 0x29: ["Kompressor (SR1)", "Dynamik"], 0x2a: ["Limiter", "Dynamik"], 0x2b: ["EQ, 4 Bänder", "Klang"],
    0x2c: ["Wah", "Filter"], 0x2d: ["Multimode-Filter", "Filter"], 0x2e: ["Verzerrung", "Verzerrung"], 0x2f: ["Röhren-Vorstufe", "Verzerrung"],
    0x31: ["Chorus", "Bewegung"], 0x32: ["Flanger", "Bewegung"], 0x33: ["Phaser", "Bewegung"], 0x34: ["Tremolo", "Bewegung"],
    0x35: ["Lautstärke-Modulation", "Bewegung"], 0x36: ["Hall", "Hall"], 0x37: ["Weicher Hall", "Hall"], 0x38: ["Plate, nass", "Hall"],
    0x39: ["Plate, trocken", "Hall"], 0x3a: ["Raumhall", "Hall"], 0x3b: ["Mod Delay", "Echo"], 0x3c: ["Bandecho", "Echo"],
    0x3d: ["Grain Shifter", "Spezial"], 0x3e: ["Lo-Fi (Decimator)", "Verzerrung"], 0x3f: ["Looper", "Spezial"], 0x40: ["Vinyl Break", "Spezial"],
  },
};

/** Parameter names that come up in many units; the rest show their own name with spaces. */
export const PARAMS = {
  dry_wet: "Mischung (trocken bis nass)", time: "Länge", hi_damp: "Höhen dämpfen", high_damp: "Höhen dämpfen", lo_damp: "Tiefen dämpfen",
  low_damp: "Tiefen dämpfen", lodamp: "Tiefen dämpfen", hidamp: "Höhen dämpfen", pre_delay: "Vorverzögerung", feedback: "Rückkopplung",
  fb_depth: "Rückkopplung", resonance: "Resonanz", frequency: "Frequenz", gain: "Verstärkung", output_level: "Ausgangspegel",
  output_gain: "Ausgangspegel", trim: "Eingangspegel", input_trim: "Eingangspegel", lfo_speed: "LFO-Tempo", lfo_wave: "LFO-Welle",
  lfo_sync: "LFO im Takt", mod_int: "Modulationstiefe", modint: "Modulationstiefe", threshold: "Schwelle", ratio: "Verhältnis",
  attack: "Ansprechzeit (Attack)", release: "Abklingzeit (Release)", drive: "Antrieb", sample_freq: "Abtastrate", bit_depth: "Bittiefe",
  wet_spread: "Stereobreite", spread: "Stereobreite", delay_lag: "Gleiten der Zeit", saturation: "Sättigung", manual: "Grundwert",
  dry_level: "Pegel trocken", wet_level: "Pegel Echo", tempo_sync: "Im Takt", delay_time_tempo_sync: "Zeit im Takt",
  off_delay_time: "Zeit", off_l_delay_time: "Zeit links", off_r_delay_time: "Zeit rechts", on_syncnote: "Notenwert",
  on_l_syncnote: "Notenwert links", on_r_syncnote: "Notenwert rechts", mod_depth: "Modulationstiefe", mod_freq: "Modulationstempo",
  time1: "Zeit 1", time2: "Zeit 2", tap1_level: "Pegel Kopf 1", tap2_level: "Pegel Kopf 2",
  off_time_ratio: "Zeit (frei, fein)", on_time_ratio: "Zeit (im Takt, fein)", time_ratio: "Zeit (fein)", sync_on: "Im Takt",
  lfo_sync_note: "LFO-Notenwert", lfo_syncnote: "LFO-Notenwert", s_note1: "Notenwert 1", s_note2: "Notenwert 2", lfo_depth: "LFO-Tiefe",
  pre_leq_gain: "Tiefen vorher", pre_leq_frequency: "Tiefen-Frequenz vorher", pre_heq_gain: "Höhen vorher", pre_heq_frequency: "Höhen-Frequenz vorher",
  mod_wave: "Modulations-Welle", mod_rch_degree: "Versatz rechts", fb_type: "Art der Rückkopplung", lfo_phase: "LFO-Phase",
  lfo_reset: "LFO neu starten", lfo_reset_phase: "LFO-Startpunkt", lfo_resetphase: "LFO-Startpunkt", l_delay: "Verzögerung links",
  r_delay: "Verzögerung rechts", mod_src: "Modulationsquelle", envelope_select: "Hüllkurve", sensitivity: "Empfindlichkeit",
  knee: "Knie", hold_time: "Haltezeit", tube_sat: "Röhren-Sättigung", tubesat: "Röhren-Sättigung", lo_eq: "Tiefen", hi_eq: "Höhen",
  trim2: "Eingangspegel 2", pd_thru: "Vorverzögerung umgehen", rev_level: "Hall-Pegel", er_level: "Erstreflexionen",
};

/** The parameters that shape the sound most; the Baukasten shows these first and folds the rest away. */
export const MAIN = new Set(["dry_wet", "time", "feedback", "fb_depth", "gain", "drive", "resonance", "frequency", "lfo_speed", "mod_int", "modint",
  "wet_level", "dry_level", "off_delay_time", "off_l_delay_time", "off_r_delay_time", "sample_freq", "bit_depth", "threshold", "ratio",
  "mod_depth", "mod_freq", "hi_damp", "high_damp", "pre_delay", "spread", "wet_spread", "time1", "time2", "saturation", "manual", "amp_level"]);

/** "off_l_delay_time" to "Off l delay time", for a parameter without a name here. */
export const paramLabel = name => PARAMS[name] ?? name.replace(/_/g, " ").replace(/^./, c => c.toUpperCase());

/** [German name, group] of a unit, or its own name in "Spezial". */
export const unitLabel = (kind, id, own = "") => UNITS[kind]?.[id] ?? [own || `Baustein ${id}`, "Spezial"];
