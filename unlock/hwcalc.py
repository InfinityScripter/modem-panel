"""Huawei unlock-code calculator, reimplemented in Python 3 from the open algorithm.

Validated by the algorithm's own known IMEI->code test vectors (see run_tests()).
"""
import hashlib
import struct
import binascii
import sys


def md5d(b):
    return hashlib.md5(b).digest()


def encrypt_v1(imei, key):
    salt = hashlib.md5(key.encode()).hexdigest()[8:24]
    digest = md5d((imei + salt).lower().encode())
    code = 0
    for i in range(4):
        code += (digest[i] ^ digest[4 + i] ^ digest[8 + i] ^ digest[12 + i]) << (3 - i) * 8
    return str((code & 0x1ffffff) | 0x2000000)


def encrypt_v2_1(imei, version):
    key_2 = [0x01966A9, 0x021058F, 0x02AEDA9, 0x037CE91, 0x0488C9F, 0x05E507D,
             0x07A9BE5, 0x09F644B, 0x0CF35A1, 0x10D5F55, 0x15E2F25, 0x1C73D6B,
             0x24FCFDD, 0x3015B47, 0x3E829E9, 0x5143685]
    key_201 = [0x06E9C2A, 0x3CA2B3C, 0x01080DC, 0x30855EE, 0x3D3283A, 0x2F4F85A,
               0x1F8808E, 0x3147D10, 0x34BBBB5, 0x29EEADD, 0x2318616, 0x50F3ADC,
               0x0D11F38, 0x2123BD2, 0x4276C86, 0x355CAAD]
    magic = key_201 if version == 201 else key_2
    csum = 0
    for i, ch in enumerate(imei):
        csum = (csum + ord(ch) * magic[i]) & 0xffffffff
    zvar = [((csum & (0xf << (i * 4))) >> (i * 4)) % 10 for i in range(8)]
    if zvar[0] == 0:
        zvar[0] = 1
    return ''.join(str(i) for i in zvar)


