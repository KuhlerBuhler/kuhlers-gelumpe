/**
 * Plain-language labels for the unit parameters in units.json, which only
 * carries Korg's snake_case names. The generator (tools/units-to-map.mjs)
 * copies them into the map, so the page, the linter and the docs read one
 * source.
 *
 * Nothing here was measured on hardware. The labels translate the parameter
 * names; the group is a guess from the name. units.json holds no value
 * ranges (those come from fx-ranges.mjs, read out of the DSP tables), no
 * choice names and no units, so none of those are claimed: a "choice" is
 * shown as a plain number, a "switch" is a name that suggests on/off whose
 * factory defaults are only 0 and 1.
 *
 * "(Sync an)" and "(Sync aus)" read the on_* and off_* names as the state of
 * the tempo sync switch next to them. That comes from the parameter order,
 * it was not measured.
 *
 * Flags: s = switch (0/1), c = choice (shown as a number, names unknown),
 * x = expert (meaning unclear, hidden behind the expert toggle).
 */
export const GROUPS = [
  { id: "mix", label: "Mix und Pegel" },
  { id: "eq", label: "EQ" },
  { id: "filter", label: "Filter" },
  { id: "delay", label: "Delay und Zeit" },
  { id: "mod", label: "Modulation" },
  { id: "dyn", label: "Dynamik" },
  { id: "tone", label: "Klang" },
  { id: "room", label: "Raum" },
  { id: "other", label: "Weitere" },
];

const t = (de, group, flags = "") => ({ de, group, flags });
const eqBand = n => ({
  [`b${n}_frequency`]: t(`Band ${n} Frequenz`, "eq"),
  [`b${n}_gain`]: t(`Band ${n} Gain`, "eq"),
  [`b${n}_q`]: t(`Band ${n} Q`, "eq"),
  [`b${n}_type`]: t(`Band ${n} Typ`, "eq", "c"),
});
const postEq = n => ({
  [`post_eq${n}_frequency`]: t(`Post-EQ ${n} Frequenz`, "eq"),
  [`post_eq${n}_gain`]: t(`Post-EQ ${n} Gain`, "eq"),
  [`post_eq${n}_q`]: t(`Post-EQ ${n} Q`, "eq"),
});

