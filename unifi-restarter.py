#!/usr/bin/python3

from types import NoneType
from xmlrpc.client import Boolean
import unificontrol
import sys
import argparse
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
    args.add_argument("--host", help="Unifi controller hostname (optionally suffixed with :port)", type=str, required=True)
    args.add_argument("--user", help="Unifi console username", type=str, required=True)
    args.add_argument("--password", help="Unifi console password", type=str, required=True)
    args.add_argument("--site", help="Unifi site name (default: 'default')", type=str, default="default")
    args.add_argument("--uptime-limit", help="Restart accesspoints after this amount of days (default: 50)", type=int, default=50)
    args.add_argument("--batch-size", help="Restart this amount of accesspoints per script invocation (default: 5)", type=int, default=5)
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

def restart_batch(client: unificontrol.UnifiClient, uaps_overdue: List[AP], restart_batch_size: int, dry_run: Boolean) -> None:
    uap_restart_batch = uaps_overdue[:restart_batch_size]
    print(f"Selected the following APs for restart in this round: {uap_restart_batch}")
    for ap in uap_restart_batch:
        if dry_run:
            print(f" Not Restarting AP {ap} (dry-run mode)")
        else:
            print(f" Restarting AP {ap}")
            client.restart_ap(ap.mac)

def main():
    args = parse_args()
    
    client = unificontrol.UnifiClient(host=args.host, username=args.user, password=args.password, site=args.site)

    _, uaps_overdue = get_aps(client, args.uptime_limit, args.batch_size)

    if not uaps_overdue:
        print("Everything is fine, not restarting anything today. Good-Bye!")
        sys.exit(0)

    restart_batch(client, uaps_overdue, args.batch_size, args.dry_run)


if __name__ == "__main__":
    main()