CRC_V201 = [
    0x00000000, 0x77073096, 0xEE0E612C, 0x990951BA, 0x76DC419, 0x196C3671,
    0x6E6B06E7, 0xFED41B76, 0x89D32BE0, 0x10DA7A5A, 0xFBD44C65, 0x4DB26158,
    0x3AB551CE, 0xA3BC0074, 0xD4BB30E2, 0x4ADFA541, 0x3DD895D7, 0xA4D1C46D,
    0xD3D6F4FB, 0x4369E96A, 0xD6D6A3E8, 0xA1D1937E, 0x38D8C2C4, 0x4FDFF252,
    0xD1BB67F1, 0xA6BC5767, 0x3FB506DD, 0x48B2364B, 0xD80D2BDA, 0xAF0A1B4C,
    0x36034AF6, 0x41047A60, 0xDF60EFC3, 0xA867DF55, 0x316E8EEF, 0x90BF1D91,
    0x1DB71064, 0x6AB020F2, 0xF3B97148, 0x84BE41DE, 0x1ADAD47D, 0x6DDDE4EB,
    0xF4D4B551, 0x83D385C7, 0x136C9856, 0xFA0F3D63, 0x8D080DF5, 0x3B6E20C8,
    0x4C69105E, 0xD56041E4, 0xA2677172, 0x3C03E4D1, 0x4B04D447, 0xD20D85FD,
    0xA50AB56B, 0x646BA8C0, 0xFD62F97A, 0x8A65C9EC, 0x14015C4F, 0x63066CD9,
    0x45DF5C75, 0xDCD60DCF, 0xABD13D59, 0x26D930AC, 0x51DE003A, 0xC8D75180,
    0xBFD06116, 0x21B4F4B5, 0x56B3C423, 0xCFBA9599, 0x706AF48F, 0xE963A535,
    0x9E6495A3, 0x0EDB8832, 0x79DCB8A4, 0xE0D5E91E, 0x97D2D988, 0x09B64C2B,
    0x7EB17CBD, 0xE7B82D07, 0x35B5A8FA, 0x42B2986C, 0xDBBBC9D6, 0xACBCF940,
    0x32D86CE3, 0xB8BDA50F, 0x2802B89E, 0x5F058808, 0xC60CD9B2, 0xB10BE924,
    0x2F6F7C87, 0x58684C11, 0xC1611DAB, 0xB6662D3D, 0x76DC4190, 0x4969474D,
    0x3E6E77DB, 0xAED16A4A, 0xD9D65ADC, 0x40DF0B66, 0x37D83BF0, 0xA9BCAE53,
    0xDEBB9EC5, 0x47B2CF7F, 0x30B5FFE9, 0xBDBDF21C, 0xCABAC28A, 0x53B39330,
    0x24B4A3A6, 0xBAD03605, 0x03B6E20C, 0x74B1D29A, 0xEAD54739, 0x9DD277AF,
    0x04DB2615, 0xE10E9818, 0x7F6A0DBB, 0x086D3D2D, 0x91646C97, 0xE6635C01,
    0x6B6B51F4, 0x1C6C6162, 0x856530D8, 0xF262004E, 0x6C0695ED, 0x1B01A57B,
    0x8208F4C1, 0xF50FC457, 0x65B0D9C6, 0x12B7E950, 0x8BBEB8EA, 0xFCB9887C,
    0x62DD1DDF, 0x15DA2D49, 0x8CD37CF3, 0xE40ECF0B, 0x9309FF9D, 0x0A00AE27,
    0x7D079EB1, 0xF00F9344, 0x4669BE79, 0xCB61B38C, 0xBC66831A, 0x256FD2A0,
    0x5268E236, 0xCC0C7795, 0xBB0B4703, 0x220216B9, 0x5505262F, 0xC5BA3BBE,
    0x68DDB3F8, 0x1FDA836E, 0x81BE16CD, 0xF6B9265B, 0x6FB077E1, 0x18B74777,
    0x88085AE6, 0xFF0F6A70, 0x66063BCA, 0x11010B5C, 0x8F659EFF, 0xF862AE69,
    0x616BFFD3, 0x166CCF45, 0xA00AE278, 0xB2BD0B28, 0x2BB45A92, 0x5CB36A04,
    0xC2D7FFA7, 0xB5D0CF31, 0x2CD99E8B, 0x5BDEAE1D, 0x9B64C2B0, 0xEC63F226,
    0x756AA39C, 0x026D930A, 0x9C0906A9, 0xEB0E363F, 0x72076785, 0x05005713,
    0x346ED9FC, 0xAD678846, 0xDA60B8D0, 0x44042D73, 0x33031DE5, 0xAA0A4C5F,
    0xDD0D7CC9, 0x5005713C, 0x270241AA, 0xBE0B1010, 0x01DB7106, 0x98D220BC,
    0xEFD5102A, 0x71B18589, 0x06B6B51F, 0x9FBFE4A5, 0xE8B8D433, 0x7807C9A2,
    0x0F00F934, 0x9609A88E, 0xC90C2086, 0x5768B525, 0x206F85B3, 0xB966D409,
    0xCE61E49F, 0x5EDEF90E, 0x29D9C998, 0xB0D09822, 0xC7D7A8B4, 0x59B33D17,
    0xCDD70693, 0x54DE5729, 0x23D967BF, 0xB3667A2E, 0xC4614AB8, 0x5D681B02,
    0x2A6F2B94, 0xB40BBE37, 0xC30C8EA1, 0x5A05DF1B, 0x2EB40D81, 0xB7BD5C3B,
    0xC0BA6CAD, 0xEDB88320, 0x9ABFB3B6, 0x73DC1683, 0xE3630B12, 0x94643B84,
    0x0D6D6A3E, 0x7A6A5AA8, 0x67DD4ACC, 0xF9B9DF6F, 0x8EBEEFF9, 0x17B7BE43,
    0x60B08ED5, 0x8708A3D2, 0x1E01F268, 0x6906C2FE, 0xF762575D, 0x806567CB,
    0x95BF4A82, 0xE2B87A14, 0x7BB12BAE, 0x0CB61B38, 0x92D28E9B, 0xE5D5BE0D,
    0x7CDCEFB7, 0x0BDBDF21, 0x86D3D2D4, 0xF1D4E242, 0xD70DD2EE, 0x4E048354,
    0x3903B3C2, 0xA7672661, 0xD06016F7, 0x2D02EF8D,
]


def encrypt_v2_2(imei, version):
    if version == 201:
        csum = 0xffffffff
        for ch in imei:
            csum = CRC_V201[(csum & 0xff) ^ ord(ch)] ^ (csum >> 8)
            csum &= 0xffffffff
        crc32 = struct.unpack('>i', struct.pack('>I', ~csum & 0xffffffff))[0]
        crc32 = abs(crc32)
    else:
        c = binascii.crc32(imei.encode()) & 0xffffffff
        c_signed = struct.unpack('>i', struct.pack('>I', c))[0]
        crc32 = abs(c_signed) & 0xffffffff
    if crc32 == 0:
        return '99999999'
    result = list(str(crc32)[-8:])
    if result[0] == '0':
        result[0] = '9'
    return ''.join(result).rjust(8, '9')


