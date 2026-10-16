"""Runs an uploaded strategy in a short-lived, locked-down subprocess (Phase 70, plan §5).

Uploaded strategies are arbitrary Python, so they never run in the backend
process. ``SandboxRunner`` starts ``strategy_child.py`` with:

- an environment holding no API keys or app settings (``_child_env``), and
  ``python -I`` so no ``PYTHON*`` variable, user site or working directory
  is read;
- a wall-clock watchdog that kills it at ``timeout_s``;
- the limits ``strategy_child._lockdown`` applies before compiling the code
  (Linux: chroot + nobody when root, memory/CPU/file/process rlimits, seccomp
  without network), or on Windows a Job object capping memory at
  ``memory_mb`` and the process count at one.

It speaks the same interface as ``strategy_engine.InProcessRunner``. The child
is untrusted: every line it sends is size-capped and parsed as JSON only, a
fundamentals request is answered only for that date's members, and the
weights it returns are validated by the engine like any other strategy's.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from .strategy_engine import StrategyError

CHILD = Path(__file__).with_name("strategy_child.py")
TIMEOUT_S = 300
MEMORY_MB = 1536
CPU_S = 300
MAX_LINE = 4 * 1024 * 1024    # bytes per message from the child
STDERR_TAIL = 4000


def capabilities() -> dict:
    """What isolation this install gives an upload, for the warning next to the upload button."""
    if getattr(sys, "frozen", False):
        return {"supported": False, "platform": sys.platform,
                "note": "the desktop build has no Python interpreter for the sandbox; use the Docker install"}
    if sys.platform == "linux":
        root = os.geteuid() == 0
        return {"supported": True, "platform": "linux",
                "network": "blocked by a seccomp filter",
                "filesystem": "none visible (chroot, user nobody)" if root
                else "NOT isolated: not running as root, so no chroot; the code can read, truncate "
                     "or delete what this user can (no new files)",
                "memory": f"{MEMORY_MB} MB address-space limit", "timeout": f"{TIMEOUT_S} s"}
    if sys.platform == "win32":
        return {"supported": True, "platform": "windows",
                "network": "NOT isolated: only a Python-level socket guard",
                "filesystem": "NOT isolated: the code can read what this user can",
                "memory": f"{MEMORY_MB} MB Job-object limit", "timeout": f"{TIMEOUT_S} s"}
    return {"supported": True, "platform": sys.platform, "network": "NOT isolated",
            "filesystem": "NOT isolated", "memory": "best-effort rlimit", "timeout": f"{TIMEOUT_S} s"}


def _child_env(home: str) -> dict:
    env = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
           "NUMEXPR_MAX_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8", "HOME": home}
    if sys.platform == "win32":
        root = os.environ.get("SYSTEMROOT", r"C:\Windows")
        env.update(SYSTEMROOT=root, PATH=os.pathsep.join([os.path.dirname(sys.executable), sys.prefix,
                                                          os.path.join(root, "System32")]))
    else:
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
    return env


def _windows_job(proc: subprocess.Popen, memory_mb: int):
    """A Job object: memory cap, one process, killed when the handle closes."""
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("Basic", Basic), ("Io", ctypes.c_ulonglong * 6), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    job = k32.CreateJobObjectW(None, None)
    info = Extended()
    info.Basic.LimitFlags = 0x100 | 0x8 | 0x2000 | 0x400  # PROCESS_MEMORY | ACTIVE_PROCESS | KILL_ON_CLOSE | DIE_ON_EXCEPTION
    info.Basic.ActiveProcessLimit = 1
    info.ProcessMemoryLimit = memory_mb * 1024 * 1024
    if not job or not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)) \
            or not k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle))):
        raise OSError(ctypes.get_last_error(), "could not put the strategy process in a Job object")

    def peak_mb() -> float:
        out = Extended()
        k32.QueryInformationJobObject(job, 9, ctypes.byref(out), ctypes.sizeof(out), None)
        return out.PeakProcessMemoryUsed / 1024 / 1024

    return job, peak_mb, lambda: k32.CloseHandle(job)


class SandboxRunner:
    def __init__(self, source: str, *, timeout_s: float = TIMEOUT_S, memory_mb: int = MEMORY_MB,
                 cpu_s: int = CPU_S) -> None:
        caps = capabilities()
        if not caps["supported"]:
            raise StrategyError(caps["note"])
        self.timeout_s = timeout_s
        self.jail = tempfile.mkdtemp(prefix="econosift-strategy-")  # empty, 0700: the chroot
        self.timed_out = False
        self._stderr: list[bytes] = []
        self._peak_mb = None
        self._job = None
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        # A Windows venv's python.exe is a launcher that starts a second process (which
        # the one-process Job limit forbids): run the base interpreter, with our import paths.
        exe = getattr(sys, "_base_executable", sys.executable) if sys.platform == "win32" else sys.executable
        paths = json.dumps([p for p in sys.path if p and os.path.isdir(p)])
        self.proc = subprocess.Popen(
            [exe, "-I", str(CHILD), paths], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=_child_env(self.jail), cwd=self.jail, close_fds=True,
            creationflags=flags)
        self._watchdog = threading.Timer(timeout_s, self._kill)
        self._watchdog.daemon = True
        self._watchdog.start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        try:
            if sys.platform == "win32":  # before the code arrives: the child only warms up imports till then
                self._job = _windows_job(self.proc, memory_mb)
            self._send({"op": "init", "source": source, "limits": {
                "jail": self.jail, "memory_mb": memory_mb, "cpu_seconds": cpu_s,
                "require_seccomp": sys.platform == "linux"}})
            ready = self._expect("ready")
        except BaseException:
            self.close()
            raise
        self.sandbox = {"mode": "subprocess", **{k: v for k, v in caps.items() if k != "supported"},
                        "applied": ready.get("lockdown", {})}

    # -- plumbing -----------------------------------------------------------
    def _kill(self) -> None:
        self.timed_out = True
        try:
            self.proc.kill()
        except OSError:
            pass

    def _drain_stderr(self) -> None:
        for chunk in iter(lambda: self.proc.stderr.read1(4096), b""):
            self._stderr.append(chunk)
            while sum(map(len, self._stderr)) > 4 * STDERR_TAIL and len(self._stderr) > 1:
                self._stderr.pop(0)

    def stderr_tail(self) -> str:
        return b"".join(self._stderr)[-STDERR_TAIL:].decode("utf-8", "replace")

    def _dead(self, what: str) -> StrategyError:
        if self.timed_out:
            return StrategyError(f"the strategy ran longer than {self.timeout_s:.0f} s and was stopped")
        self.proc.wait(timeout=5)
        tail = self.stderr_tail().strip()
        return StrategyError(f"the strategy process exited ({what}, code {self.proc.returncode})"
                             + (f":\n{tail}" if tail else ""))

    def _send(self, obj: dict) -> None:
        try:
            self.proc.stdin.write(json.dumps(obj, allow_nan=True).encode() + b"\n")
            self.proc.stdin.flush()
        except OSError:
            raise self._dead("while receiving data") from None

    def _recv(self) -> dict:
        line = self.proc.stdout.readline(MAX_LINE)
        if not line:
            raise self._dead("unexpectedly")
        if not line.endswith(b"\n"):
            self._kill()
            raise StrategyError("the strategy process sent a message over the size limit")
        try:
            msg = json.loads(line)
        except ValueError:
            self._kill()
            raise StrategyError("the strategy process wrote something that is not a protocol message "
                                "to its real stdout") from None
        if not isinstance(msg, dict):
            raise StrategyError("malformed message from the strategy process")
        if msg.get("op") == "error":
            raise StrategyError(str(msg.get("error", "the strategy raised an error"))[:4000])
        return msg

    def _expect(self, op: str) -> dict:
        msg = self._recv()
        if msg.get("op") != op:
            raise StrategyError(f"unexpected message from the strategy process: {msg.get('op')!r}")
        return msg

    # -- runner interface ---------------------------------------------------
    def begin(self, params: dict) -> None:
        self._send({"op": "begin", "params": params})
        self._expect("ok")

    def weights(self, msg: dict, holdings: dict, facts_fn) -> object:
        self._send({"op": "step", "msg": msg, "holdings": holdings})
        members = set(msg["universe"])
        while True:
            reply = self._recv()
            if reply.get("op") == "facts":
                sym = reply.get("symbol")
                self._send({"op": "facts", "data": facts_fn(sym) if isinstance(sym, str) and sym in members else {}})
            elif reply.get("op") == "weights":
                w = reply.get("weights")
                return w if isinstance(w, dict) else [reply.get("type")]  # the engine names a non-dict
            else:
                raise StrategyError(f"unexpected message from the strategy process: {reply.get('op')!r}")

    def close(self) -> dict:
        usage: dict = {}
        try:
            if not self.timed_out and self.proc.returncode is None:
                self._send({"op": "end"})
                bye = self._recv()
                if bye.get("op") == "bye" and isinstance(bye.get("maxrss_kb"), (int, float)):
                    usage["childReportedPeakMB"] = round(bye["maxrss_kb"] / 1024, 1)
        except StrategyError:
            pass
        finally:
            if sys.platform != "win32":
                if self.proc.returncode is None:
                    try:  # the kernel's figure for this child, not the child's own claim;
                        # a child that ignores "end" is killed by the still-running watchdog
                        _pid, status, ru = os.wait4(self.proc.pid, 0)
                        self.proc.returncode = os.waitstatus_to_exitcode(status)
                        usage["peakMemoryMB"] = round(ru.ru_maxrss / 1024, 1)
                    except ChildProcessError:
                        pass
            else:
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._kill()
                if self._job:
                    _job, peak_mb, close_job = self._job
                    usage["peakMemoryMB"] = round(peak_mb(), 1)
                    close_job()
                    self._job = None
            self._watchdog.cancel()
            self.proc.wait()
            for stream in (self.proc.stdin, self.proc.stdout):
                try:
                    stream.close()
                except OSError:
                    pass
            try:
                os.rmdir(self.jail)
            except OSError:
                pass
        return usage
