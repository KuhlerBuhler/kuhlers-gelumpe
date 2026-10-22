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
  "kind": "mfx",
  "name": "Große Halle",
  "description": "Ein langer, weicher Hall wie in einer Kirche. Das Touchpad (X) dreht den Hall von wenig bis viel.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 54,
    "unitName": "M_hall_reverb",
    "params": {
     "dry_wet": 70,
     "time": 100,
     "hi_damp": 92,
     "pre_delay": 38,
     "trim": 48,
     "trim2": 127,
     "lo_eq": 30,
     "hi_eq": 30,
     "pd_thru": 26
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 2,
    "param": 0,
    "low": 10,
    "high": 110
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Bandecho",
  "description": "Ein warmes Echo wie von einer alten Bandmaschine, die Wiederholungen werden dumpfer.",
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
     "hi_damp": 77,
     "lo_damp": 48,
     "trim": 80,
     "saturation": 53,
     "gain": 55,
     "gainshift": 5,
     "lfo_wave": 2,
     "lfo_depth": 0,
     "lfo_speed": 127,
     "lfo_reset": 0,
     "pre_lpf": 109,
     "spread": 100
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 2,
    "param": 0,
    "low": 0,
    "high": 100
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "mfx",
  "name": "Lo-Fi",
  "description": "Macht den Klang rau und digital, wie ein alter Sampler. Das Touchpad (X) senkt die Abtastrate.",
  "stages": [
   {
    "stage": "mfx",
    "unit": 62,
    "unitName": "M_decimator",
    "params": {
     "dry_wet": 100,
     "pre_lpf_sw": 0,
     "pre_lpf": 127,
     "hi_damp": 127,
     "sample_freq": 45,
     "bit_depth": 8,
     "output_level": 127,
     "mask_type": 0,
     "mod_src": 0,
     "mod_int": 0,
     "wave": 1,
     "squ_dur": 50,
     "lfo_reset": 0,
     "reset_phase": 18,
     "sync_on": 0,
     "off_freq": 34,
     "on_sync_note": 4
    }
   }
  ],
  "map": [
   {
    "source": 66,
    "chain": 2,
    "param": 4,
    "low": 127,
    "high": 20
   }
  ],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Sanfter Chorus",
  "description": "Macht eine Spur breiter und schwebender. Gut auf Flächen und Akkorden.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 17,
    "unitName": "I_chorus",
    "params": {
     "dry_wet": 50,
     "mod_src": 0,
     "mod_int": 64,
     "lfo_wave": 1,
     "lfo_sync": 0,
     "lfo_speed": 28,
     "lfo_sync_note": 6,
     "lfo_phase": 0,
     "lfo_reset": 0,
     "lfo_reset_phase": 36,
     "pre_leq_gain": 0,
     "pre_leq_frequency": 0,
     "pre_heq_gain": 0,
     "pre_heq_frequency": 0,
     "l_delay": 46,
     "r_delay": 0,
     "lodamp": 0,
     "hidamp": 0,
     "spread": 0
    }
   },
   {
    "stage": "ifx2",
    "unit": 0,
    "unitName": "nofx_thru",
    "params": {}
   }
  ],
  "map": [],
  "creator": "Kuhler Buhler"
 },
 {
  "kind": "ifx",
  "name": "Kurzes Echo",
  "description": "Ein kurzes Echo auf einer Spur, zum Beispiel für Snare oder Stimme.",
  "stages": [
   {
    "stage": "ifx1",
    "unit": 24,
    "unitName": "I_short_delay",
    "params": {
     "dry_level": 120,
     "wet_level": 30,
     "input_trim": 127,
     "tempo_sync": 0,
     "off_time_ratio": 65,
     "off_delay_time": 24,
     "on_time_ratio": 35,
     "on_syncnote": 17,
     "fb_depth": 36,
     "high_damp": 0,
     "low_damp": 0,
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
  "map": [],
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
  "name": "Sanftes Vibrato",
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
  "name": "Pumpen",
  "description": "Die Hüllkurve zieht die Lautstärke nach jedem Schlag kurz runter, wie Sidechain.",
  "depth": 80,
  "speed": 30,
  "curve": 0,
  "slots": [
   {
    "source": 0,
    "target": 8,
    "lo": 0,
    "hi": -60,
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
