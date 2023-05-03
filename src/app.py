import contextlib
import json
from datetime import datetime, timezone
from uuid import uuid5
from typing import Union
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network

import validators
from lumigo_tracer import lumigo_tracer

import internals
import config
import models
import services.aws


def extract_date(contents: str, ip_address: Union[IPv4Address, IPv4Network, IPv6Address, IPv6Network]) -> Union[datetime, None]:
    for line in contents.splitlines():
        if line.startswith('#') or not line:
            continue

        line_ip, *rest = ' '.join(line.split()).split(' ')
        line_ip = line_ip.strip()
        last_date = rest[2].strip() if rest[2] else None
        last_time = rest[3].strip() if rest[3] else ''
        if not last_date or line_ip == str(ip_address):
            continue
        if not last_time or len(last_time) < 8: # incomplete or missing time
            last_time = '00:00:00'
        if len(last_time) > 8: # ISO date cleanup
            last_time = last_time[:8]
        with contextlib.suppress(Exception):
            return datetime.fromisoformat(f"{last_date}T{last_time}")


def extract_ip_address(line: str) -> Union[IPv4Address, IPv4Network, IPv6Address, IPv6Network, None]:
    if line.startswith('#') or not line:
        return None
    ip_address, *_ = ' '.join(line.split()).split(' ')
    if ip_address := ip_address.strip():
        if validators.ipv4_cidr(ip_address) is True:
            return IPv4Network(ip_address)
        if validators.ipv4(ip_address) is True:
            return IPv4Address(ip_address)
        if validators.ipv6_cidr(ip_address) is True:
            return IPv6Network(ip_address)
        if validators.ipv6(ip_address) is True:
            return IPv6Network(ip_address)


def compare_contents(old_contents: str, new_contents: str):
    old_index = set()
    for line in old_contents.splitlines():
        if ip_address := extract_ip_address(line):
            old_index.add(ip_address)

    for line in new_contents.splitlines():
        ip_address = extract_ip_address(line)
        if ip_address and ip_address not in old_index:
            yield ip_address


@lumigo_tracer(
    token=services.aws.get_ssm(f'/{internals.APP_ENV}/{internals.APP_NAME}/Lumigo/token', WithDecryption=True),
    should_report=internals.APP_ENV == "Prod",
    skip_collecting_http_body=True,
    verbose=internals.APP_ENV != "Prod"
)
def handler(event, context):
    internals.trace_tag({
        "source": event["source"],
        "resources": ",".join([
            e.split(":")[-1] for e in event["resources"]
        ]),
    })
    instance_date = datetime.now(timezone.utc).strftime('%Y%m%d%H')
    results = 0
    for feed in config.feeds:
        if feed.disabled:
            internals.logger.info(f"{feed.name} [magenta]disabled[/magenta]")
            continue
        object_prefix = f"{internals.APP_ENV}/feeds/{feed.source}/{feed.name}/"
        # services.aws.delete_s3(f"{object_prefix}latest.txt")
        last_contents = services.aws.get_s3(path_key=f"{object_prefix}latest.txt")
        file_path = internals.download_file(feed.url)
        if not file_path.exists():
            internals.logger.warning(f"Failed to retrieve {feed.name}")
            continue
        contents = file_path.read_text(encoding='utf8')
        if not contents:
            internals.logger.warning(f"{feed.name} [magenta]no data[/magenta]")
            continue
        services.aws.store_s3(
            path_key=f"{object_prefix}{instance_date}.txt",
            value=contents
        )
        if not last_contents:
            last_contents = ''
            # split contents in half, all are being processed the first time
            contents = "\n".join(contents.splitlines()[:round(len(contents.splitlines())/2)])
            internals.logger.info(f"halving to {round(len(contents.splitlines())/2)} lines -> {feed.name}")
        queued = 0
        for ip_address in compare_contents(last_contents, contents):
            now = datetime.now(timezone.utc).replace(microsecond=0)
            data = models.BruteforceBlocker(
                address_id=uuid5(internals.BRUTE_FORCE_BLOCKER_NAMESPACE, str(ip_address)),
                ip_address=ip_address,
                feed_name=feed.name,
                feed_url=feed.url,
                first_seen=extract_date(contents, ip_address) or now,
                last_seen=now,
            )
            if not data.exists() and data.save() and services.aws.store_sqs(
                queue_name=f'{internals.APP_ENV.lower()}-early-warning-service',
                message_body=json.dumps({**data.dict(), **{'source': feed.source}}, cls=internals.JSONEncoder),
                deduplicate=False,
            ):
                queued += 1
                results += 1
        internals.logger.info(f"{queued} queued records -> {feed.name}")
        services.aws.store_s3(
            path_key=f"{object_prefix}latest.txt",
            value=contents
        )
    internals.logger.info(f"{results} processed records")
