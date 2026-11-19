"""Sample host-wide CPU, RAM and disk use and track observed child processes."""

import ctypes
import os
from pathlib import Path
import shutil
from threading import Event, Thread
from time import perf_counter


def system():
    if os.name != "nt":
        fields = list(map(int, Path("/proc/stat").read_text().splitlines()[0].split()[1:9]))
        memory = {line.split(":")[0]: int(line.split()[1]) * 1024
                  for line in Path("/proc/meminfo").read_text().splitlines() if " kB" in line}
        return sum(fields), fields[3] + fields[4], memory["MemTotal"] - memory["MemAvailable"], memory["MemTotal"]

    ticks = [ctypes.c_ulonglong() for _ in range(3)]
    if not ctypes.windll.kernel32.GetSystemTimes(*(ctypes.byref(value) for value in ticks)):
        raise ctypes.WinError()
    idle, kernel, user = (value.value for value in ticks)
    # MEMORYSTATUSEX is two DWORDs followed by seven DWORDLONGs.
    memory_type = type("MemoryStatus", (ctypes.Structure,), {"_fields_": [
        ("length", ctypes.c_uint32), ("load", ctypes.c_uint32),
        ("physical", ctypes.c_uint64), ("available", ctypes.c_uint64),
        ("remaining", ctypes.c_uint64 * 5),
    ]})
    memory = memory_type()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError()
    return kernel + user, idle, memory.physical - memory.available, memory.physical


def processes():
    if os.name != "nt":
        table = {}
        for proc in Path("/proc").iterdir():
            if not proc.name.isdecimal():
                continue
            try:
                name, _, fields = (proc / "stat").read_text(errors="replace").rpartition(")")
                table[int(proc.name)] = int(fields.split()[1]), name.partition("(")[2]
            except (OSError, ValueError, IndexError):
                continue
        return table

    from ctypes import wintypes as win

    class Entry(ctypes.Structure):
        _fields_ = [("size", win.DWORD), ("usage", win.DWORD), ("pid", win.DWORD),
                    ("heap", ctypes.c_size_t), ("module", win.DWORD), ("threads", win.DWORD),
                    ("parent", win.DWORD), ("priority", win.LONG), ("flags", win.DWORD),
                    ("name", win.WCHAR * 260)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [win.DWORD, win.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = win.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        getattr(kernel, name).argtypes = [win.HANDLE, ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes = [win.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    table = {}
    entry = Entry()
    entry.size = ctypes.sizeof(entry)
    try:
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            table[entry.pid] = entry.parent, entry.name
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    return table


def descendants(table, roots):
    found = set(roots)
    while True:
        children = {pid for pid, (parent, _) in table.items() if parent in found} - found
        if not children:
            return found
        found.update(children)


class Sampler:
    def __init__(self, pid, volumes):
        self.seen = {pid}
        self.volumes = volumes
        self.rows = []
        self.errors = []
        self.done = Event()
        self.started = perf_counter()
        self.thread = Thread(target=self.sample, daemon=True)
        self.thread.start()

    def sample(self):
        previous = None
        while True:
            try:
                total, idle, used, capacity = system()
                cpu = None
                if previous and total > previous[0]:
                    cpu = 100 * (1 - (idle - previous[1]) / (total - previous[0]))
                previous = total, idle
                self.rows.append({
                    "seconds": perf_counter() - self.started,
                    "cpu_percent": cpu,
                    "ram_used_bytes": used,
                    "ram_total_bytes": capacity,
                    "disk_used_bytes": {name: shutil.disk_usage(path).used
                                        for name, path in self.volumes.items()},
                })
                self.seen = descendants(processes(), self.seen)
            except (OSError, ValueError, KeyError) as exc:
                self.errors.append(type(exc).__name__)
            if self.done.wait(1):
                return

    def finish(self):
        self.done.set()
        self.thread.join()
        try:
            table = processes()
            observed = descendants(table, self.seen)
            return [name for pid, (_, name) in table.items() if pid in observed
                    and any(term in name.lower() for term in ("python", "bazel", "java"))]
        except OSError:
            return None
