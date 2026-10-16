# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hält lokale Firmwarekopien und fremde Buildartefakte aus Git-Verzeichnissen."""
from pathlib import Path


def external_output(path):
    target = Path(path).resolve()
    root = Path(__file__).resolve().parents[2]
    if target == root or root in target.parents:
        raise ValueError("Ausgabepfad muss außerhalb des Repos liegen")
    if any((parent / ".git").exists() for parent in (target, *target.parents)):
        raise ValueError("Ausgabepfad muss außerhalb eines Git-Repos liegen")
    return target
