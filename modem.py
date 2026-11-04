"""Talk to Huawei USB modems on macOS directly over libusb.

macOS has no serial driver for these modems, so AT commands go straight
to the bulk endpoints of the modem's vendor-specific interface.
"""

import ctypes.util
import re
import subprocess
import sys
import time

import usb.backend.libusb1
import usb.core
import usb.util

HUAWEI = 0x12D1
# Product IDs a Huawei stick reports while pretending to be a CD-ROM.
STORAGE_PIDS = {0x1446, 0x14D1, 0x1F01, 0x1505, 0x1C0B, 0x14FE, 0x1F1E}
SWITCH_MESSAGE = bytes.fromhex("55534243123456780000000000000011062000000100000000000000000000")

LIBUSB_PATHS = [
    "/opt/homebrew/lib/libusb-1.0.dylib",
    "/usr/local/lib/libusb-1.0.dylib",
]

# Unsolicited status lines the modem pushes on its own.
URC = re.compile(r"^\^(RSSI|SIMST|SRVST|MODE|STIN|BOOT|DSFLOWRPT|CSNR|HCSQ):")


class ModemError(Exception):
    pass


def _backend():
    for path in LIBUSB_PATHS + [ctypes.util.find_library("usb-1.0")]:
        if path:
            backend = usb.backend.libusb1.get_backend(find_library=lambda _x, p=path: p)
            if backend:
                return backend
    raise ModemError("libusb не найден. Поставьте его: brew install libusb")


def find_device():
    """Return (device, mode), mode is 'storage' or 'modem'; (None, None) if absent."""
    for dev in usb.core.find(find_all=True, idVendor=HUAWEI, backend=_backend()):
        return dev, ("storage" if dev.idProduct in STORAGE_PIDS else "modem")
    return None, None


def switch_to_modem():
    """Send the Huawei mode-switch message. Detaching the CD driver needs root."""
    dev, mode = find_device()
    if dev is None:
        raise ModemError("Модем Huawei не подключён")
    if mode == "modem":
        return
    try:
        dev.detach_kernel_driver(0)
    except usb.core.USBError:
        pass
    intf = dev.get_active_configuration()[(0, 0)]
    out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT,
    )
    out.write(SWITCH_MESSAGE)


def switch_with_admin_prompt():
    """Rerun the switch as root through the standard macOS password dialog."""
    command = f"'{sys.executable}' -I '{__file__}' switch"
    script = f'do shell script "{command}" with administrator privileges'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise ModemError(result.stderr.strip() or "Переключение отменено")
    for _ in range(20):
        time.sleep(1)
        if find_device()[1] == "modem":
            return
    raise ModemError("Модем не переключился в режим модема")


