#!/usr/bin/env python3

import argparse
import ipaddress
import sys


def load_entries(path):
    entries = set()

    try:
        with open(path, encoding="utf-8") as source:
            for raw_line in source:
                line = raw_line.split("#", 1)[0].strip().lower().rstrip(".")
                if line:
                    entries.add(line)
    except FileNotFoundError:
        pass

    return entries


def domain_is_whitelisted(domain, whitelist):
    domain = domain.strip().lower().rstrip(".")

    return any(
        domain == allowed or domain.endswith("." + allowed)
        for allowed in whitelist
    )


def load_ip_networks(path):
    networks = []

    for entry in load_entries(path):
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError as error:
            print(
                f"Warning: invalid whitelist IP/network {entry!r}: {error}",
                file=sys.stderr,
            )

    return networks


def ip_is_whitelisted(value, networks):
    try:
        candidate = ipaddress.ip_network(value.strip(), strict=False)
    except ValueError:
        return False

    return any(candidate.subnet_of(network) for network in networks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=("domain", "ip"), required=True)
    parser.add_argument("--whitelist", required=True)
    args = parser.parse_args()

    if args.type == "domain":
        whitelist = load_entries(args.whitelist)

        for line in sys.stdin:
            value = line.strip()
            if value and not domain_is_whitelisted(value, whitelist):
                print(value)

    else:
        whitelist = load_ip_networks(args.whitelist)

        for line in sys.stdin:
            value = line.strip()
            if value and not ip_is_whitelisted(value, whitelist):
                print(value)


if __name__ == "__main__":
    main()
