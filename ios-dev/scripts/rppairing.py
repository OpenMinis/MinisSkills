"""rppairing.py — Minimal implementation of the RemotePairing protocol (host side, Pair-Verify + createListener).

It only handles protocol bytes: no threads, no subprocesses, no pymobiledevice3 dependency, so every function can be unit-tested offline.

Wire format (the iOS 17+ remoted RSD entry point, default 10.7.0.1:49152):
    frame   = b"RPPairing" + big-endian uint16 length + JSON
    handshake = plain message, hostOptions.attemptPairVerify = true
    M1/M3   = TLV8 placed in base64, kind is verifyManualPairing
    The session keys are derived from the X25519 shared secret via HKDF-SHA512, and payloads use ChaCha20-Poly1305
    After Pair-Verify completes, send createListener so the device opens a TLS-PSK channel on a new port

Protocol basis: reading the remote_pairing source of idevice (MIT, Rust), plus capture verification on a real device.
"""
import base64
import json
import os
import plistlib
import struct
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"RPPairing"
WIRE_PROTOCOL_VERSION = 19

# TLV8 tags (HomeKit style)
T_IDENTIFIER, T_PUBLIC_KEY, T_ENCRYPTED, T_STATE, T_SIGNATURE = 1, 3, 5, 6, 10


class PairingError(Exception):
    """The pairing record is bad, or the device rejected Pair-Verify."""


