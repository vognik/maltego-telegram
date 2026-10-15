"""
Transform: Profile to IP
Resolves a Telegram user profile to peer IP address via P2P call signaling.
Captures WebRTC ICE candidates during MTProto P2P call initiation.
"""

import asyncio
import atexit
from dataclasses import dataclass
import ipaddress
import json
import logging
import os
import sys
from typing import Dict, List, Optional

from maltego_trx.transform import DiscoverableTransform
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from pyrogram.errors import (
    PeerIdInvalid,
    UserDeactivated,
    UserIsBot,
    UserPrivacyRestricted,
    UsernameInvalid,
    UsernameNotOccupied,
)
from pytgcalls import PyTgCalls
from pytgcalls.types import CallConfig

try:
    from pytgcalls.pytgcalls_session import PyTgCallsSession
    PyTgCallsSession.notice_displayed = True
except Exception:
    pass

from extensions import registry
from client import run_telegram, get_client
from settings import CONNECTION_TIMEOUT
from utils import safe_get_identifier, normalize_identifier


@dataclass(frozen=True)
class Candidate:
    address: str
    port: int
    protocol: str
    kind: str

    @property
    def is_global(self) -> bool:
        return ipaddress.ip_address(self.address).is_global

    @property
    def is_ipv6(self) -> bool:
        return ":" in self.address


def parse_candidate(sdp_string: str) -> Optional[Candidate]:
    """Parse an RFC 5245 / RFC 8445 SDP candidate attribute string into a Candidate object."""
    if not isinstance(sdp_string, str):
        return None

    parts = sdp_string.strip().removeprefix("a=").split()
    if len(parts) < 8 or not parts[0].startswith("candidate:") or parts[6].lower() != "typ":
        return None

    proto = parts[2].lower()
    kind = parts[7].lower()
    address = parts[4].strip("[]")
    port = parts[5]

    if kind not in {"host", "srflx", "prflx", "relay"} or proto not in {"udp", "tcp"}:
        return None

    try:
        ip = ipaddress.ip_address(address)
        port_num = int(port)
    except ValueError:
        return None

    if ip.is_unspecified or ip.is_multicast or not (0 < port_num <= 65535):
        return None

    return Candidate(str(ip), port_num, proto, kind)


class CandidateHandler(logging.Handler):
    """Logging handler intercepting WebRTC signaling candidate payloads."""

    def __init__(self, callback):
        super().__init__(logging.DEBUG)
        self.callback = callback

    def emit(self, record):
        msg = record.getMessage()
        if "processSignalingData" not in msg:
            return
        try:
            sep = "processSignalingData: " if "processSignalingData: " in msg else "processSignalingData:"
            json_part = msg.split(sep, 1)[1]
            payload = json.loads(json_part)
            if isinstance(payload, dict) and payload.get("@type") == "Candidates":
                for item in payload.get("candidates", []):
                    sdp = item.get("sdpString")
                    if sdp and (cand := parse_candidate(sdp)):
                        self.callback(cand)
        except Exception:
            pass


_webrtc_cleanup_registered = False


def _register_webrtc_teardown() -> None:
    """
    Register an exit handler for WebRTC native thread cleanup on Windows.
    Bypasses the loader-lock deadlock in ntgcalls/libwebrtc upon interpreter shutdown.
    """
    global _webrtc_cleanup_registered
    if _webrtc_cleanup_registered:
        return
    _webrtc_cleanup_registered = True

    def _on_exit():
        try:
            from client import _stop_client
            _stop_client()
        except Exception:
            pass

        sys.stdout.flush()
        sys.stderr.flush()

        if sys.platform.startswith("win"):
            try:
                import ctypes
                kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
                kernel32.GetCurrentProcess.restype = ctypes.c_void_p
                kernel32.TerminateProcess(kernel32.GetCurrentProcess(), 0)
            except Exception:
                pass
        os._exit(0)

    atexit.register(_on_exit)


