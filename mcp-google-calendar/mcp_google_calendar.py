#!/usr/bin/env python3
"""
MCP Server for Google Calendar Integration

This server provides tools to manage Google Calendar events, schedule meetings, and check availability.
Uses OAuth 2.0 for secure authentication with Google Calendar API.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlencode

import requests
import yaml
from mcp.server.fastmcp import FastMCP

try:
    from dateutil import parser as dateutil_parser

    DATEUTIL_AVAILABLE = True
except ImportError:
    DATEUTIL_AVAILABLE = False

mcp = FastMCP("Google Calendar")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

_access_token: Optional[str] = None
_refresh_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None
_credentials: Optional[Dict[str, str]] = None


def load_credentials() -> Dict[str, str]:
    """Load Google Calendar credentials from fastagent.secrets.yaml or GCP file"""
    global _credentials

    if _credentials:
        return _credentials

    secrets_file = Path("fastagent.secrets.yaml")
    if secrets_file.exists():
        try:
            with open(secrets_file, "r", encoding="utf-8") as f:
                secrets = yaml.safe_load(f) or {}

            google_config = secrets.get("google", {})
            calendar_config = google_config.get("calendar", {})

            if "client_id" in calendar_config and "client_secret" in calendar_config:
                if "redirect_uri" not in calendar_config:
                    calendar_config["redirect_uri"] = "http://127.0.0.1:8080/callback"

                _credentials = calendar_config
                return _credentials
        except Exception:
            pass

    # Try GCP OAuth keys file
    gcp_file = Path("gcp-oauth.keys.json")
    if gcp_file.exists():
        try:
            with open(gcp_file, "r", encoding="utf-8") as f:
                gcp_data = json.load(f)

            # Extract credentials from GCP format
            if "web" in gcp_data or "installed" in gcp_data:
                key = "web" if "web" in gcp_data else "installed"
                gcp_creds = gcp_data[key]

                # Use the first redirect URI from GCP file, or default to localhost
                redirect_uris = gcp_creds.get("redirect_uris", ["http://localhost"])
                redirect_uri = redirect_uris[0] if redirect_uris else "http://localhost"

                # Keep the redirect URI exactly as specified in GCP credentials
                # Don't modify it - Google needs exact match

                _credentials = {
                    "client_id": gcp_creds.get("client_id"),
                    "client_secret": gcp_creds.get("client_secret"),
                    "redirect_uri": redirect_uri,
                }
                return _credentials
        except Exception:
            pass

    raise Exception(
        "Google Calendar credentials not found. Please add them to fastagent.secrets.yaml or ensure gcp-oauth.keys.json exists."
    )


def save_tokens(access_token: str, refresh_token: str, expires_in: int):
    """Save tokens to a local cache file"""
    global _access_token, _refresh_token, _token_expires_at

    _access_token = access_token
    _refresh_token = refresh_token
    _token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)  # 60s buffer

    token_data = {"access_token": access_token, "refresh_token": refresh_token, "expires_at": _token_expires_at.isoformat()}

    token_file = Path(".google_calendar_tokens.json")
    try:
        with open(token_file, "w") as f:
            json.dump(token_data, f)
    except Exception:
        pass


def load_cached_tokens() -> bool:
    """Load tokens from cache file if they exist and are valid"""
    global _access_token, _refresh_token, _token_expires_at

    token_file = Path(".google_calendar_tokens.json")
    if not token_file.exists():
        return False

    try:
        with open(token_file, "r") as f:
            token_data = json.load(f)

        _access_token = token_data.get("access_token")
        _refresh_token = token_data.get("refresh_token")
        expires_at_str = token_data.get("expires_at")

        if expires_at_str:
            _token_expires_at = datetime.fromisoformat(expires_at_str)

        if _token_expires_at and datetime.now() < _token_expires_at:
            return True
        elif _refresh_token:
            return refresh_access_token()

    except Exception:
        pass

    return False


def refresh_access_token() -> bool:
    """Refresh the access token using refresh token"""
    global _access_token, _token_expires_at

    if not _refresh_token:
        return False

    credentials = load_credentials()

    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    data = {
        "grant_type": "refresh_token",
        "refresh_token": _refresh_token,
        "client_id": credentials["client_id"],
        "client_secret": credentials["client_secret"],
    }

    try:
        response = requests.post(GOOGLE_TOKEN_URL, headers=headers, data=data, timeout=10)
        response.raise_for_status()

        token_data = response.json()
        _access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        _token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

        save_tokens(_access_token, _refresh_token, expires_in)
        return True

    except Exception:
        return False


def get_valid_token() -> Optional[str]:
    """Get a valid access token, refreshing if necessary"""
    global _access_token, _token_expires_at

    if not _access_token and not load_cached_tokens():
        return None

    if _token_expires_at and datetime.now() >= _token_expires_at:
        if not refresh_access_token():
            return None

    return _access_token


def calendar_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """Make authenticated request to Google Calendar API"""
    token = get_valid_token()
    if not token:
        raise Exception("No valid Google Calendar access token. Please authenticate first using 'authenticate_google_calendar'.")

    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    headers["Content-Type"] = "application/json"
    kwargs["headers"] = headers

    url = f"{GOOGLE_CALENDAR_API_BASE}/{endpoint.lstrip('/')}"
    response = requests.request(method, url, timeout=15, **kwargs)

    if response.status_code == 401:
        if refresh_access_token():
            token = get_valid_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.request(method, url, timeout=15, **kwargs)

    return response


def parse_datetime_input(datetime_str: str) -> Optional[str]:
    """Parse various datetime formats into ISO format for Google Calendar API"""
    import re

    if not DATEUTIL_AVAILABLE:
        # Fallback for basic parsing without dateutil
        pass

    try:
        # Handle relative terms like "tomorrow", "today"
        now = datetime.now()

        if "tomorrow" in datetime_str.lower():
            base_date = now + timedelta(days=1)
            time_match = re.search(r"(\d{1,2}):?(\d{2})?\s*(am|pm)?", datetime_str, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                ampm = time_match.group(3).lower() if time_match.group(3) else None

                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0

                result_dt = base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                result_dt = base_date.replace(hour=9, minute=0, second=0, microsecond=0)

        elif "today" in datetime_str.lower():
            time_match = re.search(r"(\d{1,2}):?(\d{2})?\s*(am|pm)?", datetime_str, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                ampm = time_match.group(3).lower() if time_match.group(3) else None

                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0

                result_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            else:
                result_dt = now.replace(hour=9, minute=0, second=0, microsecond=0)

        else:
            # Try to parse with dateutil
            if DATEUTIL_AVAILABLE:
                result_dt = dateutil_parser.parse(datetime_str)
            else:
                return None

        return result_dt.isoformat()

    except Exception:
        return None


@mcp.tool()
async def authenticate_google_calendar() -> str:
    """
    Authenticate with Google Calendar using OAuth 2.0 flow.
    This needs to be done once before using calendar features.

    Returns:
        Authentication status and instructions
    """
    try:
        credentials = load_credentials()
    except Exception as e:
        return f"Credential error: {e}"

    if load_cached_tokens():
        return "Already authenticated with Google Calendar! You can now manage your calendar."

    # Generate the auth URL for manual authentication
    scopes = ["https://www.googleapis.com/auth/calendar", "https://www.googleapis.com/auth/calendar.events"]

    auth_params = {
        "client_id": credentials["client_id"],
        "redirect_uri": credentials["redirect_uri"],
        "scope": " ".join(scopes),
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(auth_params)}"

    return f"""Google Calendar Authentication Required:

