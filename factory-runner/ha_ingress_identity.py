"""Trust boundary for Home Assistant ingress identity.

Only the Supervisor ingress proxy may reach the ingress listener. Identity
headers are trusted only after the TCP peer is verified as 172.30.32.2.
This module does not start a listener or enable ingress by itself.
"""
from __future__ import annotations

import hmac
import ipaddress
import re
from collections.abc import Mapping

SUPERVISOR_INGRESS_PEER = ipaddress.ip_address("172.30.32.2")
INGRESS_PATH_PREFIX = "/api/hassio_ingress/"
_INGRESS_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def _single_header(headers, wanted: str) -> str | None:
    """Read exactly one header, case-insensitively; duplicates fail closed."""
    if not hasattr(headers, "items"):
        return None
    values = [
        str(value)
        for name, value in headers.items()
        if str(name).lower() == wanted.lower()
    ]
    if len(values) != 1:
        return None
    value = values[0]
    if not value or value != value.strip() or any(ch.isspace() for ch in value):
        return None
    return value


def _valid_ingress_path(value: str | None) -> bool:
    if not value or not value.startswith(INGRESS_PATH_PREFIX):
        return False
    token = value[len(INGRESS_PATH_PREFIX):]
    if token.endswith("/"):
        token = token[:-1]
    return bool(_INGRESS_TOKEN.fullmatch(token))


def is_supervisor_ingress_peer(peer_ip) -> bool:
    """Return true only for the Supervisor's fixed ingress proxy address."""
    try:
        return ipaddress.ip_address(peer_ip) == SUPERVISOR_INGRESS_PEER
    except (TypeError, ValueError):
        return False


def verify_ha_ingress_context(
    context,
    *,
    expected_ha_user_id: str,
    owner_id: str,
) -> str | None:
    """Return the configured owner ID only for a verified Supervisor session.

    Never use X-Forwarded-For, X-Forwarded-Proto, Authorization, or a browser
    supplied identity header as a substitute for the actual TCP peer check.
    """
    if not isinstance(context, Mapping):
        return None
    if (not isinstance(expected_ha_user_id, str) or not expected_ha_user_id
            or expected_ha_user_id != expected_ha_user_id.strip()
            or any(ch.isspace() for ch in expected_ha_user_id)
            or not isinstance(owner_id, str) or not owner_id
            or owner_id != owner_id.strip() or any(ch.isspace() for ch in owner_id)):
        return None

    if not is_supervisor_ingress_peer(context.get("peer_ip")):
        return None

    headers = context.get("headers")
    remote_user_id = _single_header(headers, "X-Remote-User-Id")
    ingress_path = _single_header(headers, "X-Ingress-Path")
    if not _valid_ingress_path(ingress_path):
        return None
    if not remote_user_id or not hmac.compare_digest(
        remote_user_id, expected_ha_user_id
    ):
        return None
    return owner_id
