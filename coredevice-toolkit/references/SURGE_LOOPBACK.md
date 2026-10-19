# Surge Local Loopback Configuration Guide

**[English](SURGE_LOOPBACK.md)** | **[中文说明](SURGE_LOOPBACK_zh.md)**

This guide details how to configure Surge iOS as a local loopback reflector for CoreDevice RSD.

---

## 1. Principles
On non-jailbroken iOS, normal applications cannot establish unauthenticated developer RPC connections to `127.0.0.1`.
Surge provides high-performance packet rewriting and TUN routing. By configuring `10.7.0.1` as `reflect` (loopback reflection) and routing it through the TUN virtual interface, packets sent to this virtual address are reflected back into the device's incoming network stack, safely establishing a loopback developer tunnel without a computer.

---

## 2. Surge Configuration

### Method A: Direct Configuration in `Default.conf` (Recommended)
Add the following lines to your Surge configuration profile:

```ini
[General]
# Capture 10.7.0.1 into TUN interface
tun-included-routes = %APPEND% 10.7.0.1/32

# Preserve raw TCP stream for Apple pairing protocol
always-raw-tcp-keywords = %APPEND% "Content-Type: application/pairing+tlv8"

[IP Rewrite]
# Reflect packets directed to 10.7.0.1 back to the device network stack
10.7.0.1 = reflect
```

### Method B: Standalone Module (`Surge-CoreDevice.sgmodule`)
Import and enable the bundled module:

```ini
#!name=CoreDevice RSD Local Loopback
#!desc=Enables on-device loopback reflection for CoreDevice RSD developer tunnels

[General]
tun-included-routes = %APPEND% 10.7.0.1/32
always-raw-tcp-keywords = %APPEND% "Content-Type: application/pairing+tlv8"

[IP Rewrite]
10.7.0.1 = reflect
```

---

## 3. Safety & Zero Conflict Analysis

1. **`tun-included-routes = 10.7.0.1/32`**:
   - **Scope**: Strictly limited to a single `/32` IP (`10.7.0.1`);
   - **Side Effects**: Scoped to that single host route. It does not intentionally capture LAN or internet traffic; review your own rule order if you use a custom profile.
2. **`always-raw-tcp-keywords = "Content-Type: application/pairing+tlv8"`**:
   - **Scope**: Only instructs Surge to bypass TLS MitM decryption when Apple's specific pairing Content-Type is matched;
   - **Side Effects**: Normal HTTPS websites and APIs never use this content type; general web decryption and ad-blocking remain unaffected.

---

## 4. Verification
Test connectivity using `cdtk-doctor` or:
```bash
nc -zv 10.7.0.1 49152
```
When it outputs `open`, the port is reachable. This does not prove the Pair-Verify handshake works; run `cdtk-doctor` for the full check.