async def fetch_profile_ip(
    identifier: str,
    timeout: Optional[int] = None,
) -> List[Candidate]:
    """
    Initiate a Telegram peer-to-peer call via shared MTProto client and capture ICE candidate IP addresses.
    Terminates the call immediately upon receiving candidate data.
    """
    _register_webrtc_teardown()

    client = get_client()
    clean_id = normalize_identifier(identifier)
    if not clean_id:
        return []

    conn_timeout = timeout if timeout and timeout > 0 else CONNECTION_TIMEOUT
    peer_arg = int(clean_id) if clean_id.lstrip("-").isdigit() else clean_id

    peer = await client.get_users(peer_arg)
    me = await client.get_me()

    if me.is_bot or peer.is_bot or peer.id == me.id:
        return []

    found_event = asyncio.Event()
    all_candidates: List[Candidate] = []

    def on_candidate(c: Candidate):
        if c not in all_candidates:
            all_candidates.append(c)
            # Exit as soon as a public peer IP (host or reflexive) is discovered
            if c.is_global and c.kind != "relay":
                found_event.set()

    handler = CandidateHandler(on_candidate)
    for name in ("ntgcalls", "webrtc"):
        log = logging.getLogger(name)
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)
        log.propagate = False

    calls = PyTgCalls(client)
    await calls.start()
    # Logically track P2P permission from MTProto signaling
    p2p_allowed: Optional[bool] = None
    orig_confirm_call = getattr(calls._app, "confirm_call", None)
    if callable(orig_confirm_call):
        async def hooked_confirm_call(*args, **kwargs):
            nonlocal p2p_allowed
            res = await orig_confirm_call(*args, **kwargs)
            p2p_allowed = getattr(res, "p2p_allowed", None)
            return res

        calls._app.confirm_call = hooked_confirm_call

    in_call = False
    try:
        await calls.play(peer.id, config=CallConfig(timeout=conn_timeout))
        in_call = True

        # Call established.
        # If Telegram protocol indicates P2P is disabled (p2p_allowed is False)
        # or no global non-relay candidate was received, hang up immediately.
        has_personal_ip = any(c.is_global and c.kind != "relay" for c in all_candidates)
        if not has_personal_ip or p2p_allowed is False:
            return []
    finally:
        if in_call:
            try:
                await calls.leave_call(peer.id)
            except Exception:
                pass
        try:
            calls.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        for name in ("ntgcalls", "webrtc"):
            log = logging.getLogger(name)
            try:
                log.removeHandler(handler)
            except Exception:
                pass

    # Filter out relay servers (Telegram TURN relays) and prioritize srflx > prflx > host
    kind_priority = {"srflx": 3, "prflx": 2, "host": 1}
    unique: Dict[str, Candidate] = {}
    for c in all_candidates:
        if c.kind != "relay" and c.is_global:
            existing = unique.get(c.address)
            if existing is None or kind_priority.get(c.kind, 0) > kind_priority.get(existing.kind, 0):
                unique[c.address] = c

    return list(unique.values())


@registry.register_transform(
    display_name="To IP",
    input_entity="interlinked.telegram.UserProfile",
    description="Resolves a Telegram user profile to peer IP address via P2P call signaling",
    output_entities=["maltego.IPv4Address", "maltego.IPv6Address"],
)
class ProfileToIP(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        identifier = (
            safe_get_identifier(request, "properties.username")
            or safe_get_identifier(request, "properties.id")
            or getattr(request, "Value", None)
        )
        if not identifier:
            response.addUIMessage("No user profile specified", messageType="PartialError")
            return

        timeout_setting = request.getTransformSetting("connection_timeout")
        custom_timeout = (
            int(timeout_setting)
            if timeout_setting and timeout_setting.strip().isdigit()
            else None
        )

        try:
            candidates = run_telegram(fetch_profile_ip(identifier, timeout=custom_timeout))
            if not candidates:
                response.addUIMessage(
                    "No public IP address discovered for profile",
                    messageType="Inform",
                )
            else:
                for cand in candidates:
                    entity_type = "maltego.IPv6Address" if cand.is_ipv6 else "maltego.IPv4Address"
                    entity = response.addEntity(entity_type, value=cand.address)
                    entity.addProperty("ipv6-address" if cand.is_ipv6 else "ipv4-address", value=cand.address)
                    entity.addProperty("properties.port", value=str(cand.port))
                    entity.addProperty("properties.protocol", value=cand.protocol.upper())
                    entity.addProperty("properties.type", value=cand.kind)
                    entity.setLinkLabel(f"{cand.protocol.upper()}:{cand.port} ({cand.kind})")
                    entity.setLinkThickness(2)
        except UserPrivacyRestricted:
            response.addUIMessage(
                "Target user's Telegram privacy settings restrict incoming calls",
                messageType="PartialError",
            )
        except (UserIsBot, UserDeactivated):
            response.addUIMessage(
                "Target account is inactive or a bot; calls are not supported",
                messageType="PartialError",
            )
        except (UsernameNotOccupied, PeerIdInvalid, UsernameInvalid):
            response.addUIMessage(
                f"Telegram profile '{identifier}' not found",
                messageType="PartialError",
            )
        except Exception as e:
            response.addUIMessage(f"Error resolving profile IP: {e}", messageType="PartialError")
