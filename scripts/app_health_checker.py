#!/usr/bin/env python3
"""
Application Health Checker Script
---------------------------------
Periodically checks the uptime, availability, and response latency of an application
via HTTP/HTTPS requests. Determines whether the application is 'UP' or 'DOWN'
based on HTTP status codes and response timeliness.

Usage:
    python app_health_checker.py --url http://localhost:4499 [--expected-status 200] [--timeout 5]
"""

import argparse
import datetime
import logging
import sys
import time
import urllib.error
import urllib.request


def setup_logger(log_file: str = "app_health.log") -> logging.Logger:
    """Configures multi-handler logging to console and persistent log file."""
    logger = logging.getLogger("AppHealthChecker")
    logger.setLevel(logging.INFO)

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


def check_application_health(
    url: str,
    expected_status: int = 200,
    timeout: float = 5.0,
    retries: int = 2,
    retry_delay: float = 1.0,
) -> tuple[bool, int | None, float, str]:
    """
    Checks the target URL with optional retries.
    Returns: (is_up, status_code, latency_ms, message)
    """
    last_error = ""

    for attempt in range(1, retries + 2):
        start_time = time.perf_counter()
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "AppHealthChecker/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                latency = round((time.perf_counter() - start_time) * 1000, 2)
                status_code = response.getcode()

                if status_code == expected_status:
                    return True, status_code, latency, "OK"
                else:
                    return (
                        False,
                        status_code,
                        latency,
                        f"Unexpected status code {status_code} (Expected {expected_status})",
                    )

        except urllib.error.HTTPError as e:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            if e.code == expected_status:
                return True, e.code, latency, "OK"
            last_error = f"HTTP Error {e.code}: {e.reason}"

        except urllib.error.URLError as e:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            last_error = f"Connection Error: {e.reason}"

        except TimeoutError:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            last_error = f"Request timed out after {timeout}s"

        except Exception as e:
            latency = round((time.perf_counter() - start_time) * 1000, 2)
            last_error = f"Unexpected Error: {str(e)}"

        if attempt <= retries:
            time.sleep(retry_delay)

    return False, None, latency, last_error


def run_check(
    logger: logging.Logger,
    url: str,
    expected_status: int,
    timeout: float,
    retries: int,
) -> bool:
    """Executes a health check run and logs formatted output."""
    is_up, status_code, latency_ms, message = check_application_health(
        url=url,
        expected_status=expected_status,
        timeout=timeout,
        retries=retries,
    )

    if is_up:
        logger.info(
            "[STATUS: UP] Target: %s | HTTP %s | Latency: %.2f ms | Details: %s",
            url,
            status_code,
            latency_ms,
            message,
        )
        return True
    else:
        status_str = str(status_code) if status_code is not None else "N/A"
        logger.error(
            "[STATUS: DOWN] Target: %s | HTTP %s | Latency: %.2f ms | Details: %s",
            url,
            status_str,
            latency_ms,
            message,
        )
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Application Uptime and Health Checker"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:4499",
        help="Target application URL to monitor (default: http://localhost:4499)",
    )
    parser.add_argument(
        "--expected-status",
        type=int,
        default=200,
        help="Expected HTTP status code for a healthy application (default: 200)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="HTTP request timeout in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Number of retries before marking as DOWN (default: 1)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Monitoring interval in seconds (default: 0 = run once)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default="app_health.log",
        help="Log file path (default: app_health.log)",
    )

    args = parser.parse_args()
    logger = setup_logger(args.log_file)

    logger.info("Starting Application Health Checker for URL: %s", args.url)
    logger.info(
        "Config: Expected Status=%d | Timeout=%.1fs | Retries=%d | Interval=%ds",
        args.expected_status,
        args.timeout,
        args.retries,
        args.interval,
    )

    try:
        while True:
            healthy = run_check(
                logger=logger,
                url=args.url,
                expected_status=args.expected_status,
                timeout=args.timeout,
                retries=args.retries,
            )
            if args.interval <= 0:
                sys.exit(0 if healthy else 1)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logger.info("Application Health Checker stopped by user.")


if __name__ == "__main__":
    main()