# ───────────────────────── pairing record ─────────────────────────
def find_pairing_file(explicit=None):
    """Find the pairing file by priority: explicit argument → env var IOSDEV_PAIRING_FILE (legacy name CDTK_PAIRING_FILE also accepted) → ~/.cdtk/pairing/*.plist (newest)."""
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("IOSDEV_PAIRING_FILE") or os.environ.get("CDTK_PAIRING_FILE")   # the latter is the old name, still supported
    if env:
        return Path(env).expanduser()
    d = Path.home() / ".cdtk" / "pairing"
    cands = sorted(d.glob("*.plist"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []
    if cands:
        return cands[0]
    raise PairingError(
        "No pairing file found. Put one in ~/.cdtk/pairing/*.plist (mode 600), or set the CDTK_PAIRING_FILE environment variable. "
        "See references/pairing.md for how to obtain one.")


def load_pairing(path=None):
    """Read and validate the pairing file, returning {'identifier': str, 'private_key': bytes(32)}.

    Only the RemotePairing format (iOS 17+) is accepted. Legacy lockdown records (HostID/EscrowBag etc.) cannot be used and raise a clear error.
    """
    p = find_pairing_file(path)
    if not p.is_file():
        raise PairingError(f"pairing file does not exist: {p}")
    try:
        d = plistlib.loads(p.read_bytes())
    except Exception as e:
        raise PairingError(f"pairing file is not a valid plist: {p} ({type(e).__name__})") from e
    missing = [k for k in ("identifier", "private_key", "public_key") if k not in d]
    if missing:
        hint = "This looks like a legacy lockdown record, which cannot be used for iOS 17+ RemotePairing." if "HostID" in d or "EscrowBag" in d else ""
        raise PairingError(f"pairing file is missing fields {missing}. {hint}")
    ident, priv = d["identifier"], d["private_key"]
    if not isinstance(ident, str) or not ident:
        raise PairingError("identifier must be a non-empty string")
    if not isinstance(priv, (bytes, bytearray)) or len(priv) != 32:
        raise PairingError(f"private_key must be 32 bytes (Ed25519), got {len(priv) if hasattr(priv, '__len__') else '?'}")
    return {"identifier": ident, "private_key": bytes(priv)}


# ───────────────────────── TLV8 ─────────────────────────
def tlv8_encode(items):
    """items: [(tag, bytes), ...]. A single value longer than 255 bytes is split into multiple segments with the same tag (the receiver joins them back)."""
    out = bytearray()
    for tag, val in items:
        if not val:
            out += bytes([tag, 0])
            continue
        for i in range(0, len(val), 255):
            chunk = val[i:i + 255]
            out += bytes([tag, len(chunk)]) + chunk
    return bytes(out)


def tlv8_decode(data):
    """Return {tag: bytes}. Multiple segments with the same tag are concatenated in order. Raises PairingError if the data is truncated."""
    res, i = {}, 0
    while i < len(data):
        if i + 2 > len(data):
            raise PairingError("TLV8 is truncated (missing length byte)")
        tag, ln = data[i], data[i + 1]
        if i + 2 + ln > len(data):
            raise PairingError("TLV8 is truncated (incomplete value)")
        res[tag] = res.get(tag, b"") + data[i + 2:i + 2 + ln]
        i += 2 + ln
    return res


# ───────────────────────── frames ─────────────────────────
def frame(obj):
    body = json.dumps(obj, separators=(",", ":")).encode()
    if len(body) > 0xFFFF:
        raise ValueError("frame too large")
    return MAGIC + struct.pack(">H", len(body)) + body


async def read_frame(reader):
    head = await reader.readexactly(len(MAGIC) + 2)
    if head[:len(MAGIC)] != MAGIC:
        raise PairingError(f"bad frame header: {head[:len(MAGIC)]!r} (the peer is not a RemotePairing service)")
    (ln,) = struct.unpack(">H", head[len(MAGIC):])
    return json.loads((await reader.readexactly(ln)).decode())


def _plain(seq, payload):
    return frame({"message": {"plain": {"_0": payload}}, "originatedBy": "host", "sequenceNumber": seq})


def _pairing_event(tlv, new_session, kind="verifyManualPairing"):
    """pairing-data event. new_session: True for the first one (M1), must be False for the following ones (M3), otherwise the device drops the connection."""
    return {"event": {"_0": {"pairingData": {"_0": {
        "data": base64.b64encode(tlv).decode(), "kind": kind, "startNewSession": new_session}}}}}


def _hkdf(secret, salt, info, length=32):
    return HKDF(algorithm=hashes.SHA512(), length=length, salt=salt, info=info).derive(secret)


# ───────────────────────── Pair-Verify ─────────────────────────
async def pair_verify(reader, writer, record):
    """Complete the handshake and Pair-Verify, returning (shared secret, client key, server key). Raises PairingError when the device rejects."""
    # Handshake: tell the device we want pair-verify
    hello = {"request": {"_0": {"handshake": {"_0": {
        "hostOptions": {"attemptPairVerify": True}, "wireProtocolVersion": WIRE_PROTOCOL_VERSION}}}}}
    writer.write(_plain(0, hello)); await writer.drain()
    await read_frame(reader)

    # M1: our ephemeral X25519 public key
    eph = X25519PrivateKey.generate()
    eph_pub = eph.public_key().public_bytes_raw()
    m1 = tlv8_encode([(T_STATE, b"\x01"), (T_PUBLIC_KEY, eph_pub)])
    writer.write(_plain(1, _pairing_event(m1, True))); await writer.drain()

    # M2: the device's X25519 public key
    r2 = await read_frame(reader)
    try:
        data2 = base64.b64decode(r2["message"]["plain"]["_0"]["event"]["_0"]["pairingData"]["_0"]["data"])
    except (KeyError, TypeError) as e:
        raise PairingError(f"unexpected M2 structure: {str(r2)[:160]}") from e
    dev_pub = tlv8_decode(data2).get(T_PUBLIC_KEY)
    if not dev_pub or len(dev_pub) != 32:
        raise PairingError("M2 contains no valid device public key")
    shared = eph.exchange(X25519PublicKey.from_public_bytes(dev_pub))
    enc_key = _hkdf(shared, b"Pair-Verify-Encrypt-Salt", b"Pair-Verify-Encrypt-Info")

    # M3: sign (our ephemeral public key ‖ identity ‖ device public key) with the Ed25519 private key from the pairing record, then encrypt
    ident = record["identifier"].encode()
    sig = Ed25519PrivateKey.from_private_bytes(record["private_key"]).sign(eph_pub + ident + dev_pub)
    sealed = ChaCha20Poly1305(enc_key).encrypt(b"\x00\x00\x00\x00PV-Msg03",
                                               tlv8_encode([(T_IDENTIFIER, ident), (T_SIGNATURE, sig)]), b"")
    m3 = tlv8_encode([(T_STATE, b"\x03"), (T_ENCRYPTED, sealed)])
    writer.write(_plain(2, _pairing_event(m3, False))); await writer.drain()

    # M4: state=4 means the device accepted this pairing record
    r4 = await read_frame(reader)
    try:
        data4 = base64.b64decode(r4["message"]["plain"]["_0"]["event"]["_0"]["pairingData"]["_0"]["data"])
    except (KeyError, TypeError) as e:
        raise PairingError(f"unexpected M4 structure: {str(r4)[:160]}") from e
    if tlv8_decode(data4).get(T_STATE) != b"\x04":
        raise PairingError("The device did not accept this pairing record (Pair-Verify failed). Common causes: the pairing was deleted on the phone, "
                           "the phone was reset, or the pairing file belongs to another device.")

    client_key = _hkdf(shared, None, b"ClientEncrypt-main")
    server_key = _hkdf(shared, None, b"ServerEncrypt-main")
    return shared, client_key, server_key


# ───────────────────────── createListener ─────────────────────────
def _nonce(counter):
    return struct.pack("<Q", counter) + b"\x00\x00\x00\x00"


async def create_listener(reader, writer, psk, client_key, server_key, seq=3):
    """Ask the device to open a TLS-PSK channel on a new port and return the port number. psk is the random 32 bytes we generated."""
    req = {"request": {"_0": {"createListener": {
        "key": base64.b64encode(psk).decode(), "transportProtocolType": "tcp",
        "peerConnectionsInfo": [{"owningPID": os.getpid(), "owningProcessName": "CoreDeviceService"}]}}}}
    sealed = ChaCha20Poly1305(client_key).encrypt(_nonce(0), json.dumps(req).encode(), b"")
    writer.write(frame({"message": {"streamEncrypted": {"_0": base64.b64encode(sealed).decode()}},
                        "originatedBy": "host", "sequenceNumber": seq}))
    await writer.drain()

    env = await read_frame(reader)
    try:
        enc = base64.b64decode(env["message"]["streamEncrypted"]["_0"])
        resp = json.loads(ChaCha20Poly1305(server_key).decrypt(_nonce(0), enc, b""))
        return int(resp["response"]["_1"]["createListener"]["port"])
    except Exception as e:
        raise PairingError(f"cannot parse the createListener response: {type(e).__name__}: {str(env)[:140]}") from e
