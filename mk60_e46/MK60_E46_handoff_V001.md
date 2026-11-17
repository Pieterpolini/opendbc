# MK60 (BMW E46) standalone — handoff V001

Date: 2026-11-17. Status: **research only, nothing measured yet.** V001 adds §10 (cmg5461/mk60e5-firmware reviewed).
Legend: **V** = verified (source read), **F** = forum/anecdotal, **U** = unverified (memory/assumption, must be measured).

## 1. Goal

| Item | Target |
|---|---|
| Cars | BMW E28 (MaxxECU, sends full E46 CAN protocol), BMW E24; later Saab 9000 |
| Unit | Teves MK60 ABS/DSC from BMW E46 |
| Function wanted | ABS only. Brakes + yaw sensor stay. Steering angle sensor (LWS) removed if possible. DSC/ASC/TCS in MK60 off; traction control in MaxxECU |
| Output wanted | 4 wheel speeds into MaxxECU; ABS-OK status → lamp via MaxxECU |

## 2. Tools

| Purpose | Hardware | Software | Status |
|---|---|---|---|
| Coding / diagnosis (K-line, address DSC) | K+DCAN USB (owned) | INPA, NCS Expert, EDIABAS | Sufficient |
| CAN logging / emulation (PT-CAN 500 kbit/s) | CANable / PCAN / Kvaser, or MaxxECU CAN | SavvyCAN, cantools, candump | **Adapter still needed** (or use MaxxECU CAN log) |

## 3. Frames to MK60 (minimum)

| ID | Name | Rate | Content | Static OK? | Status |
|---|---|---|---|---|---|
| 0x316 | DME1 | 10 ms | KL15/status, RPM = bytes 2-3 (LE) / 6.4, torque | Probably | F |
| 0x329 | DME2 | 10 ms | Coolant temp, pedal, cruise (byte 3); byte 0 = counter/mux, "key to keep DSC happy" | Doubtful | F |
| 0x545 | DME4 | 10 ms | Lamps/status | Probably | F |

Conflicting reports: MK60 runs ABS without any CAN (lamps on) vs. silent until woken by 0x316. KL15 pin must be wired. **E28: keep MaxxECU E46 protocol (dynamic) — safest.**

Bench test order (E24): (1) power + KL15, no TX → does 0x1F0 appear? (2) static 0x316 only (3) static 0x316+0x329+0x545 (4) fall back to MaxxECU dynamic protocol.

## 4. Frames from MK60

| ID | Name | Content | Layout (candidate) | Status |
|---|---|---|---|---|
| 0x1F0 | ASC2 | Wheel speeds FL, FR, RL, RR | bytes 0-1 / 2-3 / 4-5 / 6-7, little endian, low 12-13 bits, 0.0625 km/h/bit | U |
| 0x153 | ASC1 | Vehicle speed, ASC/MSR requests, lamp/fault bits | speed start bit 12, 12 bit, 0x08 = 1 km/h (F); lamp bits unknown | F/U |
| 0x1F3 / 0x1F5 / 0x1F8 | — | Accel / steering angle (LWS) / brake pressure | unknown | U |

MaxxECU RX setting (candidate): User CAN RX, ID 0x1F0, 16 bit, little endian, mask 0x0FFF (try 0x1FFF), factor 0.0625 → km/h.

## 5. ABS status → lamp

| Option | Method | Status |
|---|---|---|
| A | Status bit in 0x153 (or other): log, unplug one wheel sensor, find the bit that flips | To measure |
| B | MaxxECU logic: lamp ON if any wheel deviates > 90 % from mean of other three while speed > 10 km/h, OR 0x1F0 timeout (> 200 ms) | Use now; also for Saab 9000 |

## 6. Coding / parameters

| What | How | Possible? | Status |
|---|---|---|---|
| Variant/datafile (`MK60_`, `MK60_M3`, `_87`, `_M82`) | NCS Expert, profile that allows edits (FISTER / Revtor) | Yes | F |
| Code as ASC variant without LWS/yaw | NCS — check if datafile exists | Unknown | U |
| DTC read/clear, LWS/yaw/pressure zero, bleed | INPA | Yes | F |
| Slip thresholds / pressure strategy | Firmware hack only | Practically no | F |
| **Back up original TRC before any change** | NCS Expert | Required | F |

Known issues (F): NCS sometimes doesn't see MK60 while INPA does (often VIN mismatch); re-coding can get blocked.

## 7. LWS / TCS

| Topic | Advice | Status |
|---|---|---|
| Remove LWS | DSC yaw control lost + DTC; ABS reportedly keeps working | F |
| MK60 ASC/DSC | Off — its torque requests aren't honoured by MaxxECU | Advice |
| DSC off method | E9x MK60E5: button to ground, hold 0.5 s; resets at each start. E46 same? | U |
| Traction control | MaxxECU, based on 4 wheel speeds | Advice |

## 8. Next steps (on laptop/PC121)

