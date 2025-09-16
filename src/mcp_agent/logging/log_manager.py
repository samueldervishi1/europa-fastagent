#!/usr/bin/env python3

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List


class LogManager:
    """
    Manages log files with rotation, cleanup, and analysis features
    """

    def __init__(self, logs_dir: Path = Path("logs")):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(exist_ok=True)

    def rotate_logs(self, max_age_days: int = 7, max_size_mb: int = 100):
        """
        Rotate old log files based on age and size

        Args:
            max_age_days: Maximum age of log files in days
            max_size_mb: Maximum size of log directory in MB
        """
        print(f"Rotating logs older than {max_age_days} days or exceeding {max_size_mb}MB...")

        cutoff_date = datetime.now() - timedelta(days=max_age_days)

        session_logs = list(self.logs_dir.glob("session_*.log"))
        archived_count = 0

        for log_file in session_logs:
            try:
                filename = log_file.stem
                date_str = filename.split("_", 1)[1].split("_")[0]
                file_date = datetime.strptime(date_str, "%Y%m%d")

                if file_date < cutoff_date:
                    archive_dir = self.logs_dir / "archived"
                    archive_dir.mkdir(exist_ok=True)

                    shutil.move(log_file, archive_dir / log_file.name)
                    archived_count += 1

            except (ValueError, IndexError) as e:
                print(f"Warning: Could not parse date from {log_file.name}: {e}")
                continue

        if archived_count > 0:
            print(f"Archived {archived_count} old session logs")

        total_size_mb = self._calculate_directory_size() / (1024 * 1024)
        if total_size_mb > max_size_mb:
            self._compress_old_logs()

    def _calculate_directory_size(self) -> int:
        """Calculate total size of logs directory in bytes"""
        total_size = 0
        for file_path in self.logs_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size

    def _compress_old_logs(self):
        """Compress old log files to save space"""
        import gzip

        cutoff = datetime.now() - timedelta(days=1)

        for log_file in self.logs_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff.timestamp():
                try:
                    compressed_file = log_file.with_suffix(".log.gz")

                    with open(log_file, "rb") as f_in:
                        with gzip.open(compressed_file, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    log_file.unlink()
                    print(f"Compressed {log_file.name}")

                except Exception as e:
                    print(f"Failed to compress {log_file.name}: {e}")

    def analyze_errors(self, days: int = 7) -> Dict:
        """
        Analyze error patterns from the last N days

        Returns:
            Dictionary with error analysis
        """
        analysis = {"total_errors": 0, "error_types": {}, "error_timeline": [], "top_error_sources": {}, "critical_errors": []}

        json_errors_file = self.logs_dir / "errors.jsonl"
        if not json_errors_file.exists():
            return analysis

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        try:
            with open(json_errors_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        error_data = json.loads(line.strip())
                        error_time = datetime.fromisoformat(error_data["timestamp"].replace("Z", "+00:00"))

                        if error_time < cutoff_date:
                            continue

                        analysis["total_errors"] += 1

                        if "exception" in error_data:
                            error_type = error_data["exception"]["type"]
                            analysis["error_types"][error_type] = analysis["error_types"].get(error_type, 0) + 1

                        analysis["error_timeline"].append(
                            {
                                "timestamp": error_data["timestamp"],
                                "message": error_data["message"][:100] + "..."
                                if len(error_data["message"]) > 100
                                else error_data["message"],
                            }
                        )

                        if "context" in error_data and "function" in error_data["context"]:
                            func_name = error_data["context"]["function"]
                            analysis["top_error_sources"][func_name] = analysis["top_error_sources"].get(func_name, 0) + 1

                        if any(keyword in error_data["message"].lower() for keyword in ["fatal", "critical", "crash", "abort"]):
                            analysis["critical_errors"].append(
                                {
                                    "timestamp": error_data["timestamp"],
                                    "message": error_data["message"],
                                    "type": error_data.get("exception", {}).get("type", "Unknown"),
                                }
                            )

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            print(f"Error analyzing errors: {e}")

        return analysis

    def generate_health_report(self) -> str:
        """Generate a health report of the application"""
        report = []
        report.append("=" * 60)
        report.append("EUROPA HEALTH REPORT")
        report.append("=" * 60)

        log_files = self.get_log_file_info()
        report.append(f"Log Files: {len(log_files)}")

        total_size = self._calculate_directory_size() / (1024 * 1024)
        report.append(f"Total Log Size: {total_size:.2f} MB")

        error_analysis = self.analyze_errors(7)
        report.append(f"Errors (7 days): {error_analysis['total_errors']}")

        if error_analysis["error_types"]:
            report.append("\nTop Error Types:")
            for error_type, count in sorted(error_analysis["error_types"].items(), key=lambda x: x[1], reverse=True)[:5]:
                report.append(f"  {error_type}: {count}")

        if error_analysis["critical_errors"]:
            report.append(f"\nCritical Errors: {len(error_analysis['critical_errors'])}")

        sessions = self.get_session_summary()
        report.append(f"\nSessions Today: {sessions['today_count']}")
        if sessions["last_session"]:
            report.append(f"Last Session: {sessions['last_session']}")

        report.append("=" * 60)

        return "\n".join(report)

    def get_log_file_info(self) -> List[Dict]:
        """Get information about all log files"""
        log_files = []

        for log_file in self.logs_dir.glob("*.log"):
            try:
                stat = log_file.stat()
                log_files.append(
                    {
                        "name": log_file.name,
                        "size_mb": stat.st_size / (1024 * 1024),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "path": str(log_file),
                    }
                )
            except Exception as e:
                print(f"Error reading {log_file}: {e}")

        return sorted(log_files, key=lambda x: x["modified"], reverse=True)

    def get_session_summary(self) -> Dict:
        """Get summary of session information"""
        sessions_file = self.logs_dir / "sessions.jsonl"

        summary = {"total_sessions": 0, "today_count": 0, "last_session": None, "average_duration": None}

        if not sessions_file.exists():
            return summary

        today = datetime.now().date()
        durations = []

        try:
            with open(sessions_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        session_data = json.loads(line.strip())
                        summary["total_sessions"] += 1

                        session_time = datetime.fromisoformat(session_data["timestamp"].replace("Z", "+00:00"))
                        if session_time.date() == today:
                            summary["today_count"] += 1

                        if not summary["last_session"] or session_time > datetime.fromisoformat(
                            summary["last_session"].replace("Z", "+00:00")
                        ):
                            summary["last_session"] = session_data["timestamp"]

                        if "session_duration" in session_data:
                            duration_str = session_data["session_duration"]
                            try:
                                time_parts = duration_str.split(":")
                                if len(time_parts) >= 3:
                                    hours = int(time_parts[0])
                                    minutes = int(time_parts[1])
                                    seconds = float(time_parts[2])
                                    total_seconds = hours * 3600 + minutes * 60 + seconds
                                    durations.append(total_seconds)
                            except ValueError:
                                pass

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            print(f"Error reading sessions: {e}")

        if durations:
            avg_seconds = sum(durations) / len(durations)
            summary["average_duration"] = f"{avg_seconds:.1f}s"

        return summary

    def cleanup_logs(self, keep_days: int = 30):
        """
        Clean up old logs beyond the retention period

        Args:
            keep_days: Number of days to keep logs
        """
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        deleted_count = 0

        for log_file in self.logs_dir.glob("session_*.log"):
            try:
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"Error deleting {log_file}: {e}")

        archived_dir = self.logs_dir / "archived"
        if archived_dir.exists():
            for log_file in archived_dir.glob("*"):
                try:
                    if log_file.stat().st_mtime < cutoff_date.timestamp():
                        log_file.unlink()
                        deleted_count += 1
                except Exception as e:
                    print(f"Error deleting archived {log_file}: {e}")

        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} old log files")

    def export_error_report(self, output_file: Path, days: int = 7) -> bool:
        """
        Export error analysis to a file

        Args:
            output_file: Path to output file
            days: Number of days to analyze

        Returns:
            True if successful, False otherwise
        """
        try:
            analysis = self.analyze_errors(days)

            report_data = {
                "generated_at": datetime.now().isoformat(),
                "analysis_period_days": days,
                "summary": {
                    "total_errors": analysis["total_errors"],
                    "unique_error_types": len(analysis["error_types"]),
                    "critical_errors": len(analysis["critical_errors"]),
                },
                "detailed_analysis": analysis,
            }

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2, default=str)

            print(f"Error report exported to {output_file}")
            return True

        except Exception as e:
            print(f"Failed to export error report: {e}")
            return False


log_manager = LogManager()
