"""Watch mode must not change when player-mode features are added: same seeds, same companies."""

from __future__ import annotations

import json

from app.tools import golden


def test_watch_mode_matches_golden_runs():
    want = json.loads(golden.FIXTURE.read_text())
    got = golden.run_all()
    assert got == want, "watch mode changed; if intended, regenerate with `python -m app.tools.golden --write`"
