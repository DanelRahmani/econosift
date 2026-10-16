"""The sandboxed strategy process (Phase 70, plan §5). Run as a script, never imported by the app.

``strategy_sandbox`` starts it as ``python -I strategy_child.py`` with an
environment that holds no API keys, and talks to it over stdin/stdout, one JSON
message per line. It loads numpy/pandas and the harness's ``strategy_context``,
then locks itself down **before** it compiles or runs the uploaded code:

Linux (Docker, a source install):
- as root (Docker): ``chroot`` into an empty directory, then drop to ``nobody``,
  so the database, ``.env`` and the rest of the filesystem are out of reach;
- resource limits: address space (memory), CPU seconds, no new files, no new
  processes or threads;
- ``no_new_privs`` + a seccomp filter that fails ``socket()``, ``io_uring`` and
  ``ptrace`` with EPERM: no network, whatever the code does.
Windows (desktop or a source run): the parent puts this process in a Job object
with a memory cap and a one-process limit; there is no network or filesystem
isolation, only a Python-level socket guard that determined code can get
around (see ``strategy_sandbox.capabilities``).

The data the strategy can see arrives only through ``Panel`` messages, which
the parent cuts at each rebalance date, so nothing in this process's memory is
from after the date being decided.
"""
import ctypes
import json
import os
import struct
import sys
import traceback

if len(sys.argv) > 1:  # the parent's import paths (python -I ignores PYTHONPATH and venvs on Windows)
    sys.path[1:1] = [p for p in json.loads(sys.argv[1]) if p not in sys.path]

# Loaded before the lockdown: once chrooted, nothing more can be imported from disk.
import bisect, collections, datetime, decimal, fractions, functools, heapq, itertools  # noqa: E401,F401
import linecache, math, operator, random, re, statistics  # noqa: E401,F401
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I leaves the script's own folder off
from strategy_context import Panel, StrategyContext  # noqa: E402

NOBODY = 65534
_ARCH = {"x86_64": (0xC000003E, {"socket": 41, "ptrace": 101, "io_uring_setup": 425}),
         "aarch64": (0xC00000B7, {"socket": 198, "ptrace": 117, "io_uring_setup": 425})}


def _warm_pandas() -> None:
    """Touch the pandas paths strategies use, so their lazy imports happen before the chroot."""
    idx = pd.bdate_range("2020-01-01", periods=40)
    df = pd.DataFrame(np.arange(80, dtype=float).reshape(40, 2) + 1, index=idx, columns=["a", "b"])
    df.pct_change().rolling(5).std().ewm(span=5).mean().rank(axis=1).corr()
    df.resample("ME").last().shift(1).diff().cumprod().clip(0, 1).nlargest(1, "a")
    df.iloc[-1].nlargest(1).sort_values().to_dict()
    df.stack().groupby(level=1).mean().describe()
    pd.qcut(df["a"], 3, labels=False)
    np.linalg.lstsq(df.to_numpy(), df["a"].to_numpy(), rcond=None)
    repr(df), str(df.iloc[0])


def _seccomp() -> None:
    """Install a filter: socket/ptrace/io_uring -> EPERM, a foreign ABI -> kill, the rest allowed."""
    arch, nrs = _ARCH[os.uname().machine]
    libc = ctypes.CDLL(None, use_errno=True)
    LD, JEQ, JGE, RET = 0x20, 0x15, 0x35, 0x06          # BPF_LD|W|ABS, BPF_JMP|JEQ|K, JGE, BPF_RET|K
    ALLOW, KILL, EPERM = 0x7FFF0000, 0x80000000, 0x00050000 | 1
    prog = [(LD, 0, 0, 4), (JEQ, 1, 0, arch), (RET, 0, 0, KILL),   # seccomp_data.arch
            (LD, 0, 0, 0), (JGE, 0, 1, 0x40000000), (RET, 0, 0, KILL)]  # .nr; x32 ABI -> kill
    for nr in nrs.values():
        prog += [(JEQ, 0, 1, nr), (RET, 0, 0, EPERM)]
    prog.append((RET, 0, 0, ALLOW))
    buf = b"".join(struct.pack("HBBI", *ins) for ins in prog)
    filt = ctypes.create_string_buffer(buf)

    class Fprog(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]

    fprog = Fprog(len(prog), ctypes.addressof(filt))
    if libc.prctl(38, 1, 0, 0, 0) != 0:                    # PR_SET_NO_NEW_PRIVS
        raise OSError(ctypes.get_errno(), "PR_SET_NO_NEW_PRIVS failed")
    if libc.prctl(22, 2, ctypes.byref(fprog), 0, 0) != 0:  # PR_SET_SECCOMP, SECCOMP_MODE_FILTER
        raise OSError(ctypes.get_errno(), "seccomp filter refused")


