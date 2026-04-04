"""
Fetch WHOOP data and save as JSON for the website.
Run after whoop_auth.py has saved tokens.
"""

import json
import os
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(DIR, ".whoop_tokens.json")
DATA_FILE = os.path.join(DIR, "whoop_data.json")

CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID", "")
if not CLIENT_ID:
    raise SystemExit("Set WHOOP_CLIENT_ID environment variable before running.")
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer"


def load_tokens():
    with open(TOKEN_FILE) as f:
        return json.load(f)


def save_tokens(tokens):
    with open(TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)


def refresh_tokens(tokens):
    secret = os.environ.get("WHOOP_CLIENT_SECRET") or input("Paste your WHOOP Client Secret: ").strip()

    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": CLIENT_ID,
        "client_secret": secret,
    }).encode("utf-8")

    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "NextEliteProtocol/1.0")

    with urllib.request.urlopen(req) as resp:
        new_tokens = json.loads(resp.read().decode())

    save_tokens(new_tokens)
    print("Tokens refreshed.")
    return new_tokens


def api_get(endpoint, access_token):
    url = f"{API_BASE}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    req.add_header("User-Agent", "NextEliteProtocol/1.0")

    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return None  # token expired
        print(f"  Warning: {endpoint} returned {e.code}")
        return {}


def main():
    if not os.path.exists(TOKEN_FILE):
        print("No tokens found. Run whoop_auth.py first.")
        return

    tokens = load_tokens()
    access_token = tokens["access_token"]

    # Test connection, refresh if expired
    test = api_get("/v1/cycle", access_token)
    if test is None:
        print("Token expired, refreshing...")
        tokens = refresh_tokens(tokens)
        access_token = tokens["access_token"]
        test = api_get("/v1/cycle", access_token)

    # Fetch all endpoints
    print("Fetching cycles...")
    cycles = api_get("/v1/cycle", access_token)
    print("Fetching recovery...")
    recovery_data = api_get("/v1/recovery", access_token)
    if not recovery_data or "records" not in recovery_data:
        recovery_data = api_get("/v2/recovery", access_token)
    print("Fetching sleep...")
    sleep_data = api_get("/v1/activity/sleep", access_token)
    if not sleep_data or "records" not in sleep_data:
        sleep_data = api_get("/v2/activity/sleep", access_token)

    # Build result
    result = {
        "updated": datetime.now().isoformat(),
        "recovery": None,
        "strain": None,
        "sleep_hours": None,
        "hrv": None,
        "rhr": None,
        "avg_hr": None,
        "max_hr": None,
    }

    # Strain from cycles
    if cycles and "records" in cycles and len(cycles["records"]) > 0:
        latest = cycles["records"][0]
        score = latest.get("score", {})
        if isinstance(score, dict):
            result["strain"] = round(score.get("strain", 0), 1)
            result["avg_hr"] = score.get("average_heart_rate")
            result["max_hr"] = score.get("max_heart_rate")

    # Recovery
    if recovery_data and "records" in recovery_data and len(recovery_data["records"]) > 0:
        latest_rec = recovery_data["records"][0]
        score = latest_rec.get("score", {})
        if isinstance(score, dict):
            result["recovery"] = score.get("recovery_score")
            result["hrv"] = score.get("hrv_rmssd_milli")
            result["rhr"] = score.get("resting_heart_rate")
        elif isinstance(score, (int, float)):
            result["recovery"] = score

    # Sleep
    if sleep_data and "records" in sleep_data and len(sleep_data["records"]) > 0:
        latest_sleep = sleep_data["records"][0]
        score = latest_sleep.get("score", {})
        if isinstance(score, dict):
            stage = score.get("stage_summary", {})
            total_ms = stage.get("total_in_bed_time_milli")
            awake_ms = stage.get("total_awake_time_milli", 0)
            if total_ms:
                actual_sleep_ms = total_ms - awake_ms
                result["sleep_hours"] = round(actual_sleep_ms / 3600000, 1)
            result["sleep_performance"] = score.get("sleep_performance_percentage")

    # Save for website (latest)
    with open(DATA_FILE, "w") as f:
        json.dump(result, f, indent=2)

    # Append to history
    history_file = os.path.join(DIR, "whoop_history.json")
    history = []
    if os.path.exists(history_file):
        with open(history_file) as f:
            history = json.load(f)

    # Only add if different date from last entry
    today = datetime.now().strftime("%Y-%m-%d")
    if not history or history[-1].get("date") != today:
        entry = dict(result)
        entry["date"] = today
        history.append(entry)
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
        print(f"Added to history ({len(history)} days tracked)")

    # Save raw for debugging
    raw = {"cycles": cycles, "recovery": recovery_data, "sleep": sleep_data}
    with open(os.path.join(DIR, "whoop_raw.json"), "w") as f:
        json.dump(raw, f, indent=2)

    print(f"\nWHOOP Data ({result['updated']}):")
    print(f"  Recovery: {result['recovery']}%")
    print(f"  Strain:   {result['strain']}")
    print(f"  Sleep:    {result['sleep_hours']}h")
    print(f"  HRV:      {result['hrv']} ms")
    print(f"  RHR:      {result['rhr']} bpm")
    print(f"\nSaved to {DATA_FILE}")


if __name__ == "__main__":
    main()