class Modem:
    def __init__(self):
        dev, mode = find_device()
        if dev is None:
            raise ModemError("Модем Huawei не подключён")
        if mode == "storage":
            raise ModemError("Модем в режиме диска, сначала переключите его")
        self.dev = dev
        self.intf, self.ep_out, self.ep_in = self._find_at_interface()

    def _bulk_endpoints(self, intf):
        eps = {}
        for e in intf:
            if usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                eps[usb.util.endpoint_direction(e.bEndpointAddress)] = e
        return eps.get(usb.util.ENDPOINT_OUT), eps.get(usb.util.ENDPOINT_IN)

    def _find_at_interface(self):
        for intf in self.dev.get_active_configuration():
            if intf.bInterfaceClass != 0xFF:
                continue
            ep_out, ep_in = self._bulk_endpoints(intf)
            if not (ep_out and ep_in):
                continue
            try:
                usb.util.claim_interface(self.dev, intf)
            except usb.core.USBError:
                continue
            self.intf, self.ep_out, self.ep_in = intf, ep_out, ep_in
            self._drain()
            if "OK" in self._raw("ATE0", timeout=1.5):
                return intf, ep_out, ep_in
            usb.util.release_interface(self.dev, intf)
        raise ModemError("Не нашла интерфейс модема, который отвечает на AT-команды")

    def close(self):
        usb.util.release_interface(self.dev, self.intf)
        usb.util.dispose_resources(self.dev)

    def _drain(self):
        while True:
            try:
                self.ep_in.read(512, 100)
            except usb.core.USBError:
                return

    def _raw(self, command, timeout=3.0, wait_for=None):
        self.ep_out.write((command + "\r").encode(), 1000)
        buf = ""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                buf += bytes(self.ep_in.read(512, 200)).decode(errors="replace")
            except usb.core.USBError:
                pass
            if wait_for and re.search(wait_for, buf):
                break
            if not wait_for and re.search(r"(^|\r\n)(OK|ERROR|\+CM[ES] ERROR:.*)\r\n", buf):
                break
        return buf

    def at(self, command, timeout=3.0, wait_for=None):
        """Run a command and return its response lines without echo and noise."""
        lines = [l.strip() for l in self._raw(command, timeout, wait_for).splitlines()]
        return [l for l in lines if l and l != command and not URC.match(l)]

    def query(self, command, prefix):
        for line in self.at(command):
            if line.startswith(prefix):
                return line[len(prefix):].strip()
        return None

    # --- high-level helpers -------------------------------------------------

    def info(self):
        lines = self.at("ATI")
        fields = dict(l.split(": ", 1) for l in lines if ": " in l)
        lock = self.query("AT^CARDLOCK?", "^CARDLOCK:")
        lock_state = None
        if lock:
            status, attempts, _ = (lock.split(",") + ["", ""])[:3]
            lock_state = {
                "1": "привязан к оператору, нужен код",
                "2": "не привязан, работает с любой симкой",
                "3": "заблокирован навсегда",
            }.get(status, status)
            lock_state += f" (попыток ввода кода: {attempts})"
        return {
            "model": fields.get("Model"),
            "manufacturer": fields.get("Manufacturer"),
            "firmware": fields.get("Revision"),
            "imei": fields.get("IMEI"),
            "hardware": (self.query("AT^HWVER", "^HWVER:") or "").strip('"') or None,
            "lock": lock_state,
        }

    def status(self):
        self.at("AT+COPS=3,0")
        cops = self.query("AT+COPS?", "+COPS:") or ""
        operator = re.search(r'"([^"]*)"', cops)
        csq = self.query("AT+CSQ", "+CSQ:") or "99,99"
        rssi = int(csq.split(",")[0])
        creg = (self.query("AT+CREG?", "+CREG:") or "0,0").split(",")[1]
        sim = self.query("AT+CPIN?", "+CPIN:")
        imsi = next((l for l in self.at("AT+CIMI") if l.isdigit()), None)
        sysinfo = (self.query("AT^SYSINFO", "^SYSINFO:") or "").split(",")
        return {
            "sim": "нет симки" if sim is None else ("готова" if sim == "READY" else sim),
            "sim_operator_code": f"{imsi[:3]}-{imsi[3:5]}" if imsi else None,
            "operator": operator.group(1) if operator else None,
            "registration": {
                "0": "не ищет сеть", "1": "в домашней сети", "2": "ищет сеть",
                "3": "сеть отказала в регистрации", "4": "неизвестно", "5": "в роуминге",
            }.get(creg, creg),
            "network": {"0": "нет", "3": "2G", "5": "3G", "7": "4G"}.get(sysinfo[3], sysinfo[3]) if len(sysinfo) > 3 else None,
            "signal_percent": None if rssi == 99 else round(rssi * 100 / 31),
        }

    def ussd(self, code):
        """Send a USSD request like *100# and return the decoded answer."""
        lines = self.at(f'AT+CUSD=1,"{gsm7_pack(code)}",15', timeout=20, wait_for=r"\+CUSD:.*\r\n|ERROR")
        for line in lines:
            if line.startswith("+CUSD:"):
                m = re.match(r'\+CUSD:\s*(\d)(?:,"([^"]*)"(?:,(\d+))?)?', line)
                if not m:
                    return line
                if m.group(1) == "4":
                    return "Оператор не поддерживает этот запрос"
                return decode_ussd(m.group(2) or "", int(m.group(3) or 15))
            if "ERROR" in line:
                raise ModemError("Модем вернул ошибку на USSD-запрос")
        raise ModemError("Оператор не ответил на USSD-запрос")

    def list_sms(self):
        self.at("AT+CMGF=1")
        self.at('AT+CSCS="UCS2"')
        lines = self.at('AT+CMGL="ALL"', timeout=10)
        messages = []
        for i, line in enumerate(lines):
            m = re.match(r'\+CMGL:\s*(\d+),"([^"]*)","([^"]*)",[^,]*,"([^"]*)"', line)
            if m and i + 1 < len(lines):
                messages.append({
                    "index": int(m.group(1)),
                    "status": m.group(2),
                    "from": decode_sender(m.group(3)),
                    "date": m.group(4),
                    "text": decode_ucs2(lines[i + 1]),
                })
        return messages

    def send_sms(self, number, text):
        self.at("AT+CMGF=1")
        self.at('AT+CSCS="UCS2"')
        self.at("AT+CSMP=17,167,0,8")
        self._raw(f'AT+CMGS="{encode_ucs2(number)}"', timeout=3, wait_for=">")
        response = self._raw(encode_ucs2(text) + "\x1a", timeout=30, wait_for=r"\+CMGS:|ERROR")
        if "+CMGS:" not in response:
            raise ModemError("SMS не отправлено")

    def delete_sms(self, index):
        self.at(f"AT+CMGD={int(index)}")