export const PARAM_LABELS = {
  dry_wet: t("Dry/Wet", "mix"), dry_level: t("Dry-Pegel", "mix"), wet_level: t("Wet-Pegel", "mix"),
  wet_spread: t("Wet-Breite", "mix"), blend: t("Blend", "mix"),
  input_level: t("Eingangspegel", "mix"), input_trim: t("Eingangs-Trim", "mix"), trim: t("Trim", "mix"), trim2: t("Trim 2", "mix"),
  output_level: t("Ausgangspegel", "mix"), output_gain: t("Ausgangs-Gain", "mix"), output_gain_adjust: t("Ausgangs-Gain", "mix"),
  output_select: t("Ausgang", "mix", "c"), amp_level: t("Amp-Pegel", "mix"), gain: t("Gain", "mix"),
  spread: t("Breite", "mix"), rev_level: t("Hall-Pegel", "room"), er_level: t("Early-Pegel", "room"),
  tap1_level: t("Tap 1 Pegel", "delay"), tap2_level: t("Tap 2 Pegel", "delay"),

  ...eqBand(1), ...eqBand(2), ...eqBand(3), ...eqBand(4),
  ...postEq(1), ...postEq(2), ...postEq(3),
  pre_eq_frequency: t("Pre-EQ Frequenz", "eq"), pre_eq_gain: t("Pre-EQ Gain", "eq"), pre_eq_q: t("Pre-EQ Q", "eq"),
  pre_leq_frequency: t("Tiefen-EQ Frequenz", "eq"), pre_leq_gain: t("Tiefen-EQ Gain", "eq"),
  pre_heq_frequency: t("Höhen-EQ Frequenz", "eq"), pre_heq_gain: t("Höhen-EQ Gain", "eq"),
  lo_eq: t("Tiefen-EQ", "eq"), hi_eq: t("Höhen-EQ", "eq"),

  lo_cut1: t("Low-Cut 1", "filter"), lo_cut2: t("Low-Cut 2", "filter"), hi_cut1: t("High-Cut 1", "filter"), hi_cut2: t("High-Cut 2", "filter"),
  pre_lpf: t("Pre-Tiefpass", "filter"), pre_lpf_sw: t("Pre-Tiefpass an", "filter", "s"),
  hpf_level: t("Hochpass-Pegel", "filter"), lpf_level: t("Tiefpass-Pegel", "filter"), lpf24_level: t("Tiefpass-Pegel (24 dB)", "filter"), bpf_level: t("Bandpass-Pegel", "filter"),
  frequency: t("Cutoff", "filter"), resonance: t("Resonance", "filter"),
  osc_freq: t("Osc-Frequenz", "mod"),

  delay: t("Delay-Zeit", "delay"), delay_lag: t("Delay-Lag", "delay"), l_delay: t("Delay-Zeit links", "delay"), r_delay: t("Delay-Zeit rechts", "delay"),
  time: t("Hallzeit", "room"), time1: t("Zeit 1", "delay"), time2: t("Zeit 2", "delay"), time_ratio: t("Zeitverhältnis", "delay"),
  feedback: t("Feedback", "delay"), fb_depth: t("Feedback", "delay"), fb_hicut: t("Feedback High-Cut", "delay"), fb_type: t("Feedback-Typ", "delay", "c"),
  delay_time_tempo_sync: t("Tempo-Sync", "delay", "s"), tempo_sync: t("Tempo-Sync", "delay", "s"),
  duration_bpm_sync: t("Dauer-Sync", "delay"), duration_lag: t("Dauer-Lag", "delay"),
  on_time_ratio: t("Zeitverhältnis (Sync an)", "delay"), off_time_ratio: t("Zeitverhältnis (Sync aus)", "delay"),
  on_duration: t("Dauer (Sync an)", "delay"), off_duration: t("Dauer (Sync aus)", "delay"),
  off_delay_time: t("Zeit (Sync aus)", "delay"), off_l_delay_time: t("Zeit links (Sync aus)", "delay"), off_r_delay_time: t("Zeit rechts (Sync aus)", "delay"),
  on_sync_note: t("Notenwert (Sync an)", "delay", "c"), on_syncnote: t("Notenwert (Sync an)", "delay", "c"),
  on_l_syncnote: t("Notenwert links (Sync an)", "delay", "c"), on_r_syncnote: t("Notenwert rechts (Sync an)", "delay", "c"),
  s_note1: t("Notenwert 1", "delay", "c"), s_note2: t("Notenwert 2", "delay", "c"),
  pre_delay: t("Pre-Delay", "room"), sync_on: t("Tempo-Sync", "delay", "s"),
  loop_length: t("Loop-Länge", "delay"), loop_trigger: t("Loop-Trigger", "delay", "c"), loop_type: t("Loop-Typ", "delay", "c"),
  loopswitch: t("Loop an", "delay", "s"), reset: t("Reset", "delay", "s"), reset_phase: t("Reset-Phase", "delay"),

  lfo_wave: t("LFO-Wellenform", "mod", "c"), lfo_shape: t("LFO-Shape", "mod"), lfo_speed: t("LFO-Rate", "mod"), lfo_depth: t("LFO-Tiefe", "mod"),
  lfo_phase: t("LFO-Phase", "mod"), lfo_rch_degree: t("LFO-Phase rechts", "mod"), lfo_step: t("LFO-Stufen", "mod"),
  lfo_sync: t("LFO-Sync", "mod", "s"), lfo_bpm_sync: t("LFO-Sync", "mod", "s"),
  lfo_sync_note: t("LFO-Notenwert", "mod", "c"), lfo_syncnote: t("LFO-Notenwert", "mod", "c"),
  lfo_reset: t("LFO-Reset", "mod", "s"), lfo_reset_phase: t("LFO-Reset-Phase", "mod"), lfo_resetphase: t("LFO-Reset-Phase", "mod"),
  lfo_squ_dur: t("LFO-Rechteck-Dauer", "mod"), lfo_squdur: t("LFO-Rechteck-Dauer", "mod"),
  lfo_squ_lag: t("LFO-Rechteck-Lag", "mod"), lfo_squlag: t("LFO-Rechteck-Lag", "mod"), squ_dur: t("Rechteck-Dauer", "mod"),
  off_lfo_freq: t("LFO-Rate (Sync aus)", "mod"), off_freq: t("Rate (Sync aus)", "mod"),
  mod_wave: t("Mod-Wellenform", "mod", "c"), mod_depth: t("Mod-Tiefe", "mod"), mod_freq: t("Mod-Rate", "mod"),
  mod_int: t("Mod-Tiefe", "mod"), modint: t("Mod-Tiefe", "mod"), mod_lag: t("Mod-Lag", "mod"),
  mod_rch_degree: t("Mod-Phase rechts", "mod"), mod_source: t("Mod-Quelle", "mod", "c"), mod_src: t("Mod-Quelle", "mod", "c"),
  freq_mod_int: t("Cutoff-Modulation", "mod"), level_mod_int: t("Pegel-Modulation", "mod"),
  level_mod_source: t("Pegel-Mod-Quelle", "mod", "c"), level_mod_type: t("Pegel-Mod-Typ", "mod", "c"),
  drive_mod_int: t("Drive-Modulation", "mod"), phase: t("Phase", "mod"), manual: t("Manual", "mod"),
  pitch_lag: t("Pitch-Lag", "mod"), delta_pitch: t("Pitch-Änderung", "mod"), fine: t("Feintuning", "mod"),

  threshold: t("Threshold", "dyn"), ratio: t("Ratio", "dyn"), knee: t("Knee", "dyn"), attack: t("Attack", "dyn"), release: t("Release", "dyn"),
  hold_time: t("Hold-Zeit", "dyn"), sensitivity: t("Empfindlichkeit", "dyn"), env_sens: t("Empfindlichkeit", "dyn"),
  envelope_select: t("Hüllkurve", "dyn", "c"), env_select: t("Hüllkurve", "dyn", "c"), env_response: t("Hüllkurven-Ansprache", "dyn"),
  tube_sat: t("Röhren-Sättigung", "dyn"), tubesat: t("Röhren-Sättigung", "dyn"),

  drive: t("Drive", "tone"), drive_tone: t("Drive-Klang", "tone"), saturation: t("Sättigung", "tone"),
  bit_depth: t("Bittiefe", "tone"), sample_freq: t("Samplerate", "tone"), mask_type: t("Maskentyp", "tone", "c"),
  type: t("Typ", "tone", "c"), wave: t("Wellenform", "tone", "c"), wah_type: t("Wah-Typ", "tone", "c"),
  tube1_bias: t("Röhre 1 Bias", "tone"), tube1_gain: t("Röhre 1 Gain", "tone"), tube1_phase: t("Röhre 1 Phase", "tone"), tube1_sat: t("Röhre 1 Sättigung", "tone"),
  tube2_bias: t("Röhre 2 Bias", "tone"), tube2_gain: t("Röhre 2 Gain", "tone"), tube2_sat: t("Röhre 2 Sättigung", "tone"),
  emphatic_lag: t("Betonungs-Lag", "tone"), emphatic_point: t("Betonungspunkt", "tone"),
  scratch: t("Scratch", "tone"), scratch_lag: t("Scratch-Lag", "tone"), scratch_width: t("Scratch-Breite", "tone"), pad_on: t("Pad an", "tone", "s"),

  hi_damp: t("Höhendämpfung", "tone"), hidamp: t("Höhendämpfung", "tone"), high_damp: t("Höhendämpfung", "tone"),
  lo_damp: t("Tiefendämpfung", "tone"), lodamp: t("Tiefendämpfung", "tone"), low_damp: t("Tiefendämpfung", "tone"),

  asobi: t("Asobi", "other", "x"), control: t("Control", "other", "x"), do_nothing: t("Ohne Funktion", "other", "x"),
  env_bit_shift_amount: t("Hüllkurve Bit-Shift", "other", "x"), fader: t("Fader", "other", "x"), gainshift: t("Gain-Shift", "other", "x"),
  hpf_b1: t("Hochpass B1", "other", "x"), pd_thru: t("PD Thru", "other", "x"), peak_hold_b1: t("Peak-Hold B1", "other", "x"),
  step: t("Stufe", "other", "x"),
};

const humanize = name => name.replace(/_/g, " ").replace(/^./, c => c.toUpperCase());

/** Label, group and flags for a parameter name; a name without an entry is an expert field. */
export function labelFor(name) {
  return PARAM_LABELS[name] ?? t(humanize(name), "other", "x");
}
