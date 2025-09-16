#!/usr/bin/env python3
"""
MCP Server for Spotify Music Control

This server provides tools to control Spotify playback, search music, and manage playlists.
Requires Spotify Premium account and developer app credentials.
"""

import base64
import http.server
import json
import socketserver
import threading
import time
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import requests
import yaml
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Spotify Controller")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

_access_token: Optional[str] = None
_refresh_token: Optional[str] = None
_token_expires_at: Optional[datetime] = None
_credentials: Optional[Dict[str, str]] = None


class CallbackHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        global _auth_code_received
        if self.path.startswith("/callback"):
            query_params = parse_qs(urlparse(self.path).query)
            if "code" in query_params:
                _auth_code_received = query_params["code"][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"""
                <html><body>
                <h2>Authorization successful!</h2>
                <p>You can now close this window and return to your terminal.</p>
                <script>setTimeout(function(){window.close();}, 3000);</script>
                </body></html>
                """)
            else:
                self.send_error(400, "Authorization failed")
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


_auth_code_received = None


def load_credentials() -> Dict[str, str]:
    """Load Spotify credentials from fastagent.secrets.yaml"""
    global _credentials

    if _credentials:
        return _credentials

    secrets_file = Path("fastagent.secrets.yaml")
    if not secrets_file.exists():
        raise Exception("fastagent.secrets.yaml not found. Please create it with your Spotify credentials.")

    try:
        with open(secrets_file, "r", encoding="utf-8") as f:
            secrets = yaml.safe_load(f) or {}

        spotify_config = secrets.get("spotify", {})
        required_keys = ["client_id", "client_secret"]

        for key in required_keys:
            if key not in spotify_config:
                raise Exception(f"Missing '{key}' in spotify section of fastagent.secrets.yaml")

        if "redirect_uri" not in spotify_config:
            spotify_config["redirect_uri"] = "http://127.0.0.1:8080/callback"

        _credentials = spotify_config
        return _credentials

    except Exception as e:
        raise Exception(f"Failed to load Spotify credentials: {e}")


def save_tokens(access_token: str, refresh_token: str, expires_in: int):
    """Save tokens to a local cache file"""
    global _access_token, _refresh_token, _token_expires_at

    _access_token = access_token
    _refresh_token = refresh_token
    _token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)

    token_data = {"access_token": access_token, "refresh_token": refresh_token, "expires_at": _token_expires_at.isoformat()}

    token_file = Path(".spotify_tokens.json")
    try:
        with open(token_file, "w") as f:
            json.dump(token_data, f)
    except Exception:
        pass


def load_cached_tokens() -> bool:
    """Load tokens from cache file if they exist and are valid"""
    global _access_token, _refresh_token, _token_expires_at

    token_file = Path(".spotify_tokens.json")
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

    auth_header = base64.b64encode(f"{credentials['client_id']}:{credentials['client_secret']}".encode()).decode()

    headers = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/x-www-form-urlencoded"}

    data = {"grant_type": "refresh_token", "refresh_token": _refresh_token}

    try:
        response = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data, timeout=10)
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