0. **Decide which unit**: read the part number / INPA ident. E46 MK60 → steps 1–6. MK60**E5** (E9x/E8x/E85) → §10 path (much better documented).
1. Get CAN log from E28 (MaxxECU bus log or adapter): idle, roll each wheel by hand, unplug one sensor, DSC button.
2. Decode with `mk60_e46/e46_mk60_V000.dbc`; confirm 0x1F0 layout + scale vs GPS.
3. Find ABS fault/lamp bit → save as `e46_mk60_V001.dbc`.
4. INPA: read DTCs + datafile name. NCS: back up TRC.
5. Configure MaxxECU: RX wheel speeds, lamp logic (option B), traction control.
6. E24 bench test per §3.

## 9. Sources

| Source | Covers | Read? |
|---|---|---|
| github.com/tomazcebul/MK60e5-Standalone | MK60**E5** (E9x) — different unit/IDs | Read (V for E5 only) |
| github.com/cmg5461/mk60e5-firmware (MIT, last commit 2026-11-02) | MK60**E5** M3 7846816A: min. frames, E46-sensor patch, ABS tuning | Read — see §10 |
| miataturbo.net MK60 installation guide p15/16 | Standalone handshake 0x610/0x316/0x329/0x613/0x615 | Search snippet only |
| m3forum.net MK60 DSC thread | ABS works without CAN | Snippet |
| rusefi.com forum t=2454 | 0x316 wake-up | Snippet |
| forum.e46fanatics.com p=14815659 | 0x153 / 0x1F0 | Snippet |
| romraider.com p=117679 | 0x316/0x329/0x545 | Snippet |
| bimmerforums MK60 CAN thread (p=25012791) | 0x329 byte 0, counters | Snippet |
| nam3forum MK60 swap coding / track mode | NCS coding | Snippet |
| racehuggins.com E46 DSC pdf; shiftbmw E46 traction pdf | System description | Not read |

## 10. Source review: cmg5461/mk60e5-firmware (V001)

Applies to **MK60E5, E9x M3 firmware 7846816A** — NOT the E46 MK60. Repo derives everything from disassembly; tags below are the repo's own (verified = bench-tested by author, otherwise code-read).

### 10.1 Key findings

| Topic | Finding | Repo status |
|---|---|---|
| Min. PT-CAN frames (ABS on, DSC off, no DTCs) | 0x130 (ign.), 0x0A8/0x0A9/0x0AA (DME idle), 0x3B0 (manual) or 0x0BA (DCT), 0x310 + 0x330 (cluster), 0x398 `00 04` (DSC off, ~100 ms) | Code-read, not checked on unit |
| Static content? | **No**: every frame needs a 4-bit alive counter (0–14) + checksum; constant *values* are fine | Code-read |
| Timeouts | Monitoring starts ~750 ms after ign. on; 500 ms timeout for 0x130/0x0A8–0x0AA | Code-read |
| Ignition off (no 0x130 / KL15 off) | No CAN DTCs, ABS still runs but degraded (no long. accel, wheel-speed estimate) | Code-read |
| Wheel speeds out | 0x0CE, DLC 8, 20 ms, 4× s16 FL/FR/RL/RR, **raw/16 = km/h** | Verified (bench) |
| ABS status for lamp | **0x19E byte 1 bits 0–1 = 0 → ABS OK**; bits 2–4: 1 = DSC off, 2 = DSC failed. Lamp state is CAN-only (no lamp pin) | Code-read; lamp CAN-only verified |
| Steering sensor (F-CAN 0x0C9) missing | Yaw + lateral marked invalid, yaw control + all traction control off; ABS keeps running with long. accel; rear axle select-low | Code-read |
| E46 sensors on MK60E5 | 4-byte firmware patch + re-sign → E46 2-level (7/14 mA) sensors work on all 4 wheels | Bench-verified, not car-tested |
| ABS tuning | Full map of dump/hold/reapply parameters (`docs/ABS_TUNING.md`, XDF) — editable, re-sign, flash | Code-read; "bench only" |
| Coding | Read/write via UDS `22/2E 30 00`; hill-start + RPA off advised | Code-read |

### 10.2 Consequence for this project

| Option | Pro | Con |
|---|---|---|
| A. Keep E46 MK60 | Already owned; MaxxECU E46 protocol fits | Frames/bits undocumented → must reverse-engineer from logs (§8) |
| B. Switch to MK60E5 (E9x M3) + E46-sensor patch | Documented frames, ABS-OK bit known, ABS parameters tunable, works without steering sensor | Needs different unit, flash tool, F-CAN/PT-CAN emulation with counter+checksum; patch not car-tested |

Decision for user: A or B. Recommendation: **A first** (log what you have); B if E46 unit stays a black box or tuning is wanted.

### 10.3 Checksum (from repo, "mode 8")

To verify against repo before use: `analysis/` and `FACTS.md` sections "CAN RX handlers". Do not implement from memory.
