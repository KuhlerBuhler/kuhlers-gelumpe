/**
 * The catalog of the Baukasten (site/app/baukasten.mjs): ready effects and modulation types as .e2fx v2 values
 * (src/fx-v2.mjs). The values are the defaults of the units in data/units.json with a few changed; the Short Delay is
 * the author's own, set on his ESX. A new entry comes in by pull request, like a plugin.
 */
export const FX_CATALOG = Object.freeze([
 {
  "kind": "mfx",
  "name": "Short Delay",
  "description": "Ein kurzes Stereo-Echo, die Wiederholungen leicht versetzt. Das Touchpad mischt das Echo dazu und verschiebt die Zeiten.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 59,
    "unitName": "M_mod_delay",
    "params": {
     "dry_wet": 114,
     "wet_spread": 100,
     "input_trim": 95,
     "pre_leq_gain": 36,
     "pre_leq_frequency": 20,
     "pre_heq_gain": 36,
     "pre_heq_frequency": 44,
     "delay_time_tempo_sync": 0,
     "off_time_ratio": 65,
     "off_l_delay_time": 19,
     "off_r_delay_time": 21,
     "on_time_ratio": 26,
     "on_l_syncnote": 44,
     "on_r_syncnote": 42,
     "fb_type": 0,
     "fb_depth": 0,
     "high_damp": 12,
     "low_damp": 5,
     "mod_depth": 0,
     "mod_wave": 0,
     "mod_freq": 34,
     "mod_rch_degree": 18,
     "delay_lag": 30
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 2,
    "param": 0,
    "low": 45,
    "high": 122
   },
   {
    "source": 65,
    "chain": 7,
    "param": 5,
    "low": 0,
    "high": 88
   },
   {
    "source": 66,
    "chain": 2,
    "param": 9,
    "low": 60,
    "high": 4
   },
   {
    "source": 66,
    "chain": 2,
    "param": 10,
    "low": 62,
    "high": 5
   },
   {
    "source": 67,
    "chain": 2,
    "param": 15,
    "low": 0,
    "high": 127
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "1/6 Delay",
  "description": "Echo auf Vierteltriolen. Regler links nimmt das Echo raus, rechts mehr Wiederholungen.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 24,
    "unitName": "I_short_delay",
    "params": {
     "dry_level": 127,
     "wet_level": 100,
     "input_trim": 127,
     "tempo_sync": 1,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 35,
     "on_syncnote": 6,
     "fb_depth": 30,
     "high_damp": 60,
     "low_damp": 15,
     "delay_lag": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 69,
    "chain": 0,
    "param": 1,
    "low": 100,
    "high": 0
   },
   {
    "source": 69,
    "chain": 0,
    "param": 8,
    "low": 30,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 30,
    "high": 88
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "1/24 Delay",
  "description": "Echo auf Sechzehnteltriolen, rollt schnell. Regler links nimmt das Echo raus, rechts mehr Wiederholungen.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 24,
    "unitName": "I_short_delay",
    "params": {
     "dry_level": 127,
     "wet_level": 100,
     "input_trim": 127,
     "tempo_sync": 1,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 35,
     "on_syncnote": 2,
     "fb_depth": 30,
     "high_damp": 40,
     "low_damp": 15,
     "delay_lag": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 69,
    "chain": 0,
    "param": 1,
    "low": 100,
    "high": 0
   },
   {
    "source": 69,
    "chain": 0,
    "param": 8,
    "low": 30,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 30,
    "high": 88
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "5/32 Delay",
  "description": "Ein Achtel mal 5/4: das Echo kommt etwas nach der Achtel und schiebt. Regler links nimmt das Echo raus, rechts mehr Wiederholungen.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 24,
    "unitName": "I_short_delay",
    "params": {
     "dry_level": 127,
     "wet_level": 100,
     "input_trim": 127,
     "tempo_sync": 1,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 8,
     "on_syncnote": 5,
     "fb_depth": 30,
     "high_damp": 60,
     "low_damp": 15,
     "delay_lag": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 69,
    "chain": 0,
    "param": 1,
    "low": 100,
    "high": 0
   },
   {
    "source": 69,
    "chain": 0,
    "param": 8,
    "low": 30,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 30,
    "high": 88
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "3/64 Delay",
  "description": "Ein sehr kurzes Echo, eine Zweiunddreißigstel mal 3/2. Klingt metallisch, fast wie ein Kammfilter.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 24,
    "unitName": "I_short_delay",
    "params": {
     "dry_level": 127,
     "wet_level": 70,
     "input_trim": 127,
     "tempo_sync": 1,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 62,
     "on_syncnote": 1,
     "fb_depth": 45,
     "high_damp": 60,
     "low_damp": 15,
     "delay_lag": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 69,
    "chain": 0,
    "param": 1,
    "low": 100,
    "high": 0
   },
   {
    "source": 69,
    "chain": 0,
    "param": 8,
    "low": 45,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 45,
    "high": 70
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Slap Delay",
  "description": "Ein kurzes Echo, eine Zweiunddreißigstel lang, wenig Wiederholungen. Dickt den Ton an wie ein Slapback. Regler links nimmt das Echo raus, rechts mehr Wiederholungen.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 24,
    "unitName": "I_short_delay",
    "params": {
     "dry_level": 127,
     "wet_level": 100,
     "input_trim": 127,
     "tempo_sync": 1,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 35,
     "on_syncnote": 1,
     "fb_depth": 20,
     "high_damp": 60,
     "low_damp": 15,
     "delay_lag": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 69,
    "chain": 0,
    "param": 1,
    "low": 100,
    "high": 0
   },
   {
    "source": 69,
    "chain": 0,
    "param": 8,
    "low": 20,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 20,
    "high": 88
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Long Delay",
  "description": "Ein langes Echo, eine punktierte Viertel, dunkel und mit vielen Wiederholungen. Regler links nimmt das Echo raus, rechts mehr Wiederholungen.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 24,
    "unitName": "I_short_delay",
    "params": {
     "dry_level": 127,
     "wet_level": 90,
     "input_trim": 127,
     "tempo_sync": 1,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 35,
     "on_syncnote": 10,
     "fb_depth": 40,
     "high_damp": 50,
     "low_damp": 25,
     "delay_lag": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 69,
    "chain": 0,
    "param": 1,
    "low": 90,
    "high": 0
   },
   {
    "source": 69,
    "chain": 0,
    "param": 8,
    "low": 40,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 40,
    "high": 88
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Loud Distortion",
  "description": "Weniger Verzerrung als das Werkspreset (Gain 64 statt 100), der Ausgangspegel knapp darüber (18 statt 11). Der Regler dreht die Verzerrung.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 15,
    "unitName": "I_distortion",
    "params": {
     "dry_wet": 0,
     "gain": 64,
     "pre_eq_frequency": 35,
     "pre_eq_q": 15,
     "pre_eq_gain": 48,
     "post_eq1_frequency": 16,
     "post_eq1_q": 5,
     "post_eq1_gain": 36,
     "post_eq2_frequency": 43,
     "post_eq2_q": 5,
     "post_eq2_gain": 42,
     "post_eq3_frequency": 53,
     "post_eq3_q": 5,
     "post_eq3_gain": 25,
     "output_level": 18
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 32,
    "high": 96
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Fuzz",
  "description": "Volle Verzerrung mit vorgeschobenen Mitten, weniger Bass und Höhen.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 15,
    "unitName": "I_distortion",
    "params": {
     "dry_wet": 0,
     "gain": 80,
     "pre_eq_frequency": 35,
     "pre_eq_q": 15,
     "pre_eq_gain": 60,
     "post_eq1_frequency": 16,
     "post_eq1_q": 5,
     "post_eq1_gain": 30,
     "post_eq2_frequency": 43,
     "post_eq2_q": 5,
     "post_eq2_gain": 42,
     "post_eq3_frequency": 53,
     "post_eq3_q": 5,
     "post_eq3_gain": 20,
     "output_level": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 60,
    "high": 100
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Crunch",
  "description": "Leicht angezerrt, etwas mehr Bass. Gut auf Drums und Bass.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 15,
    "unitName": "I_distortion",
    "params": {
     "dry_wet": 0,
     "gain": 40,
     "pre_eq_frequency": 35,
     "pre_eq_q": 15,
     "pre_eq_gain": 48,
     "post_eq1_frequency": 16,
     "post_eq1_q": 5,
     "post_eq1_gain": 42,
     "post_eq2_frequency": 43,
     "post_eq2_q": 5,
     "post_eq2_gain": 42,
     "post_eq3_frequency": 53,
     "post_eq3_q": 5,
     "post_eq3_gain": 30,
     "output_level": 20
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 20,
    "high": 60
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Hot Overdrive",
  "description": "Der Overdrive weiter aufgedreht. Der Regler dreht den Drive und nimmt dabei den Pegel zurück, wie Korgs Overdrive.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 16,
    "unitName": "I_acid_driver",
    "params": {
     "drive": 70,
     "output_level": 27
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 0,
    "low": 30,
    "high": 100
   },
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 39,
    "high": 19
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Tri Ping Pong",
  "description": "Links Vierteltriolen, rechts Achteltriolen. X mischt das Echo dazu, Y die Wiederholungen.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 59,
    "unitName": "M_mod_delay",
    "params": {
     "dry_wet": 100,
     "wet_spread": 127,
     "input_trim": 80,
     "pre_leq_gain": 36,
     "pre_leq_frequency": 20,
     "pre_heq_gain": 36,
     "pre_heq_frequency": 44,
     "delay_time_tempo_sync": 1,
     "off_time_ratio": 65,
     "off_l_delay_time": 47,
     "off_r_delay_time": 41,
     "on_time_ratio": 35,
     "on_l_syncnote": 6,
     "on_r_syncnote": 4,
     "fb_type": 0,
     "fb_depth": 60,
     "high_damp": 40,
     "low_damp": 10,
     "mod_depth": 10,
     "mod_wave": 1,
     "mod_freq": 26,
     "mod_rch_degree": 9,
     "delay_lag": 0
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 7,
    "param": 5,
    "low": 0,
    "high": 98
   },
   {
    "source": 66,
    "chain": 2,
    "param": 0,
    "low": 40,
    "high": 100
   },
   {
    "source": 67,
    "chain": 2,
    "param": 15,
    "low": 30,
    "high": 85
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Dub Echo",
  "description": "Ein Bandecho mit vielen, dunkler werdenden Wiederholungen und etwas Leiern. X mischt das Echo dazu, Y die Wiederholungen.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 60,
    "unitName": "M_tape_echo",
    "params": {
     "dry_wet": 100,
     "time_ratio": 25,
     "sync_on": 1,
     "s_note1": 8,
     "s_note2": 8,
     "time1": 19,
     "time2": 19,
     "delay_lag": 1,
     "output_level": 53,
     "tap1_level": 88,
     "tap2_level": 88,
     "feedback": 70,
     "hi_damp": 55,
     "lo_damp": 60,
     "trim": 80,
     "saturation": 55,
     "gain": 55,
     "gainshift": 5,
     "lfo_wave": 2,
     "lfo_depth": 15,
     "lfo_speed": 40,
     "lfo_reset": 0,
     "pre_lpf": 109,
     "spread": 100
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 7,
    "param": 5,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 0,
    "low": 40,
    "high": 100
   },
   {
    "source": 67,
    "chain": 2,
    "param": 11,
    "low": 40,
    "high": 72
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Master Pumper",
  "description": "Pumpen auf der ganzen Summe, auf Viertel. X stellt die Tiefe, Play setzt den Takt neu an. Ein Baustein, den Hacktribe in keinem Preset benutzt.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 53,
    "unitName": "M_level_mod",
    "params": {
     "amp_level": 127,
     "output_gain_adjust": 26,
     "level_mod_source": 4,
     "level_mod_int": 126,
     "level_mod_type": 0,
     "saturation": 1,
     "lfo_sync": 1,
     "lfo_speed": 33,
     "lfo_sync_note": 6,
     "lfo_phase": 27,
     "lfo_reset": 0,
     "lfo_reset_phase": 36
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 10,
    "param": 4,
    "low": 127,
    "high": 0
   },
   {
    "source": 65,
    "chain": 10,
    "param": 0,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 3,
    "low": 63,
    "high": 126
   },
   {
    "source": 74,
    "chain": 2,
    "param": 10,
    "low": 0,
    "high": 1
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Tremolo 1/8",
  "description": "Die ganze Summe schwankt in Achteln in der Lautstärke. X stellt die Tiefe. Ein Baustein, der in keinem Preset steht.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 52,
    "unitName": "M_tremolo",
    "params": {
     "dry_wet": 100,
     "mod_src": 0,
     "mod_int": 100,
     "lfo_wave": 2,
     "lfo_squdur": 50,
     "lfo_squlag": 0,
     "lfo_sync": 1,
     "lfo_speed": 66,
     "lfo_sync_note": 7,
     "lfo_shape": 25,
     "lfo_phase": 36,
     "lfo_reset": 0,
     "lfo_reset_phase": 18
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 10,
    "param": 4,
    "low": 127,
    "high": 0
   },
   {
    "source": 65,
    "chain": 10,
    "param": 0,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 2,
    "low": 0,
    "high": 127
   },
   {
    "source": 74,
    "chain": 2,
    "param": 11,
    "low": 0,
    "high": 1
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Wah 1/8",
  "description": "Ein Wah, das im Takt auf Achteln auf und zu geht. X stellt die Mitte, Y die Tiefe. Ein Baustein, den Hacktribe in keinem Preset benutzt.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 44,
    "unitName": "M_wah",
    "params": {
     "dry_wet": 100,
     "wah_type": 0,
     "mod_src": 0,
     "mod_int": 127,
     "control": 1,
     "env_select": 1,
     "env_response": 1,
     "env_sens": 127,
     "lfo_step": 0,
     "lfo_wave": 0,
     "lfo_sync": 1,
     "lfo_speed": 47,
     "lfo_syncnote": 7,
     "lfo_rch_degree": 19,
     "lfo_reset": 0,
     "lfo_resetphase": 0,
     "manual": 56
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 10,
    "param": 4,
    "low": 127,
    "high": 0
   },
   {
    "source": 65,
    "chain": 10,
    "param": 0,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 16,
    "low": 20,
    "high": 110
   },
   {
    "source": 67,
    "chain": 2,
    "param": 3,
    "low": 0,
    "high": 127
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Small Plate",
  "description": "Ein kurzer, heller Plattenhall. X mischt den Hall dazu. Ein Baustein, der in keinem Preset steht.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 57,
    "unitName": "M_dry_plate_reverb",
    "params": {
     "dry_wet": 50,
     "time": 45,
     "hi_damp": 61,
     "pre_delay": 51,
     "trim": 39,
     "trim2": 64,
     "lo_eq": 30,
     "hi_eq": 30,
     "pd_thru": 26
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 7,
    "param": 5,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 0,
    "low": 20,
    "high": 90
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Master Limiter",
  "description": "Ein Limiter auf der Summe, macht sie dichter. X dreht die Schwelle runter. Ein Baustein, der in keinem Preset steht.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 42,
    "unitName": "M_limiter",
    "params": {
     "dry_wet": 100,
     "envelope_select": 0,
     "threshold": 48,
     "attack": 0,
     "release": 8,
     "hold_time": 8,
     "tube_sat": 50,
     "output_gain": 54
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 10,
    "param": 4,
    "low": 127,
    "high": 0
   },
   {
    "source": 65,
    "chain": 10,
    "param": 0,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 2,
    "low": 52,
    "high": 30
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Bounce Gate 16",
  "description": "Macht aus jeder Note einen kurzen Schlag auf Sechzehntel: schneller Anschlag, kurzes Abklingen. Für knackige Bässe im Bouncy Techno. Der Takt läuft mit, Noten neben dem Raster werden angeschnitten. Regler von sanft bis hart, Play setzt den Takt neu an.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 21,
    "unitName": "I_level_mod",
    "params": {
     "amp_level": 127,
     "output_gain": 36,
     "level_mod_source": 4,
     "level_mod_int": 8,
     "level_mod_type": 0,
     "saturation": 1,
     "lfo_sync": 1,
     "lfo_speed": 33,
     "lfo_sync_note": 8,
     "lfo_reset": 0,
     "lfo_reset_phase": 18
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 74,
    "chain": 0,
    "param": 9,
    "low": 0,
    "high": 1
   },
   {
    "source": 66,
    "chain": 0,
    "param": 3,
    "low": 40,
    "high": 0
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Bounce Gate 8",
  "description": "Wie Bounce Gate 16, aber auf Achtel: ein längerer Schlag pro Note, für Bässe, die auf den Achteln springen. Der Takt läuft mit, Noten neben dem Raster werden angeschnitten. Regler von sanft bis hart, Play setzt den Takt neu an.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 21,
    "unitName": "I_level_mod",
    "params": {
     "amp_level": 127,
     "output_gain": 36,
     "level_mod_source": 4,
     "level_mod_int": 8,
     "level_mod_type": 0,
     "saturation": 1,
     "lfo_sync": 1,
     "lfo_speed": 33,
     "lfo_sync_note": 7,
     "lfo_reset": 0,
     "lfo_reset_phase": 18
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 74,
    "chain": 0,
    "param": 9,
    "low": 0,
    "high": 1
   },
   {
    "source": 66,
    "chain": 0,
    "param": 3,
    "low": 40,
    "high": 0
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Bass Enhancer",
  "description": "Viel Bass dazu und trotzdem sauber: ein Tiefen-Regal hebt an, die Tiefmitten gehen etwas zurück, der Limiter dahinter hält den Pegel. Der Regler dreht den Bass auf und nimmt dabei den Eingangspegel zurück.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 7,
    "unitName": "I_eq_4_band",
    "params": {
     "trim": 108,
     "b1_type": 2,
     "b2_type": 0,
     "b3_type": 0,
     "b4_type": 1,
     "b1_frequency": 12,
     "b1_q": 5,
     "b1_gain": 46,
     "b2_frequency": 22,
     "b2_q": 5,
     "b2_gain": 33,
     "b3_frequency": 48,
     "b3_q": 5,
     "b3_gain": 36,
     "b4_frequency": 54,
     "b4_q": 5,
     "b4_gain": 36
    }
   },
   {
    "stage": "ifx2",
    "unit": 5,
    "unitName": "I_limiter",
    "params": {
     "dry_wet": 100,
     "envelope_select": 0,
     "threshold": 44,
     "attack": 10,
     "release": 5,
     "hold_time": 7,
     "tubesat": 20,
     "output_gain": 52
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 7,
    "low": 36,
    "high": 60
   },
   {
    "source": 66,
    "chain": 0,
    "param": 0,
    "low": 118,
    "high": 96
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Hardtekk Kick",
  "description": "Ein Kick, der hart angezerrt wird: der Bass wird vor der Verzerrung angehoben und danach wieder aufgefüllt, ein Limiter fängt die Spitzen. Der Regler dreht die Verzerrung auf und nimmt dabei den Pegel zurück.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 15,
    "unitName": "I_distortion",
    "params": {
     "dry_wet": 0,
     "gain": 100,
     "pre_eq_frequency": 30,
     "pre_eq_q": 15,
     "pre_eq_gain": 44,
     "post_eq1_frequency": 12,
     "post_eq1_q": 5,
     "post_eq1_gain": 58,
     "post_eq2_frequency": 38,
     "post_eq2_q": 5,
     "post_eq2_gain": 30,
     "post_eq3_frequency": 52,
     "post_eq3_q": 5,
     "post_eq3_gain": 40,
     "output_level": 17
    }
   },
   {
    "stage": "ifx2",
    "unit": 5,
    "unitName": "I_limiter",
    "params": {
     "dry_wet": 100,
     "envelope_select": 0,
     "threshold": 44,
     "attack": 2,
     "release": 4,
     "hold_time": 4,
     "tubesat": 30,
     "output_gain": 52
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 80,
    "high": 125
   },
   {
    "source": 66,
    "chain": 0,
    "param": 14,
    "low": 18,
    "high": 14
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Tekk Kick Soft",
  "description": "Der weichere Kick: Acid Drive, dahinter ein EQ, der den Bass anhebt und oben einen Klick dazugibt. Der Regler dreht den Drive auf und nimmt dabei den Pegel zurück.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 16,
    "unitName": "I_acid_driver",
    "params": {
     "drive": 70,
     "output_level": 30
    }
   },
   {
    "stage": "ifx2",
    "unit": 6,
    "unitName": "I_eq_2_band",
    "params": {
     "trim": 100,
     "b1_type": 2,
     "b2_type": 0,
     "b1_frequency": 12,
     "b1_q": 5,
     "b1_gain": 48,
     "b2_frequency": 50,
     "b2_q": 5,
     "b2_gain": 40
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 0,
    "low": 40,
    "high": 100
   },
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 44,
    "high": 22
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Warm Drive",
  "description": "Leichte Sättigung, die den Klang wärmer und dichter macht: Acid Drive mit wenig Drive, dahinter ein EQ, der den Bass anhebt und die Höhen etwas nimmt. Der Regler dreht den Drive auf und nimmt dabei den Pegel zurück.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 16,
    "unitName": "I_acid_driver",
    "params": {
     "drive": 40,
     "output_level": 42
    }
   },
   {
    "stage": "ifx2",
    "unit": 6,
    "unitName": "I_eq_2_band",
    "params": {
     "trim": 127,
     "b1_type": 2,
     "b2_type": 1,
     "b1_frequency": 13,
     "b1_q": 5,
     "b1_gain": 40,
     "b2_frequency": 52,
     "b2_q": 5,
     "b2_gain": 31
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 0,
    "low": 20,
    "high": 70
   },
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 50,
    "high": 27
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Bass Drive",
  "description": "Verzerrung, die den Bass stehen lässt: mäßig Gain, der Tiefbass wird nach der Verzerrung wieder hochgezogen, das Zischeln oben gedämpft. Der Regler dreht den Gain auf.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 15,
    "unitName": "I_distortion",
    "params": {
     "dry_wet": 0,
     "gain": 56,
     "pre_eq_frequency": 35,
     "pre_eq_q": 15,
     "pre_eq_gain": 36,
     "post_eq1_frequency": 11,
     "post_eq1_q": 5,
     "post_eq1_gain": 54,
     "post_eq2_frequency": 30,
     "post_eq2_q": 5,
     "post_eq2_gain": 38,
     "post_eq3_frequency": 50,
     "post_eq3_q": 5,
     "post_eq3_gain": 26,
     "output_level": 16
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 30,
    "high": 90
   },
   {
    "source": 66,
    "chain": 0,
    "param": 14,
    "low": 20,
    "high": 14
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Scream Drive",
  "description": "Eine Verzerrung mit kräftig angehobenen Mitten, schreit nach vorn. Für Leads und Acid-Linien. Der Regler dreht den Gain auf.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 15,
    "unitName": "I_distortion",
    "params": {
     "dry_wet": 0,
     "gain": 96,
     "pre_eq_frequency": 36,
     "pre_eq_q": 20,
     "pre_eq_gain": 56,
     "post_eq1_frequency": 16,
     "post_eq1_q": 5,
     "post_eq1_gain": 30,
     "post_eq2_frequency": 44,
     "post_eq2_q": 8,
     "post_eq2_gain": 46,
     "post_eq3_frequency": 54,
     "post_eq3_q": 5,
     "post_eq3_gain": 28,
     "output_level": 14
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 64,
    "high": 110
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Tight Fuzz",
  "description": "Ein Fuzz mit weggenommenem Bass, klingt eng und bissig statt breit. Gut auf Drums und hohen Linien. Der Regler dreht den Gain auf.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 15,
    "unitName": "I_distortion",
    "params": {
     "dry_wet": 0,
     "gain": 88,
     "pre_eq_frequency": 35,
     "pre_eq_q": 15,
     "pre_eq_gain": 42,
     "post_eq1_frequency": 15,
     "post_eq1_q": 5,
     "post_eq1_gain": 20,
     "post_eq2_frequency": 42,
     "post_eq2_q": 5,
     "post_eq2_gain": 44,
     "post_eq3_frequency": 53,
     "post_eq3_q": 5,
     "post_eq3_gain": 22,
     "output_level": 15
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 1,
    "low": 60,
    "high": 110
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Bit Grinder",
  "description": "Zerhackt die Bittiefe, rau und digital. Der Regler geht von sauber bis kaputt und nimmt dabei etwas Pegel zurück.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 9,
    "unitName": "I_decimator",
    "params": {
     "dry_wet": 100,
     "pre_lpf_sw": 0,
     "pre_lpf": 127,
     "hi_damp": 120,
     "sample_freq": 127,
     "bit_depth": 8,
     "output_level": 90,
     "mask_type": 0
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 5,
    "low": 20,
    "high": 6
   },
   {
    "source": 66,
    "chain": 0,
    "param": 6,
    "low": 90,
    "high": 75
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Alias Crush",
  "description": "Senkt die Abtastrate: Aliasing, metallisch und hell. Der Regler dreht die Abtastrate runter.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 9,
    "unitName": "I_decimator",
    "params": {
     "dry_wet": 100,
     "pre_lpf_sw": 0,
     "pre_lpf": 127,
     "hi_damp": 110,
     "sample_freq": 60,
     "bit_depth": 20,
     "output_level": 90,
     "mask_type": 0
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 4,
    "low": 110,
    "high": 25
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Glue Comp",
  "description": "Ein Kompressor, der Bass und Drums zusammenhält, dahinter ein Limiter als Sicherung. Der Regler dreht die Schwelle runter und gleicht den Pegel mit aus.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 2,
    "unitName": "I_sr1_comp",
    "params": {
     "dry_wet": 100,
     "envelope_select": 0,
     "threshold": 40,
     "ratio": 8,
     "knee": 6,
     "attack": 11,
     "release": 5,
     "hold_time": 0,
     "tube_sat": 10,
     "output_gain": 52
    }
   },
   {
    "stage": "ifx2",
    "unit": 5,
    "unitName": "I_limiter",
    "params": {
     "dry_wet": 100,
     "envelope_select": 0,
     "threshold": 52,
     "attack": 0,
     "release": 3,
     "hold_time": 3,
     "tubesat": 0,
     "output_gain": 48
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 2,
    "low": 46,
    "high": 26
   },
   {
    "source": 66,
    "chain": 0,
    "param": 9,
    "low": 50,
    "high": 58
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Tilt EQ",
  "description": "Kippt den Klang: links Tiefen runter und Höhen hoch (heller), rechts umgekehrt (dunkler). In der Mitte bleibt er, wie er ist.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 6,
    "unitName": "I_eq_2_band",
    "params": {
     "trim": 127,
     "b1_type": 2,
     "b2_type": 1,
     "b1_frequency": 18,
     "b1_q": 5,
     "b1_gain": 36,
     "b2_frequency": 38,
     "b2_q": 5,
     "b2_gain": 36
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 5,
    "low": 24,
    "high": 48
   },
   {
    "source": 66,
    "chain": 0,
    "param": 8,
    "low": 48,
    "high": 24
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Mix Clean Up",
  "description": "Räumt eine Spur auf: nimmt das Rumpeln ganz unten und das Dröhnen in den Tiefmitten raus und gibt oben einen Hauch Luft dazu. Der Regler nimmt mehr aus den Tiefmitten.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 7,
    "unitName": "I_eq_4_band",
    "params": {
     "trim": 127,
     "b1_type": 2,
     "b2_type": 0,
     "b3_type": 0,
     "b4_type": 1,
     "b1_frequency": 5,
     "b1_q": 5,
     "b1_gain": 24,
     "b2_frequency": 22,
     "b2_q": 5,
     "b2_gain": 34,
     "b3_frequency": 48,
     "b3_q": 5,
     "b3_gain": 36,
     "b4_frequency": 54,
     "b4_q": 5,
     "b4_gain": 38
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 0,
    "param": 10,
    "low": 40,
    "high": 26
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Master Glue",
  "description": "Ein Kompressor auf der Summe, hält den Mix zusammen. X dreht die Schwelle runter. Ein Baustein, den Hacktribe in keinem Preset benutzt.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 41,
    "unitName": "M_sr1_comp",
    "params": {
     "dry_wet": 100,
     "envelope_select": 0,
     "threshold": 42,
     "ratio": 8,
     "knee": 6,
     "attack": 11,
     "release": 5,
     "hold_time": 0,
     "tube_sat": 0,
     "output_gain": 50
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 10,
    "param": 4,
    "low": 127,
    "high": 0
   },
   {
    "source": 65,
    "chain": 10,
    "param": 0,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 2,
    "low": 46,
    "high": 30
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Master Tilt",
  "description": "Kippt die ganze Summe: X nach links macht sie heller, nach rechts dunkler, um sechs Stufen. Ein Baustein, den Hacktribe in keinem Preset benutzt.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 43,
    "unitName": "M_eq_4_band",
    "params": {
     "dry_wet": 100,
     "trim": 127,
     "b1_type": 2,
     "b2_type": 0,
     "b3_type": 0,
     "b4_type": 1,
     "b1_frequency": 18,
     "b1_q": 5,
     "b1_gain": 36,
     "b2_frequency": 33,
     "b2_q": 5,
     "b2_gain": 36,
     "b3_frequency": 48,
     "b3_q": 5,
     "b3_gain": 36,
     "b4_frequency": 38,
     "b4_q": 5,
     "b4_gain": 36
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 10,
    "param": 4,
    "low": 127,
    "high": 0
   },
   {
    "source": 65,
    "chain": 10,
    "param": 0,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 8,
    "low": 30,
    "high": 42
   },
   {
    "source": 66,
    "chain": 2,
    "param": 17,
    "low": 42,
    "high": 30
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Master Warmth",
  "description": "Leichte Röhrensättigung auf der Summe: etwas Wärme und Dichte, ohne zu verzerren. X dreht die Sättigung auf.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 47,
    "unitName": "M_tubepre",
    "params": {
     "dry_wet": 100,
     "tube1_gain": 52,
     "tube1_sat": 20,
     "tube2_gain": 52,
     "tube2_sat": 30,
     "lo_cut1": 0,
     "hi_cut1": 127,
     "lo_cut2": 0,
     "hi_cut2": 127,
     "tube1_bias": 30,
     "tube1_phase": 0,
     "tube2_bias": 40,
     "output_level": 84
    }
   }
  ],
  "map": [
   {
    "source": 65,
    "chain": 10,
    "param": 4,
    "low": 127,
    "high": 0
   },
   {
    "source": 65,
    "chain": 10,
    "param": 0,
    "low": 0,
    "high": 127
   },
   {
    "source": 66,
    "chain": 2,
    "param": 2,
    "low": 20,
    "high": 70
   },
   {
    "source": 66,
    "chain": 2,
    "param": 4,
    "low": 30,
    "high": 80
   }
  ],
  "creator": "Kuhler Buhler"
 }
]);

export const MOD_CATALOG = Object.freeze([
 {
  "kind": "mod",
  "name": "Filter Wobble",
  "description": "Eine Sinuswelle bewegt den Filter auf und zu. Klassischer Wobble-Bass.",
  "depth": 64,
  "speed": 40,
  "curve": 6,
  "slots": [
   {
    "source": 1,
    "target": 3,
    "lo": 0,
    "hi": 60,
    "follow": 1
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mod",
  "name": "Soft Vibrato",
  "description": "Die Tonhöhe schwankt leicht hin und her, wie ein Sänger mit Vibrato.",
  "depth": 40,
  "speed": 70,
  "curve": 6,
  "slots": [
   {
    "source": 1,
    "target": 1,
    "lo": 0,
    "hi": 12,
    "follow": 1
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mod",
  "name": "Bounce Pluck",
  "description": "Jede Note bekommt eine kurze Hüllkurve auf den Filter und einen kleinen Schub auf die Lautstärke: der Filter schnappt auf und gleich wieder zu. Macht lange Bässe zu kurzen Plucks. MOD. DEPTH stellt die Stärke, MOD. SPEED die Länge. Auf einen Platz der EG+-Arten legen (1 bis 6).",
  "depth": 100,
  "speed": 36,
  "curve": 2,
  "slots": [
   {
    "source": 0,
    "target": 3,
    "lo": 0,
    "hi": 50,
    "follow": 1
   },
   {
    "source": 0,
    "target": 8,
    "lo": 0,
    "hi": 24,
    "follow": 1
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mod",
  "name": "Bounce Pitch",
  "description": "Jede Note springt kurz um etwa einen Halbton nach oben und fällt zurück, dazu ein kleiner Lautstärke-Schub. Gibt dem Bass ein Federn. Auf einen Platz der EG+-Arten legen (1 bis 6).",
  "depth": 80,
  "speed": 26,
  "curve": 2,
  "slots": [
   {
    "source": 0,
    "target": 1,
    "lo": 0,
    "hi": 16,
    "follow": 1
   },
   {
    "source": 0,
    "target": 8,
    "lo": 0,
    "hi": 24,
    "follow": 1
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mod",
  "name": "Kick Drop",
  "description": "Die Tonhöhe startet hoch und fällt in Millisekunden ab, dazu ein Schub auf die Lautstärke: baut den Schlag eines Kicks. Auf einen Platz der EG+-Arten legen (1 bis 6).",
  "depth": 100,
  "speed": 26,
  "curve": 2,
  "slots": [
   {
    "source": 0,
    "target": 1,
    "lo": 0,
    "hi": 56,
    "follow": 1
   },
   {
    "source": 0,
    "target": 8,
    "lo": 0,
    "hi": 16,
    "follow": 1
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mod",
  "name": "Kick Click",
  "description": "Ein sehr kurzer, hoher Pitch-Sprung am Anfang: der Klick vorn am Kick. Mit Kick Drop auf zwei Parts oder allein auf einem Kick mit eigenem Körper. Auf einen Platz der EG+-Arten legen (1 bis 6).",
  "depth": 100,
  "speed": 12,
  "curve": 2,
  "slots": [
   {
    "source": 0,
    "target": 1,
    "lo": 0,
    "hi": 63,
    "follow": 1
   },
   {
    "source": 0,
    "target": 8,
    "lo": 0,
    "hi": 28,
    "follow": 1
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   },
   {
    "source": 2,
    "target": 0,
    "lo": 0,
    "hi": 0,
    "follow": 0
   }
  ],
  "creator": "Kuhler Buhler"
 }
]);