def spotify_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """Make authenticated request to Spotify API"""
    token = get_valid_token()
    if not token:
        raise Exception("No valid Spotify access token. Please authenticate first using 'authenticate_spotify'.")

    headers = kwargs.get("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    kwargs["headers"] = headers

    url = f"{SPOTIFY_API_BASE}/{endpoint.lstrip('/')}"
    response = requests.request(method, url, timeout=10, **kwargs)

    if response.status_code == 401:
        if refresh_access_token():
            token = get_valid_token()
            headers["Authorization"] = f"Bearer {token}"
            response = requests.request(method, url, timeout=10, **kwargs)

    return response


@mcp.tool()
async def authenticate_spotify() -> str:
    """
    Authenticate with Spotify using OAuth 2.0 flow.
    This needs to be done once before using other music control features.

    Returns:
        Authentication status and instructions
    """
    global _auth_code_received

    print("Starting Spotify authentication...")

    try:
        credentials = load_credentials()
        print(f"Loaded credentials for client ID: {credentials['client_id'][:10]}...")
    except Exception as e:
        return f'Credential error: {e}\n\nPlease add your Spotify credentials to fastagent.secrets.yaml:\n\nspotify:\n  client_id: "your-client-id"\n  client_secret: "your-client-secret"\n  redirect_uri: "http://127.0.0.1:8080/callback"'

    if load_cached_tokens():
        return "Already authenticated with Spotify! You can now use music control features."

    try:
        print("Starting local server on 127.0.0.1:8080...")
        httpd = socketserver.TCPServer(("127.0.0.1", 8080), CallbackHandler)
        server_thread = threading.Thread(target=httpd.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print("Local server started successfully")

        scopes = [
            "user-read-playback-state",
            "user-modify-playback-state",
            "user-read-currently-playing",
            "playlist-read-private",
            "playlist-modify-private",
            "playlist-modify-public",
            "user-library-read",
            "user-library-modify",
        ]

        auth_params = {
            "client_id": credentials["client_id"],
            "response_type": "code",
            "redirect_uri": credentials["redirect_uri"],
            "scope": " ".join(scopes),
            "show_dialog": "true",
        }

        auth_url = f"{SPOTIFY_AUTH_URL}?{urlencode(auth_params)}"

        try:
            import subprocess

            try:
                webbrowser.open(auth_url)
            except Exception:
                subprocess.run(["xdg-open", auth_url], check=False)
        except Exception as e:
            print(f"Failed to open browser: {e}")
            print(f"Please manually open: {auth_url}")

        _auth_code_received = None
        timeout = 120
        start_time = time.time()

        print("Please complete authentication in your browser...")
        print(f"If browser didn't open, go to: {auth_url}")

        while _auth_code_received is None and (time.time() - start_time) < timeout:
            time.sleep(1)

        httpd.shutdown()

        if _auth_code_received is None:
            return f"Authentication timed out after {timeout} seconds. Please check:\n1. Browser opened the correct URL\n2. You completed the login process\n3. Redirect URI matches in Spotify app settings: {credentials['redirect_uri']}"

        auth_header = base64.b64encode(f"{credentials['client_id']}:{credentials['client_secret']}".encode()).decode()

        headers = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/x-www-form-urlencoded"}

        data = {"grant_type": "authorization_code", "code": _auth_code_received, "redirect_uri": credentials["redirect_uri"]}

        response = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data, timeout=10)
        response.raise_for_status()

        token_data = response.json()
        save_tokens(token_data["access_token"], token_data["refresh_token"], token_data["expires_in"])

        return "Successfully authenticated with Spotify! You can now control your music."

    except Exception as e:
        return f"Authentication failed: {e}"


@mcp.tool()
async def get_current_track() -> str:
    """
    Get information about the currently playing track.

    Returns:
        Current track information or playback status
    """
    try:
        response = spotify_request("GET", "/me/player/currently-playing")

        if response.status_code == 204:
            return "No track currently playing"

        response.raise_for_status()
        data = response.json()

        if not data.get("is_playing"):
            return "Playback is paused"

        track = data.get("item", {})
        artists = ", ".join([artist["name"] for artist in track.get("artists", [])])

        progress_ms = data.get("progress_ms", 0)
        duration_ms = track.get("duration_ms", 0)

        progress_min = progress_ms // 60000
        progress_sec = (progress_ms % 60000) // 1000
        duration_min = duration_ms // 60000
        duration_sec = (duration_ms % 60000) // 1000

        return f"""Now Playing:
{track.get("name", "Unknown")} by {artists}
Album: {track.get("album", {}).get("name", "Unknown")}
Progress: {progress_min}:{progress_sec:02d} / {duration_min}:{duration_sec:02d}
Device: {data.get("device", {}).get("name", "Unknown")}"""

    except Exception as e:
        return f"Failed to get current track: {e}"


@mcp.tool()
async def play_music(uri: str = None) -> str:
    """
    Start or resume music playback.

    Args:
        uri: Optional Spotify URI to play (track, album, playlist)

    Returns:
        Playback status
    """
    try:
        data = {}
        if uri:
            if uri.startswith("spotify:"):
                data["uris"] = [uri]
            else:
                data["context_uri"] = uri

        response = spotify_request("PUT", "/me/player/play", json=data)

        if response.status_code == 404:
            return "No active device found. Please open Spotify on a device first."
        elif response.status_code == 403:
            return "Spotify Premium required for playback control."

        response.raise_for_status()

        if uri:
            return f"Started playing: {uri}"
        else:
            return "Music resumed"

    except Exception as e:
        return f"Failed to play music: {e}"


@mcp.tool()
async def pause_music() -> str:
    """
    Pause the current music playback.

    Returns:
        Pause status
    """
    try:
        response = spotify_request("PUT", "/me/player/pause")

        if response.status_code == 404:
            return "No active device found."
        elif response.status_code == 403:
            return "Spotify Premium required for playback control."

        response.raise_for_status()
        return "Music paused"

    except Exception as e:
        return f"Failed to pause music: {e}"


@mcp.tool()
async def skip_track() -> str:
    """
    Skip to the next track.

    Returns:
        Skip status
    """
    try:
        response = spotify_request("POST", "/me/player/next")

        if response.status_code == 404:
            return "No active device found."
        elif response.status_code == 403:
            return "Spotify Premium required for playback control."

        response.raise_for_status()
        return "Skipped to next track"

    except Exception as e:
        return f"Failed to skip track: {e}"


@mcp.tool()
async def previous_track() -> str:
    """
    Go back to the previous track.

    Returns:
        Previous track status
    """
    try:
        response = spotify_request("POST", "/me/player/previous")

        if response.status_code == 404:
            return "No active device found."
        elif response.status_code == 403:
            return "Spotify Premium required for playback control."

        response.raise_for_status()
        return "Went to previous track"

    except Exception as e:
        return f"Failed to go to previous track: {e}"


@mcp.tool()
async def set_volume(level: int) -> str:
    """
    Set the playback volume.

    Args:
        level: Volume level (0-100)

    Returns:
        Volume change status
    """
    try:
        if not 0 <= level <= 100:
            return "Volume level must be between 0 and 100"

        params = {"volume_percent": level}
        response = spotify_request("PUT", "/me/player/volume", params=params)

        if response.status_code == 404:
            return "No active device found."
        elif response.status_code == 403:
            return "Spotify Premium required for playback control."

        response.raise_for_status()
        return f"Volume set to {level}%"

    except Exception as e:
        return f"Failed to set volume: {e}"


@mcp.tool()
async def search_music(query: str, type: str = "track", limit: int = 5) -> str:
    """
    Search for music on Spotify.

    Args:
        query: Search query
        type: Type of content to search (track, artist, album, playlist)
        limit: Number of results to return (1-20)

    Returns:
        Search results
    """
    try:
        if type not in ["track", "artist", "album", "playlist"]:
            return "Search type must be one of: track, artist, album, playlist"

        if not 1 <= limit <= 20:
            return "Limit must be between 1 and 20"

        params = {"q": query, "type": type, "limit": limit}

        response = spotify_request("GET", "/search", params=params)
        response.raise_for_status()

        data = response.json()
        results = []

        if type == "track":
            tracks = data.get("tracks", {}).get("items", [])
            for track in tracks:
                artists = ", ".join([artist["name"] for artist in track.get("artists", [])])
                results.append(f"{track['name']} by {artists} (spotify:track:{track['id']})")

        elif type == "artist":
            artists = data.get("artists", {}).get("items", [])
            for artist in artists:
                results.append(f"{artist['name']} (spotify:artist:{artist['id']})")

        elif type == "album":
            albums = data.get("albums", {}).get("items", [])
            for album in albums:
                artists = ", ".join([artist["name"] for artist in album.get("artists", [])])
                results.append(f"{album['name']} by {artists} (spotify:album:{album['id']})")

        elif type == "playlist":
            playlists = data.get("playlists", {}).get("items", [])
            for playlist in playlists:
                owner = playlist.get("owner", {}).get("display_name", "Unknown")
                results.append(f"{playlist['name']} by {owner} (spotify:playlist:{playlist['id']})")

        if not results:
            return f"No {type}s found for '{query}'"

        return f"Search results for '{query}':\n\n" + "\n".join(results)

    except Exception as e:
        return f"Search failed: {e}"


@mcp.tool()
async def get_user_playlists() -> str:
    """
    Get the user's playlists.

    Returns:
        List of user playlists
    """
    try:
        response = spotify_request("GET", "/me/playlists", params={"limit": 20})
        response.raise_for_status()

        data = response.json()
        playlists = data.get("items", [])

        if not playlists:
            return "No playlists found"

        results = []
        for playlist in playlists:
            track_count = playlist.get("tracks", {}).get("total", 0)
            results.append(f"{playlist['name']} ({track_count} tracks) - spotify:playlist:{playlist['id']}")

        return "Your Playlists:\n\n" + "\n".join(results)

    except Exception as e:
        return f"Failed to get playlists: {e}"


@mcp.tool()
async def toggle_shuffle() -> str:
    """
    Toggle shuffle mode on/off.

    Returns:
        Shuffle status
    """
    try:
        response = spotify_request("GET", "/me/player")

        if response.status_code == 204:
            return "No active playback session"

        response.raise_for_status()
        current_state = response.json()
        current_shuffle = current_state.get("shuffle_state", False)

        new_shuffle = not current_shuffle
        params = {"state": new_shuffle}
        response = spotify_request("PUT", "/me/player/shuffle", params=params)

        if response.status_code == 404:
            return "No active device found."
        elif response.status_code == 403:
            return "Spotify Premium required for playback control."

        response.raise_for_status()
        return f"Shuffle {'enabled' if new_shuffle else 'disabled'}"

    except Exception as e:
        return f"Failed to toggle shuffle: {e}"


@mcp.tool()
async def get_spotify_status() -> str:
    """
    Get comprehensive Spotify playback status and connection info.

    Returns:
        Detailed status information
    """
    try:
        token = get_valid_token()
        if not token:
            return "Not authenticated. Run 'authenticate_spotify' first."

        response = spotify_request("GET", "/me/player")

        if response.status_code == 204:
            return "Connected to Spotify\nNo active playback session"

        response.raise_for_status()
        data = response.json()

        device = data.get("device", {})
        track = data.get("item", {})

        if track:
            artists = ", ".join([artist["name"] for artist in track.get("artists", [])])
            status = f"""Spotify Status:

Device: {device.get("name", "Unknown")} ({device.get("type", "Unknown")})
Volume: {device.get("volume_percent", 0)}%
Playing: {"Yes" if data.get("is_playing") else "Paused"}
Shuffle: {"On" if data.get("shuffle_state") else "Off"}
Repeat: {data.get("repeat_state", "off").title()}

Current Track:
{track.get("name", "Unknown")} by {artists}\nAlbum: {track.get("album", {}).get("name", "Unknown")}"""
        else:
            status = f"""Spotify Status:

Device: {device.get("name", "Unknown")} ({device.get("type", "Unknown")})
Volume: {device.get("volume_percent", 0)}%
Playing: No track loaded"""

        return status

    except Exception as e:
        return f"Failed to get status: {e}"


if __name__ == "__main__":
    mcp.run()
