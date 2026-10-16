"""Phase 70 item 4: uploaded strategies run in a locked-down subprocess."""
import functools
import os
import sys

import pytest

from backend.services import strategy_engine as se
from backend.services.strategy_sandbox import SandboxRunner, capabilities
from tests.test_strategy_engine import EXAMPLE, _store  # noqa: F401  (the stored universe fixture)

LINUX_ROOT = sys.platform == "linux" and os.geteuid() == 0


def _run(source, **runner_kw):
    return se.backtest(source, start="2024-01-01", end="2024-06-30",
                       runner_factory=functools.partial(SandboxRunner, **runner_kw))


def _probe(body: str) -> str:
    """A strategy that runs ``body`` on its first rebalance, then holds cash."""
    return "def generate_weights(ctx):\n" + "".join(f"    {line}\n" for line in body.splitlines()) + "    return {}\n"


def test_the_example_runs_in_the_sandbox_and_matches_the_in_process_run():
    sandboxed = _run(EXAMPLE)
    trusted = se.backtest(EXAMPLE, start="2024-01-01", end="2024-06-30")
    assert sandboxed["equityCurve"] == trusted["equityCurve"]
    assert sandboxed["sandbox"]["mode"] == "subprocess" and sandboxed["sandbox"]["peakMemoryMB"] > 0


def test_the_child_environment_holds_no_keys(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "secret-for-test")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-for-test")
    res = _run(_probe("import os\nassert not [k for k in os.environ if 'KEY' in k or 'TOKEN' in k], dict(os.environ)"))
    assert res["available"]


def test_network_is_refused():
    with pytest.raises(se.StrategyError, match="network access is disabled|Operation not permitted"):
        _run(_probe("import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=2)"))


@pytest.mark.skipif(sys.platform != "linux", reason="seccomp is Linux-only")
def test_a_raw_socket_past_the_python_guard_is_refused_by_the_kernel():
    with pytest.raises(se.StrategyError, match="Operation not permitted"):
        _run(_probe("import _socket\n_socket.socket()"))


@pytest.mark.skipif(not LINUX_ROOT, reason="the chroot needs a root parent (Docker)")
def test_the_database_env_file_and_other_processes_are_out_of_reach():
    for body in ("open('/app/.env').read()", "open('/app/data/econosift.db', 'rb').read(16)",
                 "open('/proc/1/environ').read()", "import os\nos.listdir('/')"):
        with pytest.raises(se.StrategyError, match="Error|denied|No such file"):
            _run(_probe(body))
    with pytest.raises(se.StrategyError, match="Resource temporarily unavailable|BlockingIOError"):
        _run(_probe("import os\nos.fork()"))


def test_a_runaway_strategy_is_stopped_at_the_timeout():
    with pytest.raises(se.StrategyError, match="longer than 5 s"):
        _run(_probe("while True:\n    pass"), timeout_s=5)


def test_memory_is_capped():
    with pytest.raises(se.StrategyError):
        _run(_probe("block = bytearray(3 * 1024 ** 3)"), memory_mb=1200)


def test_printing_does_not_break_the_protocol_and_errors_come_back_with_a_traceback():
    assert _run(_probe("print('{\"op\": \"weights\", \"weights\": {\"X\": 9}}')"))["available"]
    with pytest.raises(se.StrategyError, match=r'(?s)^Traceback[^\n]*\n  File "strategy\.py", line 2.*ZeroDivisionError'):
        _run(_probe("1 / 0"))


def test_capabilities_say_what_is_and_is_not_isolated():
    caps = capabilities()
    assert caps["supported"] and "network" in caps and "filesystem" in caps
    if sys.platform == "win32":
        assert caps["network"].startswith("NOT isolated")
