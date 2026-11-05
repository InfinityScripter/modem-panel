"""Minimal Qualcomm QCDM (DIAG) client over libusb for the Huawei E352 DIAG port.

Read-only probes first: version, then NV item reads. HDLC framing with CRC-16/X.25.
"""
import sys, time
import usb.core, usb.util, usb.backend.libusb1

be = usb.backend.libusb1.get_backend(find_library=lambda x: "/opt/homebrew/lib/libusb-1.0.dylib")
DIAG_INTF = 2

def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc ^ 0xFFFF

def hdlc_encode(payload):
    frame = bytes(payload)
    c = crc16(frame)
    frame += bytes([c & 0xFF, (c >> 8) & 0xFF])
    out = bytearray()
    for b in frame:
        if b == 0x7E:
            out += b"\x7d\x5e"
        elif b == 0x7D:
            out += b"\x7d\x5d"
        else:
            out.append(b)
    out.append(0x7E)
    return bytes(out)

def hdlc_decode(data):
    data = data.split(b"\x7e")[0]
    out = bytearray()
    esc = False
    for b in data:
        if esc:
            out.append(b ^ 0x20)
            esc = False
        elif b == 0x7D:
            esc = True
        else:
            out.append(b)
    return bytes(out[:-2]) if len(out) >= 2 else bytes(out)

class Diag:
    def __init__(self):
        self.dev = usb.core.find(idVendor=0x12d1, idProduct=0x1506, backend=be)
        if self.dev is None:
            raise SystemExit("modem not in modem mode")
        self.intf = self.dev.get_active_configuration()[(DIAG_INTF, 0)]
        usb.util.claim_interface(self.dev, self.intf)
        self.out = usb.util.find_descriptor(self.intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        self.inp = usb.util.find_descriptor(self.intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        self._drain()

    def _drain(self):
        while True:
            try: self.inp.read(512, 100)
            except usb.core.USBError: return

    def cmd(self, payload, timeout=1500):
        self.out.write(hdlc_encode(payload), 1000)
        buf = b""
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            try:
                buf += bytes(self.inp.read(512, 300))
                if 0x7E in buf:
                    break
            except usb.core.USBError:
                pass
        return hdlc_decode(buf)

    def nv_read(self, item):
        # DIAG_NV_READ_F = 0x26, item (2 bytes LE), 128-byte data placeholder
        resp = self.cmd(bytes([0x26, item & 0xFF, item >> 8]) + b"\x00" * 128)
        if not resp or resp[0] != 0x26:
            return None, resp
        status = resp[131] | (resp[132] << 8) if len(resp) >= 133 else None
        return resp[3:131], status

    def close(self):
        usb.util.release_interface(self.dev, self.intf)
        usb.util.dispose_resources(self.dev)

if __name__ == "__main__":
    d = Diag()
    ver = d.cmd(b"\x00")
    print("version resp:", ver.hex())
    print("ascii:", "".join(chr(b) if 32 <= b < 127 else "." for b in ver))
    esn = d.cmd(b"\x01")
    print("esn resp:", esn.hex())
    d.close()
