"""
WHOOP OAuth2 Authentication
Run this once to get your access + refresh tokens.
"""

import http.server
import urllib.parse
import urllib.request
import json
import webbrowser
import getpass
import os

CLIENT_ID = "***REDACTED_CLIENT_ID***"
REDIRECT_URI = "http://localhost:3000/callback"
AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
SCOPES = "read:recovery read:sleep read:workout read:cycles read:profile"

# Ask for secret securely (not saved in code)
CLIENT_SECRET = input("Paste your WHOOP Client Secret: ").strip()

auth_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="background:#050505;color:#e4e4e7;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;">
                <div style="text-align:center;">
                <h1>connected.</h1>
                <p style="color:#3f3f46;">you can close this tab.</p>
                </div></body></html>
            """)
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Error: no code received")

    def log_message(self, format, *args):
        pass  # suppress server logs


def main():
    # Step 1: Open browser for authorization
    auth_params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": "nextelite"
    })

    auth_link = f"{AUTH_URL}?{auth_params}"
    print("\nOpening WHOOP authorization in your browser...")
    print(f"If it doesn't open, go to:\n{auth_link}\n")
    webbrowser.open(auth_link)

    # Step 2: Start local server to catch the callback
    server = http.server.HTTPServer(("localhost", 3000), CallbackHandler)
    print("Waiting for WHOOP authorization...")

    while auth_code is None:
        server.handle_request()

    server.server_close()
    print("Authorization code received.\n")

    # Step 3: Exchange code for tokens
    token_data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }).encode("utf-8")

    req = urllib.request.Request(TOKEN_URL, data=token_data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("User-Agent", "NextEliteProtocol/1.0")

    try:
        with urllib.request.urlopen(req) as resp:
            tokens = json.loads(resp.read().decode())

        # Save tokens securely (local only, gitignored)
        token_file = os.path.join(os.path.dirname(__file__), ".whoop_tokens.json")
        with open(token_file, "w") as f:
            json.dump(tokens, f, indent=2)

        print("WHOOP connected.")
        print(f"Tokens saved to: {token_file}")
        print(f"Access token expires in: {tokens.get('expires_in', '?')} seconds")
        print("\nRun whoop_fetch.py to pull your data.")

    except urllib.error.HTTPError as e:
        print(f"Error: {e.code}")
        print(e.read().decode())


if __name__ == "__main__":
    main()