STEP 1: Open this URL in your browser:
{auth_url}

STEP 2: Complete the Google authorization process

STEP 3: After authorization, you'll be redirected to {credentials["redirect_uri"]}
(This will show "This site can't be reached" - that's normal)

STEP 4: Look at the URL in your browser address bar. It will look like:
http://localhost/?code=4/0AanS...&scope=...

STEP 5: Copy the long code after "code=" and before "&scope"

STEP 6: Use 'complete_calendar_auth' with that code

Note: Make sure Google Calendar API is enabled in your Google Cloud Console at:
https://console.cloud.google.com/apis/library/calendar-json.googleapis.com"""


@mcp.tool()
async def complete_calendar_auth(authorization_code: str) -> str:
    """
    Complete Google Calendar authentication with authorization code.
    Use this after running authenticate_google_calendar and getting the auth code.

    Args:
        authorization_code: The authorization code from the redirect URL

    Returns:
        Authentication completion status
    """
    try:
        credentials = load_credentials()

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": credentials["redirect_uri"],
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
        }

        response = requests.post(GOOGLE_TOKEN_URL, headers=headers, data=data, timeout=10)
        response.raise_for_status()

        token_data = response.json()
        save_tokens(token_data["access_token"], token_data.get("refresh_token", ""), token_data.get("expires_in", 3600))

        return "Successfully authenticated with Google Calendar! You can now manage your calendar events."

    except Exception as e:
        return f"Authentication failed: {e}"


