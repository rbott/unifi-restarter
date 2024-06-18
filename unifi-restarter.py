#!/usr/bin/python3

from types import NoneType
from xmlrpc.client import Boolean
import unificontrol
import sys
import argparse
from slack_webhook import Slack
from typing import List, Tuple

class AP:
    def __init__(self, name: str, mac: str, uptime: int):
        self.name = name
        self.mac = mac
        self.uptime = uptime

    def __str__(self):
        return f"{self.name} ({self.mac})"

    def __repr__(self):
        return f"{self.name} ({self.mac})"


def parse_args() -> argparse.Namespace:
    args = argparse.ArgumentParser()
    args.add_argument("--host", help="Unifi controller hostname", type=str, required=True)
    args.add_argument("--port", help="Unifi controller port (default: 8443)", type=int, default=8443)
    args.add_argument("--user", help="Unifi console username", type=str, required=True)
    args.add_argument("--password", help="Unifi console password", type=str, required=True)
    args.add_argument("--list-sites", help="List all known sites and exit", action="store_true", default=False)
    args.add_argument("--site", help="Unifi site name (default: 'default')", type=str, default="default")
    args.add_argument("--uptime-limit", help="Restart accesspoints after this amount of days (default: 50)", type=int, default=50)
    args.add_argument("--batch-size", help="Restart this amount of accesspoints per script invocation (default: 5)", type=int, default=5)
    args.add_argument("--slack-webhook", help="Slack Webhook URL - enables output to slack channels", required=False, default=None)
    args.add_argument("--dry-run", help="Do not actually restart anything", action="store_true", default=False)
    return args.parse_args()


def get_aps(client: unificontrol.UnifiClient, restart_day_limit: int, restart_batch_size:int) -> Tuple[List[AP], List[AP]]:
    devices = client.list_devices()
    online_list = [item for item in devices if item["state"]]
    uap_list = [item for item in online_list if item["type"] == "uap"]
    print(f"{len(online_list)}/{len(devices)} device are online and {len(uap_list)} devices are accesspoints")
    uaps_overdue = []
    uaps_good = []
    for ap in uap_list:
        uptime_days = round(ap["uptime"] / 60 / 60 / 24)
        if uptime_days >= restart_day_limit:
            uaps_overdue.append(AP(ap["name"], ap["mac"], ap["uptime"]))
        else:
            uaps_good.append(AP(ap["name"], ap["mac"], ap["uptime"]))

    print(f"Uptime limit: {restart_day_limit} days, Restart Batch Size {restart_batch_size}")
    print(f"Overdue: {uaps_overdue}")
    print(f"Good: {uaps_good}")
    return (uaps_good, uaps_overdue)


def restart_batch(client: unificontrol.UnifiClient, uaps_overdue: List[AP], restart_batch_size: int, dry_run: Boolean, slack_webhook: str) -> None:
    uap_restart_batch = uaps_overdue[:restart_batch_size]
    msg = f"Selected the following APs for restart in this round: {uap_restart_batch}"
    print(msg)
    if slack_webhook:
        print("Sending restart summary message to Slack")
        slack = Slack(url=slack_webhook)
        slack.post(text=msg)
    for ap in uap_restart_batch:
        if dry_run:
            print(f" Not Restarting AP {ap} (dry-run mode)")
        else:
            print(f" Restarting AP {ap}")
            client.restart_ap(ap.mac)


def list_sites(client: unificontrol.UnifiClient) -> None:
    print("Listing all sites known to the controller:")
    for site in client.list_sites():
        print(f" - {site['desc']} (ID: {site['name']})")


def main():
    args = parse_args()
    
    try:
        client = unificontrol.UnifiClient(host=args.host, port=args.port, username=args.user, password=args.password, site=args.site)

        if args.list_sites:
            list_sites(client)
            sys.exit(0)

        _, uaps_overdue = get_aps(client, args.uptime_limit, args.batch_size)

        if not uaps_overdue:
            print("Everything is fine, not restarting anything today. Good-Bye!")
            sys.exit(0)

        restart_batch(client, uaps_overdue, args.batch_size, args.dry_run, args.slack_webhook)
    except Exception as e:
        print(f"{type(e).__name__}: {e}")
        if args.slack_webhook:
            print("Posting error message to slack")
            slack = Slack(url=args.slack_webhook)
            slack.post(text=f"Error Running unifi-restarter.py:\n{type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
