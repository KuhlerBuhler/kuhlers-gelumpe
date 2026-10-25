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
     "dry_wet": 122,
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
     "fb_depth": 70,
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
    "low": 70,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 70,
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
     "fb_depth": 60,
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
    "low": 60,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 60,
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
     "fb_depth": 65,
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
    "low": 65,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 65,
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
     "wet_level": 90,
     "input_trim": 127,
     "tempo_sync": 1,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 62,
     "on_syncnote": 1,
     "fb_depth": 80,
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
    "low": 80,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 80,
    "high": 88
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
     "fb_depth": 35,
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
    "low": 35,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 35,
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
     "fb_depth": 70,
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
    "low": 70,
    "high": 10
   },
   {
    "source": 68,
    "chain": 0,
    "param": 8,
    "low": 70,
    "high": 88
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Loud Distortion",
  "description": "Die Distortion so laut wie der trockene Klang. Das Werkspreset steht auf Ausgangspegel 11, hier 40, die Verzerrung wie ab Werk. Der Regler dreht die Verzerrung.",
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
     "output_level": 40
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
     "output_level": 30
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
     "output_level": 35
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
  "description": "Der Overdrive weiter aufgedreht, der Pegel wie ab Werk. Der Regler dreht den Drive.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 16,
    "unitName": "I_acid_driver",
    "params": {
     "drive": 70,
     "output_level": 40
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
     "feedback": 85,
     "hi_damp": 55,
     "lo_damp": 60,
     "trim": 80,
     "saturation": 80,
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
    "low": 50,
    "high": 88
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
     "output_gain_adjust": 30,
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
 }
]);
