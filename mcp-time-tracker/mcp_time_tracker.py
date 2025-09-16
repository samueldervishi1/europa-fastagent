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

# Data file for persistent storage
TIME_DATA_FILE = Path("time_tracker_data.json")


def load_time_data() -> Dict[str, Any]:
    """Load time tracking data from JSON file"""
    if not TIME_DATA_FILE.exists():
        return {"active_timer": None, "entries": [], "projects": [], "categories": ["personal", "client", "learning", "meeting", "other"]}

    try:
        with open(TIME_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"active_timer": None, "entries": [], "projects": [], "categories": ["personal", "client", "learning", "meeting", "other"]}


def save_time_data(data: Dict[str, Any]) -> bool:
    """Save time tracking data to JSON file"""
    try:
        with open(TIME_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception:
        return False


def parse_duration_input(duration_str: str) -> Optional[int]:
    """Parse duration input and return minutes"""
    duration_str = duration_str.lower().strip()

    # Handle formats like "2h", "30m", "1h 30m", "90m", "1.5h"
    import re

    # Try "Xh Ym" format
    match = re.match(r"(\d+\.?\d*)h?\s*(\d+)m?", duration_str)
    if match:
        hours = float(match.group(1))
        minutes = int(match.group(2))
        return int(hours * 60 + minutes)

    # Try "Xh" format
    match = re.match(r"(\d+\.?\d*)h", duration_str)
    if match:
        hours = float(match.group(1))
        return int(hours * 60)

    # Try "Ym" format
    match = re.match(r"(\d+)m", duration_str)
    if match:
        minutes = int(match.group(1))
        return minutes

    # Try plain number (assume minutes)
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
        # Current week (Monday to Sunday)
        days_since_monday = now.weekday()
        start = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=6)).replace(hour=23, minute=59, second=59, microsecond=999999)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Last day of current month
        if now.month == 12:
            end = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
        else:
            end = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(microseconds=1)
    else:
        # Default to today
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

    # Stop any existing timer first
    if data["active_timer"]:
        stop_result = await stop_timer()
        if "Error" in stop_result:
            return f"Failed to stop existing timer: {stop_result}"

    # Validate category
    if category not in data["categories"]:
        data["categories"].append(category)

    # Add project to projects list if not exists
    if project not in data["projects"]:
        data["projects"].append(project)

    # Start new timer
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

    # Calculate duration
    start_time = datetime.fromisoformat(data["active_timer"]["start_time"])
    end_time = datetime.now()
    duration_minutes = int((end_time - start_time).total_seconds() / 60)

    if duration_minutes < 1:
        return "Timer stopped (duration less than 1 minute, not saved)"

    # Create entry
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

    # Add to entries
    data["entries"].append(entry)
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

    # Parse duration
    duration_minutes = parse_duration_input(duration)
    if duration_minutes is None:
        return f"Error: Invalid duration format '{duration}'. Use formats like '2h', '90m', '1h 30m'"

    if duration_minutes <= 0:
        return "Error: Duration must be greater than 0"

    # Parse date
    if date:
        try:
            log_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return "Error: Invalid date format. Use YYYY-MM-DD"
    else:
        log_date = datetime.now()

    # Validate category
    if category not in data["categories"]:
        data["categories"].append(category)

    # Add project to projects list if not exists
    if project not in data["projects"]:
        data["projects"].append(project)

    # Create entry
    entry = {
        "id": str(uuid.uuid4()),
        "project": project,
        "category": category,
        "start_time": log_date.replace(hour=9, minute=0).isoformat(),  # Default start time
        "end_time": (log_date.replace(hour=9, minute=0) + timedelta(minutes=duration_minutes)).isoformat(),
        "duration_minutes": duration_minutes,
        "description": description,
        "date": log_date.strftime("%Y-%m-%d"),
        "manual_entry": True,
    }

    data["entries"].append(entry)

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

    # Filter entries in date range
    relevant_entries = []
    for entry in data["entries"]:
        entry_date = datetime.fromisoformat(entry["start_time"])
        if start_date <= entry_date <= end_date:
            relevant_entries.append(entry)

    if not relevant_entries:
        return f"No time entries found for {period}"

    # Calculate totals
    total_minutes = sum(entry["duration_minutes"] for entry in relevant_entries)

    # Group by project
    project_totals = {}
    category_totals = {}

    for entry in relevant_entries:
        project = entry["project"]
        category = entry["category"]
        duration = entry["duration_minutes"]

        project_totals[project] = project_totals.get(project, 0) + duration
        category_totals[category] = category_totals.get(category, 0) + duration

    # Build summary
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

    # Calculate project totals
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

    # Sort by start time (most recent first)
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

    # Find most recent entry
    sorted_entries = sorted(data["entries"], key=lambda x: x["start_time"], reverse=True)
    last_entry = sorted_entries[0]

    # Remove it
    data["entries"] = [e for e in data["entries"] if e["id"] != last_entry["id"]]

    if save_time_data(data):
        return f"Deleted entry: {last_entry['project']} ({format_duration(last_entry['duration_minutes'])})"
    else:
        return "Error: Failed to delete entry"


if __name__ == "__main__":
    mcp.run()