def _socket_guard() -> None:
    """Python-level only: the one network barrier where the OS gives none (Windows)."""
    import socket

    def refused(*_a, **_k):
        raise PermissionError("network access is disabled for strategies")

    socket.socket = socket.create_connection = socket.getaddrinfo = refused  # type: ignore[assignment]


def _lockdown(cfg: dict) -> dict:
    done = {"network": "python-guard", "filesystem": "not isolated", "memory": "parent job object"}
    _socket_guard()
    if sys.platform != "linux":
        return done
    import resource

    if os.geteuid() == 0 and cfg.get("jail"):
        os.chroot(cfg["jail"])
        os.chdir("/")
        os.setgroups([])
        os.setgid(NOBODY)
        os.setuid(NOBODY)
        done["filesystem"] = "chroot (empty), user nobody"
    mem = int(cfg["memory_mb"]) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    resource.setrlimit(resource.RLIMIT_CPU, (int(cfg["cpu_seconds"]), int(cfg["cpu_seconds"]) + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    done["memory"] = f"RLIMIT_AS {cfg['memory_mb']} MB"
    if os.uname().machine in _ARCH:
        _seccomp()
        done["network"] = "seccomp: socket() refused"
    elif cfg.get("require_seccomp"):
        raise OSError(f"no seccomp filter for {os.uname().machine}: refusing to run untrusted code")
    return done


def main() -> None:
    _warm_pandas()
    proto_in = sys.stdin.buffer
    proto_out = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)  # the strategy's print() goes to stderr, not into the protocol
    sys.stdout = sys.stderr

    def send(obj) -> None:
        proto_out.write(json.dumps(obj, allow_nan=True).encode() + b"\n")

    def recv() -> dict:
        line = proto_in.readline()
        if not line:
            raise SystemExit(0)
        return json.loads(line)

    init = recv()
    source = init["source"]
    try:
        info = _lockdown(init["limits"])
    except Exception as exc:  # never run the code without the limits it was promised
        send({"op": "error", "error": f"sandbox lockdown failed: {exc}"})
        return
    linecache.cache["strategy.py"] = (len(source), None, source.splitlines(True), "strategy.py")
    send({"op": "ready", "lockdown": info})

    panel, fn, params = Panel(), None, {}
    while True:
        msg = recv()
        op = msg.get("op")
        try:
            if op == "begin":
                ns = {"__name__": "strategy"}
                exec(compile(source, "strategy.py", "exec"), ns)  # fresh module state per pass
                fn, params = ns["generate_weights"], msg.get("params") or {}
                send({"op": "ok"})
            elif op == "step":
                step = msg["msg"]
                if "panel" in step:
                    panel.apply(step["panel"])

                def facts(symbol):
                    send({"op": "facts", "symbol": symbol})
                    return recv()["data"]

                ctx = StrategyContext(panel, step, params, msg.get("holdings"), facts)
                weights = fn(ctx)
                if isinstance(weights, dict):
                    weights = {str(k): (float(v) if isinstance(v, (int, float, np.number)) else repr(v))
                               for k, v in weights.items()}
                    send({"op": "weights", "weights": weights})
                else:
                    send({"op": "weights", "weights": None, "type": type(weights).__name__})
            elif op == "end":
                usage = {}
                if sys.platform != "win32":
                    import resource
                    usage["maxrss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                send({"op": "bye", **usage})
                return
        except Exception as exc:  # the strategy's own frames only, not this file's
            te = traceback.TracebackException.from_exception(exc)
            te.stack = traceback.StackSummary.from_list([f for f in te.stack if f.filename == "strategy.py"])
            send({"op": "error", "error": "".join(te.format())[-4000:]})


if __name__ == "__main__":
    main()
