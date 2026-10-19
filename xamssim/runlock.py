"""One xamssim process per run id at a time (Geant4 and the chain write the same folders).

    with run_lock("example_cs137_sept"):
        ...

A lock file <data>/locks/<run id>.lock holds the process id; a lock of a process that no longer runs is taken over.
"""
from __future__ import annotations

import contextlib
import os

from .config import DATA

LOCKS = DATA / "locks"


class RunLocked(RuntimeError):
    pass


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextlib.contextmanager
def run_lock(run_id: str):
    LOCKS.mkdir(parents=True, exist_ok=True)
    f = LOCKS / f"{run_id}.lock"
    for _ in range(2):
        try:
            fd = os.open(f, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                pid = int(f.read_text().strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid and _alive(pid) and pid != os.getpid():
                raise RunLocked(f"run {run_id} is being processed by another xamssim (process {pid}); wait for it "
                                f"(or remove {f} if that process is not xamssim)")
            f.unlink(missing_ok=True)                                  # stale lock
    else:
        raise RunLocked(f"could not lock run {run_id} ({f})")
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        f.unlink(missing_ok=True)
