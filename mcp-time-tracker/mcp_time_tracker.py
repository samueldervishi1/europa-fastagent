#!/usr/bin/env python3
"""
MCP Server for Time Tracking and Work Hour Logging

This server provides tools to track work hours, manage timers, and generate time reports.
Perfect for freelancers, developers, and anyone who needs to log their work time.
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Time Tracker")

TIME_DATA_FILE = Path("time_tracker_data.json")


def rebuild_date_index(entries: list) -> Dict[str, list]:
    """Rebuild date index from entries for faster date-based lookups"""
    date_index = {}
    for entry in entries:
        date = entry.get("date")
        if date:
            if date not in date_index:
                date_index[date] = []
            date_index[date].append(entry["id"])
    return date_index


def update_date_index(data: Dict[str, Any], entry: Dict[str, Any]):
    """Update date index when adding a new entry"""
    date = entry.get("date")
    if date and "date_index" in data:
        if date not in data["date_index"]:
            data["date_index"][date] = []
        data["date_index"][date].append(entry["id"])


def get_entries_by_date_range(data: Dict[str, Any], start_date: datetime, end_date: datetime) -> list:
    """Get entries within date range using index for faster lookup"""
    if "date_index" not in data or not data["date_index"]:
        # Fallback to linear search if no index
        return get_entries_by_date_range_linear(data["entries"], start_date, end_date)

    relevant_entries = []
    current_date = start_date.date()
    end_date_only = end_date.date()

    # Use date index to get relevant entry IDs
    relevant_entry_ids = set()
    while current_date <= end_date_only:
        date_str = current_date.strftime("%Y-%m-%d")
        if date_str in data["date_index"]:
            relevant_entry_ids.update(data["date_index"][date_str])
        current_date += timedelta(days=1)

    # Get actual entries and filter by exact time range
    entries_by_id = {entry["id"]: entry for entry in data["entries"]}
    for entry_id in relevant_entry_ids:
        if entry_id in entries_by_id:
            entry = entries_by_id[entry_id]
            entry_date = datetime.fromisoformat(entry["start_time"])
            if start_date <= entry_date <= end_date:
                relevant_entries.append(entry)

    return relevant_entries


def get_entries_by_date_range_linear(entries: list, start_date: datetime, end_date: datetime) -> list:
    """Fallback linear search for entries within date range"""
    relevant_entries = []
    for entry in entries:
        entry_date = datetime.fromisoformat(entry["start_time"])
        if start_date <= entry_date <= end_date:
            relevant_entries.append(entry)
    return relevant_entries


def load_time_data() -> Dict[str, Any]:
    """Load time tracking data from JSON file"""
    default_data = {
        "active_timer": None,
        "entries": [],
        "projects": [],
        "categories": ["personal", "client", "learning", "meeting", "other"],
        "date_index": {},  # New: date -> list of entry IDs for faster lookups
    }

    if not TIME_DATA_FILE.exists():
        return default_data

    try:
        with open(TIME_DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            print(f"Warning: Invalid data format in {TIME_DATA_FILE}, using defaults")
            return default_data

        for key in default_data:
            if key not in data:
                print(f"Warning: Missing key '{key}' in {TIME_DATA_FILE}, adding default")
                data[key] = default_data[key]

        # Rebuild date index if missing or incomplete
        if not data.get("date_index") or len(data["date_index"]) == 0:
            data["date_index"] = rebuild_date_index(data["entries"])

        return data

    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON in {TIME_DATA_FILE}: {e}")
        backup_file = TIME_DATA_FILE.with_suffix(f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        try:
            TIME_DATA_FILE.rename(backup_file)
            print(f"Corrupted file backed up to: {backup_file}")
        except Exception:
            pass
        return default_data

    except Exception as e:
        print(f"Error: Failed to load time data: {e}")
        return default_data


def save_time_data(data: Dict[str, Any]) -> bool:
    """Save time tracking data to JSON file"""
    try:
        if not isinstance(data, dict):
            print("Error: Cannot save invalid data format")
            return False

        if TIME_DATA_FILE.exists():
            backup_file = TIME_DATA_FILE.with_suffix(".backup")
            try:
                import shutil

                shutil.copy2(TIME_DATA_FILE, backup_file)
            except Exception:
                pass

        temp_file = TIME_DATA_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        temp_file.replace(TIME_DATA_FILE)
        return True

    except json.JSONEncodeError as e:
        print(f"Error: Failed to encode data as JSON: {e}")
        return False
    except Exception as e:
        print(f"Error: Failed to save time data: {e}")
        return False


def parse_duration_input(duration_str: str) -> Optional[int]:
    """Parse duration input and return minutes"""
    duration_str = duration_str.lower().strip()

    import re

    match = re.match(r"(\d+\.?\d*)h?\s*(\d+)m?", duration_str)
    if match:
        hours = float(match.group(1))
        minutes = int(match.group(2))
        return int(hours * 60 + minutes)

    match = re.match(r"(\d+\.?\d*)h", duration_str)
    if match:
        hours = float(match.group(1))
        return int(hours * 60)

    match = re.match(r"(\d+)m", duration_str)
    if match:
        minutes = int(match.group(1))
        return minutes

    try:
        return int(float(duration_str))
    except ValueError:
        return None


def format_duration(minutes: int) -> str:
    """Format minutes into readable duration"""
    hours = minutes // 60
    mins = minutes % 60

    if hours == 0:
        return f"{mins}m"
    elif mins == 0:
        return f"{hours}h"
    else:
        return f"{hours}h {mins}m"


def get_date_range(period: str) -> tuple[datetime, datetime]:
    """Get start and end datetime for a period"""
    now = datetime.now()

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "week":
        days_since_monday = now.weekday()
        start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
        else:
            end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
    else:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    return start, end


@mcp.tool()
async def start_timer(project: str, category: str = "personal", description: str = "") -> str:
    """
    Start a new work timer.

    Args:
        project: Project name or client name
        category: Category of work (personal, client, learning, meeting, other)
        description: Optional description of the work being done

    Returns:
        Timer start confirmation
    """
    data = load_time_data()

    if data["active_timer"]:
        stop_result = await stop_timer()
        if "Error" in stop_result:
            return f"Failed to stop existing timer: {stop_result}"

    if category not in data["categories"]:
        data["categories"].append(category)

    if project not in data["projects"]:
        data["projects"].append(project)

    data["active_timer"] = {"project": project, "category": category, "start_time": datetime.now().isoformat(), "description": description}

    if save_time_data(data):
        return f"Timer started for '{project}' ({category})"
    else:
        return "Error: Failed to save timer data"


@mcp.tool()
async def stop_timer() -> str:
    """
    Stop the currently running timer and save the time entry.

    Returns:
        Timer stop confirmation with duration
    """
    data = load_time_data()

    if not data["active_timer"]:
        return "No active timer to stop"

    start_time = datetime.fromisoformat(data["active_timer"]["start_time"])
    end_time = datetime.now()
    duration_minutes = int((end_time - start_time).total_seconds() / 60)

    if duration_minutes < 1:
        return "Timer stopped (duration less than 1 minute, not saved)"

    entry = {
        "id": str(uuid.uuid4()),
        "project": data["active_timer"]["project"],
        "category": data["active_timer"]["category"],
        "start_time": data["active_timer"]["start_time"],
        "end_time": end_time.isoformat(),
        "duration_minutes": duration_minutes,
        "description": data["active_timer"]["description"],
        "date": start_time.strftime("%Y-%m-%d"),
    }

    data["entries"].append(entry)
    update_date_index(data, entry)  # Update date index
    data["active_timer"] = None

    if save_time_data(data):
        return f"Timer stopped. Logged {format_duration(duration_minutes)} for '{entry['project']}'"
    else:
        return "Error: Failed to save time entry"


@mcp.tool()
async def get_timer_status() -> str:
    """
    Get the status of the current timer.

    Returns:
        Current timer information or no timer message
    """
    data = load_time_data()

    if not data["active_timer"]:
        return "No active timer"

    start_time = datetime.fromisoformat(data["active_timer"]["start_time"])
    elapsed_minutes = int((datetime.now() - start_time).total_seconds() / 60)

    return f"""Active Timer:
Project: {data["active_timer"]["project"]}
Category: {data["active_timer"]["category"]}
Started: {start_time.strftime("%H:%M")}
Elapsed: {format_duration(elapsed_minutes)}
Description: {data["active_timer"]["description"] or "None"}"""


@mcp.tool()
async def log_time(project: str, duration: str, category: str = "personal", description: str = "", date: str = "") -> str:
    """
    Manually log time for a project (for retroactive entries).

    Args:
        project: Project name or client name
        duration: Duration (e.g., "2h", "90m", "1h 30m")
        category: Category of work (personal, client, learning, meeting, other)
        description: Description of work done
        date: Date in YYYY-MM-DD format (defaults to today)

    Returns:
        Logging confirmation
    """
    data = load_time_data()

    duration_minutes = parse_duration_input(duration)
    if duration_minutes is None:
        return f"Error: Invalid duration format '{duration}'. Use formats like '2h', '90m', '1h 30m'"

    if duration_minutes <= 0:
        return "Error: Duration must be greater than 0"

    if date:
        try:
            log_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return "Error: Invalid date format. Use YYYY-MM-DD"
    else:
        log_date = datetime.now()

    if category not in data["categories"]:
        data["categories"].append(category)

    if project not in data["projects"]:
        data["projects"].append(project)

    entry = {
        "id": str(uuid.uuid4()),
        "project": project,
        "category": category,
        "start_time": log_date.replace(hour=9, minute=0).isoformat(),
        "end_time": (log_date.replace(hour=9, minute=0) + timedelta(minutes=duration_minutes)).isoformat(),
        "duration_minutes": duration_minutes,
        "description": description,
        "date": log_date.strftime("%Y-%m-%d"),
        "manual_entry": True,
    }

    data["entries"].append(entry)
    update_date_index(data, entry)  # Update date index

    if save_time_data(data):
        return f"Logged {format_duration(duration_minutes)} for '{project}' on {log_date.strftime('%Y-%m-%d')}"
    else:
        return "Error: Failed to save time entry"


@mcp.tool()
async def get_time_summary(period: str = "today") -> str:
    """
    Get time summary for a specific period.

    Args:
        period: Time period (today, yesterday, week, month)

    Returns:
        Time summary report
    """
    data = load_time_data()

    start_date, end_date = get_date_range(period)

    # Use optimized date range search
    relevant_entries = get_entries_by_date_range(data, start_date, end_date)

    if not relevant_entries:
        return f"No time entries found for {period}"

    total_minutes = sum(entry["duration_minutes"] for entry in relevant_entries)

    project_totals = {}
    category_totals = {}

    for entry in relevant_entries:
        project = entry["project"]
        category = entry["category"]
        duration = entry["duration_minutes"]

        project_totals[project] = project_totals.get(project, 0) + duration
        category_totals[category] = category_totals.get(category, 0) + duration

    period_title = period.title()
    if period == "today":
        period_title = f"Today ({datetime.now().strftime('%Y-%m-%d')})"
    elif period == "week":
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        period_title = f"This Week ({start_str} to {end_str})"

    summary = f"Time Summary - {period_title}\n"
    summary += "=" * 40 + "\n\n"

    summary += f"Total Time: {format_duration(total_minutes)}\n\n"

    summary += "By Project:\n"
    for project, minutes in sorted(project_totals.items(), key=lambda x: x[1], reverse=True):
        summary += f"  {project}: {format_duration(minutes)}\n"

    summary += "\nBy Category:\n"
    for category, minutes in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        summary += f"  {category}: {format_duration(minutes)}\n"

    return summary


@mcp.tool()
async def list_projects() -> str:
    """
    List all projects you've worked on.

    Returns:
        List of projects with total time
    """
    data = load_time_data()

    if not data["entries"]:
        return "No projects found. Start logging time to see projects here."

    project_totals = {}
    for entry in data["entries"]:
        project = entry["project"]
        duration = entry["duration_minutes"]
        project_totals[project] = project_totals.get(project, 0) + duration

    result = "Your Projects:\n"
    result += "=" * 20 + "\n\n"

    for project, minutes in sorted(project_totals.items(), key=lambda x: x[1], reverse=True):
        result += f"{project}: {format_duration(minutes)}\n"

    return result


@mcp.tool()
async def get_recent_entries(count: int = 5) -> str:
    """
    Get recent time entries.

    Args:
        count: Number of recent entries to show (default: 5)

    Returns:
        List of recent time entries
    """
    data = load_time_data()

    if not data["entries"]:
        return "No time entries found"

    sorted_entries = sorted(data["entries"], key=lambda x: x["start_time"], reverse=True)
    recent_entries = sorted_entries[:count]

    result = f"Recent Time Entries (last {count}):\n"
    result += "=" * 30 + "\n\n"

    for entry in recent_entries:
        start_time = datetime.fromisoformat(entry["start_time"])
        date_str = start_time.strftime("%Y-%m-%d")
        time_str = start_time.strftime("%H:%M")

        result += f"{date_str} {time_str} - {entry['project']} ({entry['category']})\n"
        result += f"  Duration: {format_duration(entry['duration_minutes'])}\n"
        if entry.get("description"):
            result += f"  Description: {entry['description']}\n"
        result += "\n"

    return result


@mcp.tool()
async def delete_last_entry() -> str:
    """
    Delete the most recent time entry (useful for mistakes).

    Returns:
        Deletion confirmation
    """
    data = load_time_data()

    if not data["entries"]:
        return "No entries to delete"

    sorted_entries = sorted(data["entries"], key=lambda x: x["start_time"], reverse=True)
    last_entry = sorted_entries[0]

    data["entries"] = [e for e in data["entries"] if e["id"] != last_entry["id"]]

    if save_time_data(data):
        return f"Deleted entry: {last_entry['project']} ({format_duration(last_entry['duration_minutes'])})"
    else:
        return "Error: Failed to delete entry"


if __name__ == "__main__":
    mcp.run()