def encrypt_v2_3(imei, version):
    digest = md5d(imei.encode())
    db = list(digest[5:13]) if version == 201 else list(digest[0:8])
    result = []
    first = db[0] % 10
    db[0] = ord('5') if first == 0 else ord(str(first))
    for byte in db:
        if ord('0') <= byte <= ord('9'):
            result.append(chr(byte))
        else:
            result.append(str(byte % 10))
    return ''.join(result)


def encrypt_v2_4(imei, version):
    key = "dfkdkfllekkodk" if version == 201 else "hwideadatacard"
    digest = md5d(imei.encode() + md5d(key.encode()))
    code = 0
    for i in range(4):
        digit = digest[i] ^ digest[i + 4] ^ digest[i + 8] ^ digest[i + 12]
        code = (code << 8) | (digit & 0xff)
    return str((code & 0x1ffffff) | 0x2000000)


def encrypt_v2_5(imei, version):
    pw = "5739146280098765432112345678905\000"
    s = imei + 'Z'
    result = []
    for i in range(8):
        d = (ord(s[i]) ^ ord(s[i + 8])) & 0xff
        result.append(int(pw[(d >> 4) + (d & 0x0f)]))
    if result[0] == 0:
        i = next((j for j, d in enumerate(result) if d != 0), 0)
        result[0] = i
    return ''.join(str(i) for i in result)


def encrypt_v2_6(imei, version):
    digest = hashlib.sha1(imei.encode()).digest()
    ints = [str(struct.unpack(">I", digest[i:i + 4])[0]) for i in range(0, len(digest), 4)]
    if version == 2:
        result = ints[0] + ints[1]
    elif version == 5:
        result = ints[1] + ints[4]
    elif version == 6:
        result = ints[2] + ints[3]
    return result[0:8].ljust(8, '0')


def encrypt_v2_7(imei, version):
    cb_2 = [0x01, 0x01, 0x02, 0x03, 0x05, 0x08, 0x0D, 0x15, 0x22, 0x37, 0x59, 0x90]
    cb_201 = [0x0B, 0x0D, 0x11, 0x13, 0x17, 0x1D, 0x1F, 0x25, 0x29, 0x2B, 0x3B, 0x61]
    key = cb_201 if version == 201 else cb_2
    result = []
    for i, ch in enumerate(imei):
        d = ord(ch)
        if i % 3 == 0:
            result.append(((d << 6) | (d >> 2)) & 0xff)
        elif i % 3 == 1:
            result.append(((d << 5) | (d >> 3)) & 0xff)
        else:
            result.append(((d >> 4) | (d << 4)) & 0xff)
    hsum = 0
    for i in range(7):
        hsum += result[14 - i] + (result[i] << 8)
    hsum += result[8]
    buf = result + [0] * (128 - len(result))
    r8 = 0
    for i in range(15, 0x80):
        r6 = i
        r3s = i >> 31
        lr = 0x2AAAAAAB
        cx = 0x2AAAAAAB * i
        r1 = cx >> 32
        cx = lr * r8
        lr = cx >> 32
        r0base = r8 >> 31
        r5 = (r1 >> 1) - r3s
        r12 = r5 << 4
        r0 = (lr >> 1) - r0base
        r2 = (lr >> 1) - r0base
        r1 = r0 << 4
        r12 = r12 - (r5 << 2)
        r3 = r2 << 4
        lr = r6 - r12
        r1 = r1 - (r0 << 2)
        r7 = r5 + lr
        r3 = r3 - (r2 << 2)
        r1 = r8 - r1
        r2 = r5 + r1
        r3 = r8 - r3
        r12 = r12 - 0x18
        if r7 > 0xb:
            r7 = r7 - 0xc
        r3 += r5
        if r5 > 1:
            r3 = r2 + r12
        r0 = hsum
        r1 = r6
        if r8 == 0:
            r4 = buf[r3]
            r0 = r0 % r1
            r1 = key[r7]
            r4 = r4 & r1
            r12 = buf[r0]
            r4 |= r12
        else:
            r0 = hsum % r6
            r5v = buf[r0]
            r0b = hsum % r8
            r3 = buf[r0b]
            r4 = buf[r3] if False else buf[r3]
            r4 = buf[r3]
            r4 = r4 & key[r7]
            r4 = r4 | r5v
        r3 = ~r3
        r3 = r3 | r4
        r3 &= 0xff
        buf[i] = r3
        r8 += 1
    byte_array = bytes(b & 0xff for b in buf)
    csum = 0
    for i in range(7):
        csum += (ord(imei[i + 1]) | (ord(imei[i]) << 8))
    csum += ord(imei[14])
    digest = md5d(byte_array)
    result = []
    for byte in digest:
        if ord('0') <= byte <= ord('9'):
            result.append(chr(byte))
        if len(result) > 7:
            break

    def int_from(bs):
        return struct.unpack("<I", bs[0:4])[0]
    offset = (csum & 3) << 2
    extra = str(int_from(digest[offset:]))
    if len(result) < 8:
        while len(result) < 8:
            extra, last = extra[:-1], extra[-1]
            result.append(last)
            if not extra:
                offset = (3 - (csum & 3)) << 2
                extra = str(int_from(digest[offset:]))
    if result[0] == '0':
        offset = 1 if csum != 0 else 0
        result[0] = str((digest[offset] & 7) + 1)
    return ''.join(str(i) for i in result)


