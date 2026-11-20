"""Phase 3: create one private playlist per category and add the videos to it.

Usage:
    python push.py --dry-run   # show the plan, change nothing, no login needed
    python push.py             # do it (asks you to log in the first time)

Safe to re-run: progress is saved in pushed.json, so it resumes where it stopped.
The YouTube API allows about 200 inserts per day, so 200+ videos take 2 days.

It only creates NEW private playlists. It never edits or deletes anything that
already exists, and it does not remove videos from Watch Later (the API cannot).
"""
import json
import os
import sys
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/youtube"]
CLIENT_SECRET = Path("client_secret.json")
TOKEN = Path("youtube_token.json")
CATS = Path("categories.json")
STATE = Path("pushed.json")
PORT = 8080
PREFIX = "WL - "  # playlist names become "WL - Programming", "WL - Finance", ...


def wait_for_callback(expected_state):
    """Listen on PORT until Google's real redirect arrives; ignore any other request."""
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            if q.get("state", [None])[0] == expected_state and ("code" in q or "error" in q):
                result["url"] = f"http://localhost:{PORT}{self.path}"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h3>Done. You can close this tab and go back to the terminal.</h3>")
            else:  # favicon, prefetch, stale link...
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("0.0.0.0", PORT), Handler)
    while "url" not in result:
        server.handle_request()
    server.server_close()
    return result["url"]


def get_service():
    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(TOKEN, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRET.exists():
                sys.exit("client_secret.json not found in data/. See the README for the OAuth setup.")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            flow.redirect_uri = f"http://localhost:{PORT}/"
            auth_url, oauth_state = flow.authorization_url(access_type="offline", prompt="consent")
            print("\nOpen this link in your browser and approve access:\n")
            print(auth_url)
            print("\nWaiting for approval...")
            response_url = wait_for_callback(oauth_state)
            os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # redirect is http://localhost
            flow.fetch_token(authorization_response=response_url)
            creds = flow.credentials
        TOKEN.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def is_quota_error(e):
    return e.resp.status == 403 and b"quotaExceeded" in e.content


def main():
    dry_run = "--dry-run" in sys.argv
    if not CATS.exists():
        sys.exit("categories.json not found. Run fetch and classify first.")

    cats = json.loads(CATS.read_text())
    state = json.loads(STATE.read_text()) if STATE.exists() else {"playlists": {}, "added": []}
    added = set(state["added"])

    groups = defaultdict(list)
    for vid, cat in cats.items():
        if vid not in added:
            groups[cat].append(vid)
    total = sum(len(ids) for ids in groups.values())

    print(f"{len(added)} videos already added, {total} to add\n")
    for cat in sorted(groups):
        new = "" if cat in state["playlists"] else "  (new playlist)"
        print(f"  {PREFIX}{cat:<18} {len(groups[cat])} videos{new}")
    if dry_run or not total:
        if dry_run:
            print("\nDry run: nothing was changed.")
        return

    yt = get_service()
    added_now = 0
    try:
        for cat in sorted(groups):
            playlist_id = state["playlists"].get(cat)
            if not playlist_id:
                resp = yt.playlists().insert(
                    part="snippet,status",
                    body={
                        "snippet": {"title": f"{PREFIX}{cat}", "description": "Sorted automatically"},
                        "status": {"privacyStatus": "private"},
                    },
                ).execute()
                playlist_id = resp["id"]
                state["playlists"][cat] = playlist_id
                STATE.write_text(json.dumps(state, indent=2))
                print(f"\nCreated private playlist: {PREFIX}{cat}")

            for vid in groups[cat]:
                try:
                    yt.playlistItems().insert(
                        part="snippet",
                        body={"snippet": {
                            "playlistId": playlist_id,
                            "resourceId": {"kind": "youtube#video", "videoId": vid},
                        }},
                    ).execute()
                except HttpError as e:
                    if is_quota_error(e):
                        raise
                    print(f"  skipped {vid} (HTTP {e.resp.status}), will retry next run")
                    continue
                state["added"].append(vid)
                STATE.write_text(json.dumps(state, indent=2))
                added_now += 1
                if added_now % 10 == 0:
                    print(f"  {added_now} added this run...", flush=True)
    except HttpError as e:
        if not is_quota_error(e):
            raise
        print("\nDaily YouTube quota used up. Progress is saved.")
        print("Run the same command again tomorrow (the quota resets at midnight Pacific time).")

    remaining = total - added_now
    print(f"\nAdded {added_now} videos this run, {remaining} remaining.")


if __name__ == "__main__":
    main()