# Unlock (removing the operator lock)

*Русская версия: [README.ru.md](README.ru.md).*

Old Huawei USB modems (E352, E173, E1550 and similar) are often locked to a
carrier. The lock can be removed for free with a code computed from the IMEI.

## How it works

- `hwcalc.py` is an unlock-code calculator for a 15-digit IMEI. It computes four
  variants (V1, V2, V3/201 and Flash) using the open, widely verified algorithm.
  Built-in test vectors check the computation on every run.
- `diag.py` is a Qualcomm DIAG (service port) client over libusb: it reads the
  firmware version, serial number and the modem's memory cells directly, with no
  drivers.

## How to unlock

1. Get the modem's IMEI (in the panel under "Modem", or with the `ATI` command).
2. Compute the codes:
   ```sh
   python3 hwcalc.py <IMEI>
   ```
3. Insert a SIM from another carrier. Enter the code with `AT^CARDLOCK="<code>"`
   on the modem's port. Try V2 and V3/201 before V1.

**About the attempts.** The modem allows roughly 10 code attempts. Do not try
codes at random: when the attempts run out the modem is locked permanently. Only
enter the computed candidates (usually 1–2), never random numbers.

Tested on a Huawei E352 (MegaFon, firmware 11.102.27.00.209): the V2 code worked.

## Supported models

This works for Huawei USB modems that accept the `AT^CARDLOCK` command and use an
IMEI-based unlock code — essentially the whole E-series / K-series 3G stick
family. Known-compatible models include:

- **E-series:** E153, E156, E160, E169, E170, E171, E172, E173, E176, E177, E180,
  E182, E220, E226, E270, E271, E272, E303, E352, E353, E367, E369, E372, E398,
  E1550, E1552, E1690, E1750, E1762, E1820, E3131, E3531
- **K-series (rebranded by carriers):** K3565, K3715, K3765, K4505, K4511

Carrier-branded versions (MegaFon, MTS, Beeline, Vodafone, and others) are the
same hardware and are covered too.

Not covered: newer LTE sticks that moved the lock out of `AT^CARDLOCK` (some
E3372h and later), and non-Huawei modems. If `AT^CARDLOCK?` returns a
`<status>,<attempts>,<used>` line, your modem is of the supported kind; if the
command returns `ERROR`, it is not.

## Algorithm

The code algorithm is not secret: it was reverse-engineered by the community long
ago and is published. `hwcalc.py` is a standalone Python 3 reimplementation based
on open sources (forth32/huaweicalc, the plugnburn gist and others).

Algorithm branches 0–5 are verified against known IMEI/code test vectors. Branch
6 (chosen by rare IMEIs) is not yet verified and is flagged in the output; most
3G sticks use branches 0–1.
