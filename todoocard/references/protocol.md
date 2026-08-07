# TodooCard BLE Protocol

## GATT

| UUID | Role |
|------|------|
| `FEF0` | Image service |
| `FEF1` | Control (write / write_no_response / **notify**) |
| `FEF2` | Data (write / write_no_response / notify) |
| `FEF3` | Info read → build timestamp e.g. `Aug  5 2026 03:13:39` |

Secondary (Telink-like OTA fingerprint, not used for image dump):

- Service `00010203-0405-0607-0809-0A0B0C0D1912`
- Char `00010203-0405-0607-0809-0A0B0C0D2B12`

## Control commands

| Op | Meaning |
|----|---------|
| `01` | Request block size → notify `01 F4 00` (size=0xF4=244, payload=240) |
| `02` | Announce length: `02` + u32le(payload_len) + flags |
| `03` | Start transfer |
| `05` | Data ACK / end (`status 00` ok, `08` transfer end) |

Flags: `0x01` = compressed QuickLZ frame; `0x03` = standard raw.

## Data packets

```
[index u32le][payload ≤ 240 bytes]
```

ATT write total ≤ **244** bytes. Larger → `prepare queue is full`.

## Image pipeline

1. Cover-resize to 528×792  
2. Six-color Floyd–Steinberg (palette RGB nearest)  
3. Optional mount orientation: `rotate-180-then-flip-horizontal`  
4. Pack nibbles → `.bin` (209088 bytes)  
5. SE0368 controller transform  
6. QuickLZ **stored** framing → `.protocol.qlz`  
   - header `00 00 00 00`  
   - repeat: `74 43 40` + 64 raw bytes  

## Safe send policy

`apple-bluetooth` CLI is multi-process; notify/write race exists.

**Never resume mid-frame.** Horizontal stripes = index desync after reconnect resume.

On any write failure: abort, reconnect, full handshake, send entire qlz again.

Recommended pace: `0` (no extra delay). CLI with_response ≈ 65ms/block hard floor.  
wait_refresh default: `8` (panel may still be finishing).

## 性能与传输

- `apple-bluetooth` CLI 每个 240B 数据块都是独立进程调用，实际返回 `write_type=with_response`；实测单块约 90ms，因此 913 块约 80–90 秒。
- 已跳过已知 block size 的 notify 探测，并移除额外 `pace`；仍无法绕过 CLI/with-response 固定开销。
- 40 秒是面板刷新等待，不是 BLE 写入速度。
- 原生实现已加入 `scripts/native_sender.swift`：单个 CoreBluetooth 长连接，数据包使用 `writeValue(..., type: .withoutResponse)`，并由 `canSendWriteWithoutResponse` 流控；在 macOS 编译后 CLI 会自动优先使用它。
- 当前 iSH/Linux 无法链接 Apple CoreBluetooth，因此本机仍自动回退到 CLI 发送器。

## Faults

| Symptom | Cause | Fix |
|---------|--------|-----|
| Horizontal stripes | Mid-frame resume | Full re-push only |
| Connect timeout | Sleep/out of range | scan wake, retry, bring card closer |
| prepare queue full | block>240 | use 240 |
| Upside-down / mirror | Wrong orientation | toggle config orientation |
| Notify empty | write before subscribe | safe_send discovers size best-effort; default 240 |

## Config keys

`/var/minis/shared/todoocard/config.json`:

```json
{
  "device_id": "…",
  "device_name": "NEWSTONE",
  "screen_orientation": "rotate-180-then-flip-horizontal",
  "block_size": 240,
  "pace": 0.012
}
```
