# Modem Panel

*Русская версия: [README.ru.md](README.ru.md).*

A web panel for old Huawei USB modems (E352, E173, E1550 and similar, including
MegaFon- and MTS-branded sticks) on modern macOS, including Apple Silicon.

The modem's bundled Mobile Partner app is built for 32-bit Macs and won't run on
current macOS, and there are no macOS drivers for these modems. Modem Panel talks
to the modem directly over USB (libusb), so no drivers are needed.

## Features

- switches the modem from "CD-ROM" mode into modem mode (macOS asks for the
  administrator password);
- shows SIM status, operator, network registration, network type and signal;
- sends USSD requests, e.g. `*100#` for balance and `*205#` for your own number;
  buttons for MegaFon, MTS, Beeline and Tele2;
- reads, sends and deletes SMS, including non-Latin text;
- shows model, firmware, IMEI and the modem's operator lock;
- can permanently turn off "CD-ROM" mode (`AT^SETPORT`) so the modem boots
  straight into modem mode and the admin password is no longer needed;
- can remove the operator lock for free with an IMEI-based code (see `unlock/`).

No voice calls: carrier firmware usually disables voice.

## Install and run

```sh
brew install libusb
git clone https://github.com/InfinityScripter/modem-panel.git
cd modem-panel
./run.sh
```

The panel opens in your browser at http://127.0.0.1:18352/. It listens on this
computer only.

## Tested

Huawei E352 (firmware 11.102.27.00.209, MegaFon) on macOS 26, Apple Silicon.
Other Huawei modems with USB id `12d1:1446` and similar most likely work too.
If your modem isn't detected, open an issue with the output of
`ioreg -p IOUSB -l -w0 | grep -A3 HUAWEI`.

## How it works

- `modem.py` finds the modem, sends it the standard Huawei mode-switch message
  and exchanges AT commands over the USB bulk endpoints.
- `server.py` is a small HTTP server on the Python standard library. Other sites
  can't call its API: requests with a different `Origin` are rejected.
- `index.html` is a dependency-free page.
- `unlock/` holds the free IMEI-based unlock calculator and a Qualcomm DIAG
  client.

## Limitations

- Until "CD-ROM" mode is turned off, every reconnect needs the mode-switch button
  on the page and macOS asks for the password. The "Always boot as modem" button
  removes this for good; to revert, send `AT^SETPORT` with the value the modem
  used before (for the E352 that is `A1,A2;1,2,3,7,A1,A2`).
- The operator lock is only reliably visible with a foreign SIM: with the home
  SIM, `AT^CARDLOCK?` reports "unlocked" even when the modem is locked.
- While the panel is sending a command, other programs can't use the modem.
- Listing SMS marks new messages as read.
- The panel does not set up an internet connection through the modem.

## License

MIT