@mcp.tool()
async def create_calendar_event(
    title: str, start_time: str, duration_hours: float = 1.0, attendees: str = "", description: str = ""
) -> str:
    """
    Create a new calendar event.

    Args:
        title: Event title
        start_time: Start time (e.g., "tomorrow 2pm", "2025-01-17 14:00", "today 10am")
        duration_hours: Event duration in hours (default: 1.0)
        attendees: Comma-separated email addresses of attendees
        description: Event description

    Returns:
        Event creation confirmation
    """
    try:
        start_iso = parse_datetime_input(start_time)
        if not start_iso:
            return f"Error: Could not parse start time '{start_time}'. Try formats like 'tomorrow 2pm', '2025-01-17 14:00', or 'today 10am'"

        start_dt = datetime.fromisoformat(start_iso)
        end_dt = start_dt + timedelta(hours=duration_hours)

        event_data = {
            "summary": title,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "America/New_York",  # You might want to make this configurable
            },
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/New_York"},
            "description": description,
        }

        # Add attendees if provided
        if attendees.strip():
            attendee_emails = [email.strip() for email in attendees.split(",")]
            event_data["attendees"] = [{"email": email} for email in attendee_emails if email]

        response = calendar_request("POST", "/calendars/primary/events", json=event_data)
        response.raise_for_status()

        event = response.json()

        result = f"Event created: '{title}'"
        result += f"\nTime: {start_dt.strftime('%Y-%m-%d %I:%M %p')} - {end_dt.strftime('%I:%M %p')}"

        if attendees.strip():
            result += f"\nAttendees: {attendees}"
            result += "\nInvitations sent to attendees"

        result += f"\nEvent ID: {event.get('id')}"

        return result

    except Exception as e:
        return f"Failed to create event: {e}"


@mcp.tool()
async def list_todays_events() -> str:
    """
    List today's calendar events.

    Returns:
        List of today's events
    """
    try:
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        params = {
            "timeMin": start_of_day.isoformat() + "Z",
            "timeMax": end_of_day.isoformat() + "Z",
            "singleEvents": True,
            "orderBy": "startTime",
        }

        response = calendar_request("GET", "/calendars/primary/events", params=params)
        response.raise_for_status()

        events_data = response.json()
        events = events_data.get("items", [])

        if not events:
            return f"No events scheduled for today ({now.strftime('%Y-%m-%d')})"

        result = f"Today's Events ({now.strftime('%Y-%m-%d')}):\n"
        result += "=" * 40 + "\n\n"

        for event in events:
            title = event.get("summary", "No title")

            start = event.get("start", {})
            if "dateTime" in start:
                start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                time_str = start_dt.strftime("%I:%M %p")
            else:
                time_str = "All day"

            result += f"{time_str} - {title}"

            if "attendees" in event:
                attendee_count = len(event["attendees"])
                result += f" ({attendee_count} attendees)"

            result += "\n"

        return result

    except Exception as e:
        return f"Failed to list events: {e}"