# --- encodings -----------------------------------------------------------------

def gsm7_pack(text):
    """Pack ASCII into GSM 7-bit septets as hex, the form Huawei expects for USSD."""
    bits = 0
    nbits = 0
    out = bytearray()
    for ch in text.encode("ascii"):
        bits |= (ch & 0x7F) << nbits
        nbits += 7
        while nbits >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            nbits -= 8
    if nbits:
        out.append(bits & 0xFF)
    return out.hex().upper()


def gsm7_unpack(hexstr):
    data = bytes.fromhex(hexstr)
    chars = []
    bits = 0
    nbits = 0
    for byte in data:
        bits |= byte << nbits
        nbits += 8
        while nbits >= 7:
            chars.append(bits & 0x7F)
            bits >>= 7
            nbits -= 7
    text = "".join(map(chr, chars))
    return text.rstrip("\r\x00")


def decode_ucs2(value):
    if value and len(value) % 4 == 0 and re.fullmatch(r"[0-9A-Fa-f]+", value):
        try:
            text = bytes.fromhex(value).decode("utf-16-be")
        except UnicodeDecodeError:
            return value
        # Short digit strings like "77677283" are also valid hex: accept only
        # Latin, Cyrillic, punctuation and emoji, not random CJK.
        if all(ord(c) < 0x2000 or ord(c) >= 0x1F000 or c in "–—№₽" for c in text):
            return text
    return value


def decode_sender(value):
    """Huawei prints alphanumeric senders (e.g. MegaFon) as decimal GSM 7-bit codes."""
    value = decode_ucs2(value)
    if not value.isdigit() or len(value) < 6:
        return value
    chars, i = [], 0
    while i < len(value):
        three = int(value[i:i + 3]) if i + 3 <= len(value) else 0
        code, i = (three, i + 3) if 100 <= three <= 127 else (int(value[i:i + 2]), i + 2)
        chars.append("_" if code == 0x11 else chr(code))
    name = "".join(chars)
    # A plain phone number without "+" stays as it is.
    if all(c.isprintable() for c in name) and any(c.isalpha() for c in name):
        return name
    return value


def encode_ucs2(text):
    return text.encode("utf-16-be").hex().upper()


def decode_ussd(payload, dcs):
    if not re.fullmatch(r"[0-9A-Fa-f]*", payload):
        return payload
    if dcs == 72 or dcs & 0x0C == 0x08:
        return decode_ucs2(payload)
    try:
        return gsm7_unpack(payload)
    except ValueError:
        return payload


if __name__ == "__main__" and sys.argv[1:] == ["switch"]:
    switch_to_modem()
