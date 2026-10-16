# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prüft Doom Bedienung ausschließlich mit echten Panelnachrichten."""


class ControlsScenario:
    ACTIONS = [
        ("turn", 12, 8, 5),
        ("forward", 11, 8, 5),
        ("fire", 2, 12, 5),
        ("use", 3, 8, 5),
        ("main-menu", 9, 3, 3),
        ("new-game-menu", 0, 3, 3),
        ("episode-down", 15, 3, 3),
        ("choose-episode", 0, 3, 3),
        ("choose-skill", 0, 3, 3),
        ("wait-level2", None, 0, 0),
        ("reopen-main", 9, 3, 3),
        ("navigate-quit", 11, 3, 3),
        ("quit-dialog", 0, 3, 3),
        ("confirm-quit", 0, 3, 3),
    ]

    def __init__(self):
        self.checks = []
        self.events = []
        self.states = []
        self.game_frame = None
        self._index = -1
        self._phase = "await-play"
        self._tic = 0
        self._before = None
        self._use_seen = False
        self._main_menu = None
        self._episode_menu = None
        self._skill_menu = None
        self._level2_frame = None
        self._quit_dialog = None
        self._quit_dialog_before = None

    def _record(self, name, machine, current, engine):
        result = dict(name=name, seconds=machine.time_ns / 1e9,
                      state={key: current.get(key) for key in ["stage", "error", "frames", "gametic", "viewangle"]},
                      engine=dict(engine) if engine is not None else None)
        self.states.append(result)
        return result

    def _send(self, machine, current, index, down, name):
        message = [0, index, int(down), 0, 0]
        machine.send(message)
        self.events.append(dict(name=name, seconds=machine.time_ns / 1e9,
                                gametic=current.get("gametic"), message=message))

    def _check(self, name, ok, before, after, evidence="observed"):
        self.checks.append(dict(id=name, ok=bool(ok), before=before, after=after, evidence=evidence))
        if not ok:
            self._phase = "failed"
        return bool(ok)

    def _start_next(self, machine, current, engine):
        self._index += 1
        if self._index >= len(self.ACTIONS):
            self._phase = "failed"
            return
        name, index, _, _ = self.ACTIONS[self._index]
        self._before = self._record(name + "-before", machine, current, engine)
        self._tic = current["gametic"]
        if index is None:
            self._phase = "level2"
            self._level2_frame = None
        else:
            self._send(machine, current, index, True, name)
            self._phase = "held"

    def _evaluate(self, name, machine, current, engine):
        before, after = self._before, self._record(name + "-after", machine, current, engine)
        old = before["engine"]
        alive = engine.get("health", 0) > 0
        menu = bool(engine.get("menu"))
        pointer = engine.get("current_menu")
        if name == "turn":
            ok = alive and before["state"]["viewangle"] != current["viewangle"]
        elif name == "forward":
            ok = alive and (old.get("x"), old.get("y")) != (engine.get("x"), engine.get("y"))
        elif name == "fire":
            ok = alive and engine["ammo_clip"] < old["ammo_clip"]
        elif name == "use":
            ok = alive and self._use_seen and not engine.get("usedown")
        elif name == "main-menu":
            ok = menu
            self._main_menu = pointer
        elif name == "new-game-menu":
            ok = menu and pointer != self._main_menu
            self._episode_menu = pointer
        elif name == "episode-down":
            ok = menu and pointer == self._episode_menu
        elif name == "choose-episode":
            ok = menu and pointer != self._episode_menu
            self._skill_menu = pointer
        elif name == "choose-skill":
            ok = not menu
        elif name == "reopen-main":
            ok = menu and pointer == self._main_menu
        elif name == "navigate-quit":
            ok = menu and pointer == self._main_menu
        elif name == "quit-dialog":
            self._quit_dialog = after
            self._quit_dialog_before = before
            if "message" not in engine:
                return True
            ok = menu and bool(engine["message"]) and bool(engine.get("message_needs_input", True))
        elif name == "confirm-quit":
            return True
        else:
            ok = False
        return self._check(name, ok, before, after)

    def _stopped(self, machine, current, engine):
        expected = self._index >= 0 and self.ACTIONS[self._index][0] == "confirm-quit"
        after = self._record("stopped", machine, current, engine)
        if not self._check("quit-stopped", expected and current.get("error") == 0,
                           self._before, after):
            return True
        if self._quit_dialog is not None and "message" not in self._quit_dialog["engine"]:
            self._check("quit-dialog", True, self._quit_dialog_before, after, "derived-from-menu-quit-stopped")
        self._send(machine, current, 0, False, "confirm-quit")
        message = [6, 1, 0, 0, 0]
        machine.send(message)
        self.events.append(dict(name="power-off", seconds=machine.time_ns / 1e9,
                                gametic=current.get("gametic"), message=message))
        self._phase = "power"
        return False

    def step(self, machine, current, engine):
        if self._phase == "failed":
            return True
        if self._phase == "power":
            if not machine.powered:
                self._check("power-off", True, self.states[-1],
                            self._record("powered-off", machine, current, engine))
                self._phase = "done"
                return True
            return False
        if self._phase == "done":
            return True
        if current.get("stage", 0) & 0x80000000:
            self._check("engine-error", False, self._before,
                        self._record("error", machine, current, engine))
            return True
        if current.get("stage") == 6:
            return self._stopped(machine, current, engine)
        if engine is None:
            return False
        if self._phase == "await-play":
            if current.get("stage") != 5 or current.get("gametic", 0) < 5 or engine.get("leveltime", 0) < 5:
                return False
            initial = self._record("initial-play", machine, current, engine)
            if not self._check("initial-play", engine.get("health", 0) > 0 and not engine.get("menu"), None, initial):
                return True
            self._start_next(machine, current, engine)
            return False
        name, index, hold, settle = self.ACTIONS[self._index]
        if name == "use" and engine.get("usedown") and not self._use_seen:
            self._use_seen = True
            self._record("use-held-observed", machine, current, engine)
        if self._phase == "level2":
            if engine.get("episode") != 2 or engine.get("map") != 1 or engine.get("leveltime", 0) < 5:
                return False
            if self._level2_frame is None:
                self._level2_frame = current["frames"]
                return False
            if current["frames"] < self._level2_frame + 3:
                return False
            after = self._record("level2-play", machine, current, engine)
            if not self._check("new-game-e2m1", engine.get("health", 0) > 0 and not engine.get("menu"), self._before, after):
                return True
            self.game_frame = bytes(value for row in machine.fb for value in row)
            if not self._check("level2-spi-frame", len(self.game_frame) == 1024 and 0 < sum(value.bit_count() for value in self.game_frame) < 8192,
                               self._before, after):
                return True
            self._start_next(machine, current, engine)
            return False
        if self._phase == "held":
            if current["gametic"] - self._tic >= hold:
                self._send(machine, current, index, False, name)
                self._tic = current["gametic"]
                self._phase = "settling"
            return False
        if self._phase == "settling" and current["gametic"] - self._tic >= settle:
            if not self._evaluate(name, machine, current, engine):
                return True
            if name == "confirm-quit":
                self._phase = "await-stopped"
            else:
                self._start_next(machine, current, engine)
        return False
