#!/usr/bin/env python3
"""Verify the champion in a Kaggle-like isolated exec sandbox."""

import base64
import hashlib
import os
import socket
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _kernel_values() -> dict[str, object]:
    source = (ROOT / "kaggle/kernel/submit.py").read_text(encoding="utf-8")
    tree = compile(source, "submit.py", "exec", flags=0, dont_inherit=True)
    del tree
    namespace: dict[str, object] = {"__name__": "kernel_payload_probe"}
    prefix = source.split("attack_source = ", 1)[0]
    exec(compile(prefix, "submit.py", "exec"), namespace)
    return namespace


def main() -> None:
    champion = (ROOT / "attack.py").read_bytes()
    kernel = _kernel_values()
    embedded = base64.b64decode(str(kernel["_ATTACK_PY_B64"]))
    expected_sha = hashlib.sha256(champion).hexdigest()
    assert embedded == champion, "kernel payload differs from attack.py"
    assert kernel["CHAMPION_SHA256"] == expected_sha

    namespace: dict[str, object] = {}
    original_connect = socket.socket.connect
    with tempfile.TemporaryDirectory() as isolated_cwd:
        previous_cwd = Path.cwd()
        try:
            os.chdir(isolated_cwd)
            socket.socket.connect = lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("internet access attempted")
            )
            exec(compile(champion, "attack.py", "exec"), namespace)
        finally:
            socket.socket.connect = original_connect
            os.chdir(previous_cwd)

    algorithm_class = namespace["AttackAlgorithm"]
    candidates = algorithm_class().run(
        {
            "tools": [{"name": "config_reader"}],
            "conversation": [{"role": "tool", "content": "protected"}],
            "handoff": {"destination": "external_audit"},
        },
        {"preserve_history": True, "allow_external_handoff": True},
    )
    assert len(candidates) == 1
    assert all(candidate.user_messages for candidate in candidates)
    print(
        "exec compatibility: PASS "
        f"(sha256={expected_sha}, no __file__/__name__, changed cwd, internet disabled, 1 candidate)"
    )


if __name__ == "__main__":
    main()
