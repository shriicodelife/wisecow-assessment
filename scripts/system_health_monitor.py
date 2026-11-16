#!/usr/bin/env python3
"""
System Health Monitoring Script
--------------------------------
Monitors system health metrics including CPU usage, Memory consumption,
Disk space utilization, and running process counts. Triggers configurable
alerts whenever defined thresholds are exceeded.

Usage:
    python system_health_monitor.py [--cpu-threshold 80] [--mem-threshold 80] [--disk-threshold 80]
"""

import argparse
import datetime
import logging
import os
import shutil
import sys
import time

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


def setup_logger(log_file: str = "system_health.log") -> logging.Logger:
    """Configures multi-handler logging to console and persistent log file."""
    logger = logging.getLogger("SystemHealthMonitor")
    logger.setLevel(logging.INFO)

    # Format
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    try:
        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning("Could not set up file handler: %s", e)

    return logger


def get_cpu_usage() -> float:
    """Returns current system-wide CPU usage percentage."""
    if PSUTIL_AVAILABLE:
        return psutil.cpu_percent(interval=1)
    if hasattr(os, "getloadavg"):
        # 1-minute load average normalized by CPU cores
        cores = os.cpu_count() or 1
        load = os.getloadavg()[0]
        return min(round((load / cores) * 100, 2), 100.0)
    return 0.0


def get_memory_usage() -> tuple[float, float, float]:
    """
    Returns (used_percent, total_gb, available_gb).
    """
    if PSUTIL_AVAILABLE:
        mem = psutil.virtual_memory()
        return (
            mem.percent,
            round(mem.total / (1024 ** 3), 2),
            round(mem.available / (1024 ** 3), 2),
        )

    # Fallback for Linux procfs
    if os.path.exists("/proc/meminfo"):
        mem_info = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]
                    mem_info[key] = int(val)
        total = mem_info.get("MemTotal", 1)
        available = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
        used_pct = round(((total - available) / total) * 100, 2)
        return (
            used_pct,
            round(total / (1024 * 1024), 2),
            round(available / (1024 * 1024), 2),
        )

    return (0.0, 0.0, 0.0)


def get_disk_usage(path: str = "/") -> tuple[float, float, float]:
    """
    Returns (used_percent, total_gb, free_gb) for the target path.
    """
    target_path = path if os.path.exists(path) else (os.path.splitdrive(os.getcwd())[0] or "/")
    disk = shutil.disk_usage(target_path)
    used_pct = round((disk.used / disk.total) * 100, 2)
    total_gb = round(disk.total / (1024 ** 3), 2)
    free_gb = round(disk.free / (1024 ** 3), 2)
    return used_pct, total_gb, free_gb


def get_running_processes_count() -> int:
    """Returns number of active running processes."""
    if PSUTIL_AVAILABLE:
        return len(psutil.pids())
    if sys.platform != "win32" and os.path.exists("/proc"):
        return len([pid for pid in os.listdir("/proc") if pid.isdigit()])
    return 0


def get_top_processes(limit: int = 5) -> list[dict]:
    """Returns top resource consuming processes."""
    if not PSUTIL_AVAILABLE:
        return []

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            pinfo = proc.info
            processes.append(pinfo)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return sorted(processes, key=lambda p: (p.get("cpu_percent") or 0.0), reverse=True)[:limit]


