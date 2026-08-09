#!/usr/bin/env python3
"""
One-time local login to bootstrap the persisted Robinhood session the GitHub
Actions bot resumes from (see session_auth.py + .github/workflows/trading-bot.yml).

Run this once from your own machine. It logs in normally, which sends a
device-approval push to your phone — approve it when it arrives. On success it
uploads the resulting session as the RH_SESSION_SEED_B64 GitHub secret, so the
very first CI run has something to resume from. Every run after that persists
its own refreshed session via cache and never touches this secret again — you
should only need to run this script again if the refresh token itself expires
or gets revoked (e.g. after a long idle period).

Requires: gh CLI authenticated locally.
"""
import argparse
import base64
import os
import subprocess
import sys

from dotenv import load_dotenv
import robin_stocks.robinhood as rh

PICKLE_PATH = os.path.expanduser('~/.tokens/robinhood.pickle')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='waziak/robinhood-bot')
    args = parser.parse_args()

    load_dotenv()
    username = os.getenv('RH_USERNAME')
    password = os.getenv('RH_PASSWORD')
    if not username or not password:
        sys.exit("RH_USERNAME / RH_PASSWORD not set in .env")

    if os.path.isfile(PICKLE_PATH):
        os.remove(PICKLE_PATH)  # force a real fresh login, not a stale resume

    print("Logging in — approve the device-approval push on your phone when it arrives...")
    print("(this can take a few minutes; the process is just waiting on you)")
    data = rh.login(username, password, store_session=True)
    if not data or 'access_token' not in data:
        sys.exit(f"Login did not succeed: {data}")

    if not os.path.isfile(PICKLE_PATH):
        sys.exit(f"Login succeeded but no session file was written to {PICKLE_PATH}")

    print("Login succeeded. Uploading session as GitHub secret RH_SESSION_SEED_B64...")
    with open(PICKLE_PATH, 'rb') as f:
        b64 = base64.b64encode(f.read())

    result = subprocess.run(
        ['gh', 'secret', 'set', 'RH_SESSION_SEED_B64', '--repo', args.repo],
        input=b64, capture_output=True
    )
    if result.returncode != 0:
        sys.exit(f"gh secret set failed: {result.stderr.decode()}")

    print(f"Done. RH_SESSION_SEED_B64 is set on {args.repo}. The bot's next CI run "
          f"will resume this session headlessly — no more approvals needed unless "
          f"the refresh token itself expires.")


if __name__ == '__main__':
    main()