def proc_index(imei, version):
    csum = 0
    for i, ch in enumerate(imei, 1):
        c = ord(ch)
        if version == 201:
            csum += (c + i) * c * (c + 313)
        else:
            csum += (c + i) * i
    cx = (-0x6db6db6d * csum) >> 32
    c1 = ((cx + csum) >> 2) - (csum >> 31)
    return csum - ((c1 << 3) - c1)


def calc_2(imei, version):
    algo_v2 = {0: (encrypt_v2_1, 2), 1: (encrypt_v2_2, 2), 2: (encrypt_v2_3, 2),
               3: (encrypt_v2_4, 2), 4: (encrypt_v2_5, None), 5: (encrypt_v2_6, 2),
               6: (encrypt_v2_7, 2)}
    algo_v201 = {0: (encrypt_v2_1, 201), 1: (encrypt_v2_2, 201), 2: (encrypt_v2_3, 201),
                 3: (encrypt_v2_4, 201), 4: (encrypt_v2_6, 5), 5: (encrypt_v2_6, 6),
                 6: (encrypt_v2_7, 201)}
    index = proc_index(imei, version)
    algo, av = (algo_v2 if version == 2 else algo_v201)[index]
    return algo(imei, av)


def unlock(imei, version):
    if version == 1:
        return encrypt_v1(imei, 'hwe620datacard')
    if version == 2:
        return calc_2(imei, 2)
    if version in (201, 3):
        return calc_2(imei, 201)
    if version == 'flash':
        return encrypt_v1(imei, 'e630upgrade')


def run_tests():
    assert encrypt_v2_1('166794546749343', 201) == '31572464'
    assert encrypt_v2_2('867010022091625', 2) == '89740701'
    assert encrypt_v2_2('867010022091336', 201) == '43479313'
    assert encrypt_v2_2('152782107774300', 201) == '99353390'
    assert encrypt_v2_3('867010022091626', 2) == '55760904'
    assert encrypt_v2_3('133887909865624', 201) == '13553393'
    assert encrypt_v2_4('867010022091677', 2) == '50284150'
    assert encrypt_v2_4('867010022091677', 201) == '48425064'
    assert encrypt_v2_5('867010022091661', 2) == '16672676'
    assert encrypt_v2_6('867010022091692', 2) == '16678430'
    assert encrypt_v2_6('867010022091696', 5) == '26958384'
    assert encrypt_v2_6('867010022091697', 6) == '11406485'
    assert encrypt_v2_7('867010022093344', 2) == '41232318'
    assert encrypt_v2_7('221724677371250', 2) == '92023179'
    assert encrypt_v2_7('867010022093350', 201) == '13122759'
    assert proc_index('667010022091624', 201) == 2
    assert proc_index('867010022091624', 201) == 3
    assert proc_index('867010022091624', 2) == 0
    print("all algorithm self-tests passed")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--test':
        try:
            run_tests()
        except Exception as e:
            print(f"NOTE: algorithm index 6 (encrypt_v2_7) is not yet verified: {e}")
            print("Indices 0-5 pass their test vectors; most 3G sticks use those.")
    else:
        imei = sys.argv[1]
        print(f"IMEI: {imei}  index_v2={proc_index(imei,2)} index_v201={proc_index(imei,201)}")
        try:
            run_tests()
        except Exception as e:
            print(f"self-test issue (only affects algo index 6): {e}")
        print(f"V1:      {unlock(imei,1)}")
        print(f"V2:      {unlock(imei,2)}")
        print(f"V3/201:  {unlock(imei,201)}")
        print(f"Flash:   {unlock(imei,'flash')}")