@mcp.tool()
async def check_availability(date: str, duration_hours: float = 1.0) -> str:
    """
    Check availability for a specific date and suggest free time slots.

    Args:
        date: Date to check (e.g., "tomorrow", "2025-01-17", "today")
        duration_hours: Required duration in hours (default: 1.0)

    Returns:
        Available time slots
    """
    try:
        # Parse the date
        target_date = None
        now = datetime.now()

        if date.lower() == "today":
            target_date = now.date()
        elif date.lower() == "tomorrow":
            target_date = (now + timedelta(days=1)).date()
        else:
            if DATEUTIL_AVAILABLE:
                target_date = dateutil_parser.parse(date).date()
            else:
                return "Error: Advanced date parsing not available. Use 'today' or 'tomorrow'."

        # Get events for the entire day
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        params = {
            "timeMin": start_of_day.isoformat() + "Z",
            "timeMax": end_of_day.isoformat() + "Z",
            "singleEvents": True,
            "orderBy": "startTime",
        }

        response = calendar_request("GET", "/calendars/primary/events", params=params)
        response.raise_for_status()

        events_data = response.json()
        events = events_data.get("items", [])

        # Build busy periods
        busy_periods = []
        for event in events:
            start = event.get("start", {})
            end = event.get("end", {})

            if "dateTime" in start and "dateTime" in end:
                start_dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end["dateTime"].replace("Z", "+00:00"))
                busy_periods.append((start_dt, end_dt))

        # Sort busy periods
        busy_periods.sort()

        # Find free slots (9 AM - 6 PM working hours)
        work_start = datetime.combine(target_date, datetime.min.time().replace(hour=9))
        work_end = datetime.combine(target_date, datetime.min.time().replace(hour=18))

        free_slots = []
        current_time = work_start
        duration_delta = timedelta(hours=duration_hours)

        for busy_start, busy_end in busy_periods:
            # Check if there's a free slot before this busy period
            if current_time + duration_delta <= busy_start:
                free_slots.append((current_time, busy_start))
            current_time = max(current_time, busy_end)

        # Check for free time after last busy period
        if current_time + duration_delta <= work_end:
            free_slots.append((current_time, work_end))

        # Format result
        result = f"Availability for {target_date.strftime('%Y-%m-%d')}:\n"
        result += "=" * 40 + "\n\n"

        if not free_slots:
            result += f"No free slots found for {duration_hours} hour(s) during working hours (9 AM - 6 PM)"
        else:
            result += f"Available {duration_hours} hour slots:\n\n"
            for start_time, end_time in free_slots:
                slot_duration = (end_time - start_time).total_seconds() / 3600
                if slot_duration >= duration_hours:
                    result += f"• {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} "
                    result += f"({slot_duration:.1f} hours available)\n"

        return result

    except Exception as e:
        return f"Failed to check availability: {e}"


@mcp.tool()
async def get_calendar_status() -> str:
    """
    Get Google Calendar connection status and basic information.

    Returns:
        Calendar status and information
    """
    try:
        token = get_valid_token()
        if not token:
            return "Not authenticated. Run 'authenticate_google_calendar' first."

        # Test API access by getting calendar info
        response = calendar_request("GET", "/calendars/primary")
        response.raise_for_status()

        calendar_info = response.json()

        # Get today's event count
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        params = {
            "timeMin": start_of_day.isoformat() + "Z",
            "timeMax": end_of_day.isoformat() + "Z",
        }

        events_response = calendar_request("GET", "/calendars/primary/events", params=params)
        events_response.raise_for_status()
        events_data = events_response.json()
        event_count = len(events_data.get("items", []))

        result = "Google Calendar Status:\n\n"
        result += f"Calendar: {calendar_info.get('summary', 'Primary')}\n"
        result += f"Time Zone: {calendar_info.get('timeZone', 'Unknown')}\n"
        result += f"Today's Events: {event_count}\n"
        result += "Connected: Yes\n"

        return result

    except Exception as e:
        return f"Failed to get calendar status: {e}"


if __name__ == "__main__":
    mcp.run()