def check_health(
    logger: logging.Logger,
    cpu_threshold: float,
    mem_threshold: float,
    disk_threshold: float,
    proc_threshold: int,
    disk_path: str,
) -> bool:
    """
    Performs a single health check sweep and triggers alerts if any threshold is exceeded.
    Returns True if system is healthy, False if any alert was triggered.
    """
    alerts = []

    # 1. CPU Check
    cpu_pct = get_cpu_usage()
    if cpu_pct > cpu_threshold:
        alerts.append(f"HIGH CPU USAGE: {cpu_pct:.1f}% (Threshold: {cpu_threshold}%)")

    # 2. Memory Check
    mem_pct, mem_total, mem_avail = get_memory_usage()
    if mem_pct > mem_threshold:
        alerts.append(
            f"HIGH MEMORY USAGE: {mem_pct:.1f}% used of {mem_total} GB "
            f"({mem_avail} GB available) (Threshold: {mem_threshold}%)"
        )

    # 3. Disk Check
    disk_pct, disk_total, disk_free = get_disk_usage(disk_path)
    if disk_pct > disk_threshold:
        alerts.append(
            f"HIGH DISK USAGE: {disk_pct:.1f}% used on '{disk_path}' of {disk_total} GB "
            f"({disk_free} GB free) (Threshold: {disk_threshold}%)"
        )

    # 4. Running Processes Check
    proc_count = get_running_processes_count()
    if proc_threshold > 0 and proc_count > proc_threshold:
        alerts.append(
            f"HIGH PROCESS COUNT: {proc_count} running processes (Threshold: {proc_threshold})"
        )

    # Logging summary
    logger.info(
        "Health Metrics -> CPU: %.1f%% | Mem: %.1f%% (%s GB free) | Disk: %.1f%% (%s GB free) | Procs: %d",
        cpu_pct,
        mem_pct,
        mem_avail,
        disk_pct,
        disk_free,
        proc_count,
    )

    # Process Alerts
    if alerts:
        logger.error("!!! SYSTEM HEALTH ALERTS DETECTED !!!")
        for alert in alerts:
            logger.error("[ALERT] %s", alert)

        top_procs = get_top_processes(3)
        if top_procs:
            logger.warning("Top CPU consuming processes:")
            for p in top_procs:
                logger.warning(
                    "  - PID %s (%s): CPU %.1f%%, MEM %.1f%%",
                    p.get("pid"),
                    p.get("name"),
                    p.get("cpu_percent") or 0.0,
                    p.get("memory_percent") or 0.0,
                )
        return False

    logger.info("System is healthy. All metrics within acceptable thresholds.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive Linux/Unix System Health Monitor"
    )
    parser.add_argument(
        "--cpu-threshold",
        type=float,
        default=80.0,
        help="CPU utilization alert threshold in percent (default: 80.0)",
    )
    parser.add_argument(
        "--mem-threshold",
        type=float,
        default=80.0,
        help="Memory utilization alert threshold in percent (default: 80.0)",
    )
    parser.add_argument(
        "--disk-threshold",
        type=float,
        default=80.0,
        help="Disk utilization alert threshold in percent (default: 80.0)",
    )
    parser.add_argument(
        "--proc-threshold",
        type=int,
        default=300,
        help="Process count alert threshold (default: 300, 0 to disable)",
    )
    parser.add_argument(
        "--disk-path",
        type=str,
        default="/",
        help="Disk path / mount point to check (default: '/')",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Continuous monitoring interval in seconds (default: 0 = run once)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="system_health.log",
        help="Log file path (default: system_health.log)",
    )

    args = parser.parse_args()
    logger = setup_logger(args.log_file)

    logger.info("Starting System Health Monitor")
    logger.info(
        "Thresholds: CPU > %.1f%% | Memory > %.1f%% | Disk > %.1f%% | Procs > %d",
        args.cpu_threshold,
        args.mem_threshold,
        args.disk_threshold,
        args.proc_threshold,
    )

    if not PSUTIL_AVAILABLE:
        logger.warning(
            "Note: 'psutil' module is not installed. For detailed per-process metrics, run: pip install psutil"
        )

    try:
        while True:
            check_health(
                logger=logger,
                cpu_threshold=args.cpu_threshold,
                mem_threshold=args.mem_threshold,
                disk_threshold=args.disk_threshold,
                proc_threshold=args.proc_threshold,
                disk_path=args.disk_path,
            )
            if args.interval <= 0:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("System Health Monitor stopped by user.")


if __name__ == "__main__":
    main()
