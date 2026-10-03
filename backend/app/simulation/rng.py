"""(De)serializing random.Random state into JSON-friendly lists."""

from __future__ import annotations

import random
from typing import Any


def dump_rng(rng: random.Random) -> list[Any]:
    version, internal, gauss = rng.getstate()
    return [version, list(internal), gauss]


def load_rng(state: list[Any], fallback_seed: int = 0) -> random.Random:
    rng = random.Random(fallback_seed)
    if state:
        rng.setstate((state[0], tuple(state[1]), state[2]))
    return rng
