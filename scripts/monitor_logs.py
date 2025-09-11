#!/usr/bin/env python3
"""
Log File Monitor

A simple script to monitor the log files for MongoDB and Word document operations.
This helps with debugging performance issues in real-time.

Usage:
    python scripts/monitor_logs.py
"""

import argparse
import os
import re
import sys
import time
from typing import Dict, List, Optional

# ANSI color codes for terminal output
COLORS = {
    "RESET": "\033[0m",
    "RED": "\033[31m",
    "GREEN": "\033[32m",
    "YELLOW": "\033[33m",
    "BLUE": "\033[34m",
    "MAGENTA": "\033[35m",
    "CYAN": "\033[36m",
    "WHITE": "\033[37m",
    "BOLD": "\033[1m",
    "UNDERLINE": "\033[4m",
}


def color_text(text: str, color: str) -> str:
    """Add color to text for terminal output."""
    return f"{COLORS.get(color.upper(), '')}{text}{COLORS['RESET']}"


def get_log_files() -> Dict[str, str]:
    """Get all log files in the logs directory."""
    log_files = {}
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

    if not os.path.exists(log_dir):
        print(f"Log directory not found: {log_dir}")
        return log_files

    for filename in os.listdir(log_dir):
        if filename.endswith(".log"):
            log_files[filename] = os.path.join(log_dir, filename)

    return log_files


def tail_file(file_path: str, num_lines: int = 10) -> List[str]:
    """Read the last n lines from a file."""
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()
            return lines[-num_lines:] if lines else []
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []


def monitor_logs(files: Dict[str, str], interval: int = 2, filter_text: Optional[str] = None) -> None:
    """Monitor log files for changes and print new lines."""
    print(color_text("Log File Monitor", "BOLD"))
    print(color_text("=" * 80, "BOLD"))
    print(f"Monitoring {len(files)} log files:")

    for name, path in files.items():
        print(f"- {color_text(name, 'CYAN')}: {path}")

    print(color_text("=" * 80, "BOLD"))

    if filter_text:
        print(f"Filtering for: {color_text(filter_text, 'YELLOW')}")

    print(color_text("=" * 80, "BOLD"))
    print("Press Ctrl+C to exit")
    print(color_text("=" * 80, "BOLD"))

    # Keep track of the last position in each file
    file_positions = {path: os.path.getsize(path) if os.path.exists(path) else 0 for name, path in files.items()}

    try:
        while True:
            has_updates = False

            for name, path in files.items():
                if not os.path.exists(path):
                    continue

                # Check if file has been modified
                current_size = os.path.getsize(path)
                if current_size > file_positions[path]:
                    has_updates = True

                    # Read only the new content
                    with open(path, "r") as f:
                        f.seek(file_positions[path])
                        new_content = f.read()

                    # Update position
                    file_positions[path] = current_size

                    # Process and print new lines
                    for line in new_content.splitlines():
                        if filter_text and filter_text.lower() not in line.lower():
                            continue

                        # Parse timestamp if present
                        timestamp_match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
                        if timestamp_match:
                            timestamp = timestamp_match.group(1)
                            rest_of_line = line[len(timestamp) :]
                            print(f"{color_text(timestamp, 'GREEN')} {color_text(name, 'CYAN')}{rest_of_line}")
                        else:
                            print(f"{color_text(name, 'CYAN')}: {line}")

            # If nothing was updated, wait before checking again
            if not has_updates:
                time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopping log monitor.")


def main() -> None:
    """Main function to parse arguments and start monitoring."""
    parser = argparse.ArgumentParser(description="Monitor log files for changes")
    parser.add_argument("--filter", type=str, help="Only show lines containing this text")
    parser.add_argument("--interval", type=int, default=1, help="Check interval in seconds (default: 1)")
    parser.add_argument("--files", type=str, nargs="+", help="Specific log files to monitor (without path)")
    args = parser.parse_args()

    all_log_files = get_log_files()

    if not all_log_files:
        print("No log files found. Make sure the MCP coordinator has been run at least once.")
        sys.exit(1)

    # Filter files if specified
    if args.files:
        files_to_monitor = {name: path for name, path in all_log_files.items() if name in args.files}
        if not files_to_monitor:
            print(f"None of the specified files were found. Available files: {list(all_log_files.keys())}")
            sys.exit(1)
    else:
        files_to_monitor = all_log_files

    monitor_logs(files_to_monitor, args.interval, args.filter)


if __name__ == "__main__":
    main()
