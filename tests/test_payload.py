import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare", ROOT / "scripts/prepare-firmware.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

DELL_KEY = "bus=pci,vendor=168c,device=003e,subsystem-vendor=1028,subsystem-device=0310"
OLD_9377_KEY = "bus=pci,vendor=168c,device=0042,subsystem-vendor=1235,subsystem-device=0901"


def ie(tag, data):
    return struct.pack("<II", tag, len(data)) + data + b"x" * (-len(data) % 4)


def container(magic, data):
    return magic + b"m" * (-len(magic) % 4) + data


def board_entry(key, value):
    return ie(0, ie(0, key.encode()) + ie(1, value))


class PayloadTests(unittest.TestCase):
    def test_real_inputs(self):
        board = p.select_board((ROOT / "firmware/board-2.bin").read_bytes(), DELL_KEY)
        self.assertEqual(len(board), 8124)
        parts, version = p.parse_firmware((ROOT / "firmware/firmware-6.bin").read_bytes())
        self.assertEqual(version, "WLAN.RM.4.4.1-00309-")
        self.assertEqual(len(parts[3]), 681821)
        self.assertEqual(len(parts[4]), 24429)
        self.assertTrue(p.ignore_otp_result(parts))
        self.assertFalse(p.supports_skip_clock_init(parts))
        segments, entry = p.parse_segments(parts[3])
        self.assertEqual(entry, 0xa0400)
        self.assertEqual(len(segments), 6)
        self.assertEqual(sum(s['length'] for s in segments), 681749)

    def test_qca9377_profile(self):
        folder = ROOT / 'firmware/QCA9377/hw1.0'
        with self.assertRaises(p.BoardNotFound):
            p.select_board((folder / 'board-2.bin').read_bytes(), OLD_9377_KEY)
        files, header, entries, fallback, missing = p.prepare_family(ROOT, p.FAMILIES[1])
        import json
        manifest = json.loads(files[ROOT / 'firmware/prepared/QCA9377/manifest.json'])
        self.assertGreaterEqual(manifest['board_catalog_entries'], 37)
        self.assertEqual(manifest['firmware_version'], 'WLAN.TF.2.1-00021-QCARMSWP-1')
        self.assertEqual(manifest['otp_bytes'], 24193)
        self.assertEqual(manifest['firmware_bytes'], 727125)
        self.assertEqual(manifest['firmware_segment_data_bytes'], 727053)
        self.assertEqual(manifest['fallback_board_sha256'],
            '127d35d82edb46278f30c448cbca664d755ff0d5fed57b649959cdbc4208c768')
        self.assertIn('board-api1-fallback', fallback)
        self.assertIn('board-profile-not-found', missing)

    def test_fallback_rejects_corrupt_container_and_foreign_firmware(self):
        import tempfile
        import shutil
        folder = ROOT / 'firmware/QCA9377/hw1.0'
        with tempfile.TemporaryDirectory() as temp:
            tmp = Path(temp)
            for name in ('board-2.bin', 'board.bin', 'firmware-6.bin'):
                shutil.copyfile(folder / name, tmp / name)
            family = dict(p.FAMILIES[1], folder=str(tmp))
            bad = [b'corrupt', container(p.BOARD_MAGIC, board_entry(OLD_9377_KEY,b'a'*8124)*2),
                   container(p.BOARD_MAGIC,board_entry(OLD_9377_KEY,b'a'*8000))]
            for data in bad:
                (tmp/'board-2.bin').write_bytes(data)
                with self.assertRaises(ValueError): p.prepare_family(ROOT, family)
            shutil.copyfile(folder/'board-2.bin',tmp/'board-2.bin')
            (tmp/'board.bin').write_bytes(p.select_board((ROOT/'firmware/board-2.bin').read_bytes(),DELL_KEY))
            with self.assertRaises(ValueError): p.prepare_family(ROOT, family)
            shutil.copyfile(folder/'board.bin',tmp/'board.bin')
            shutil.copyfile(ROOT/'firmware/firmware-6.bin',tmp/'firmware-6.bin')
            with self.assertRaises(ValueError): p.prepare_family(ROOT, family)

    def test_catalog_aliases_and_unselected_corruption(self):
        aliases=ie(0,ie(0,b'first')+ie(0,b'second')+ie(1,b'a'*8124))
        self.assertEqual(p.parse_board_catalog(container(p.BOARD_MAGIC,aliases)),
                         {'first':b'a'*8124,'second':b'a'*8124})
        # A valid requested entry must not hide malformed data later in the file.
        good=board_entry(DELL_KEY,b'a'*8124)
        for bad in (ie(0,ie(0,b'orphan')),board_entry('other',b'a'*7),
                    board_entry('bad\x00name',b'a'*8124),ie(0,ie(1,b'a'*8124))):
            with self.assertRaises(ValueError):
                p.select_board(container(p.BOARD_MAGIC,good+bad),DELL_KEY)

    def test_board2_optional_and_api1_is_chip_specific(self):
        import tempfile,shutil,json
        folder=ROOT/'firmware/QCA9377/hw1.0'
        with tempfile.TemporaryDirectory() as temp:
            tmp=Path(temp)
            for name in ('board.bin','firmware-6.bin'):shutil.copyfile(folder/name,tmp/name)
            family=dict(p.FAMILIES[1],folder=str(tmp))
            files,_,entries,fallback,_=p.prepare_family(ROOT,family)
            self.assertFalse(entries)
            self.assertIn('board-api1-fallback',fallback)
            (tmp/'board.bin').unlink()
            with self.assertRaises(ValueError):p.prepare_family(ROOT,family)

    def test_known_board_hashes(self):
        expected=[('firmware',DELL_KEY,'7b01edabe0fc9071abe4d20c7f336fc5e4dc6e2ed4803df54487eef155b16862'),
            ('firmware','bus=pci,vendor=168c,device=003e,subsystem-vendor=1a56,subsystem-device=143a',
             '968e3a8fe226d691f4e5c526e05700ee3519e86237eceedd6f2fd2e85c201ce7'),
            ('firmware/QCA9377/hw1.0','bus=pci,vendor=168c,device=0042,subsystem-vendor=17aa,subsystem-device=0901',
             '34a25b4120d7c1a9bf9c4136ccf9ce0abe95fd8ab367fe0f1707b1674a8ef673')]
        for folder,key,digest in expected:
            self.assertEqual(p.sha(p.select_board((ROOT/folder/'board-2.bin').read_bytes(),key)),digest)

    def test_prepare_is_deterministic_and_validates_before_writes(self):
        import tempfile,shutil
        with tempfile.TemporaryDirectory() as temp:
            tmp=Path(temp)
            shutil.copytree(ROOT/'firmware',tmp/'firmware')
            p.prepare(tmp)
            header=tmp/'src/kext/Ath10kPayload.hpp'
            before=header.read_bytes()
            p.prepare(tmp)
            self.assertEqual(header.read_bytes(),before)
            source=tmp/'firmware/QCA9377/hw1.0/board-2.bin'
            source.write_bytes(source.read_bytes()+b'bad')
            with self.assertRaises(ValueError):p.prepare(tmp)
            self.assertEqual(header.read_bytes(),before)
            self.assertFalse((tmp/'firmware/prepared/board.bin').exists())

    def test_segmented_image_validation(self):
        header = struct.pack('<II', 0x544d4753, 0)
        segment = struct.pack('<II', 0x500000, 5) + b'abcde'
        entry = struct.pack('<II', 0x500000, 0xfffffffd)
        done = struct.pack('<II', 0, 0xffffffff)
        self.assertEqual(p.parse_segments(header + segment + entry + done)[0][0]['length'], 5)
        invalid = [b'', header + segment, header + segment + done,
                   header + segment + entry + done + b'x',
                   header + segment + entry + entry + done,
                   header + struct.pack('<II', 0x500000, 0xfffffffc),
                   header + struct.pack('<II', 0x500000, 1000) + b'abc',
                   header + segment + segment + entry + done,
                   header + struct.pack('<II', 0xfffffffc, 5) + b'abcde' + entry + done,
                   header + struct.pack('<II', 0x400800, 5) + b'abcde' + entry + done,
                   header + segment + struct.pack('<II', 0x600000, 0xfffffffd) + done]
        for data in invalid:
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                p.parse_segments(data)

    def test_otp_feature_bit(self):
        self.assertFalse(p.ignore_otp_result({}))
        self.assertFalse(p.ignore_otp_result({2: b""}))
        self.assertFalse(p.ignore_otp_result({2: b"\x40\x80"}))
        self.assertTrue(p.ignore_otp_result({2: b"\x80"}))

    def test_skip_clock_feature_bit(self):
        for value in (b"", b"\x02", b"\xc0\x10"):
            self.assertFalse(p.supports_skip_clock_init({2: value}))
        self.assertFalse(p.supports_skip_clock_init({}))
        self.assertTrue(p.supports_skip_clock_init({2: b"\xc0\x12"}))

    def test_exact_not_prefix_match(self):
        data = container(p.BOARD_MAGIC,
            board_entry(DELL_KEY + ",variant=other", b"b" * 8124) +
            board_entry(DELL_KEY, b"a" * 8124))
        self.assertEqual(p.select_board(data, DELL_KEY), b"a" * 8124)

    def test_missing_duplicate_wrong_size(self):
        entries = [board_entry("other", b"a" * 8124),
                   board_entry(DELL_KEY, b"a" * 8124) * 2,
                   board_entry(DELL_KEY, b"a" * 8123)]
        for entry in entries:
            with self.subTest(size=len(entry)), self.assertRaises(ValueError):
                p.select_board(container(p.BOARD_MAGIC, entry), DELL_KEY)

    def test_truncated_and_hostile_lengths(self):
        for data in (b"", p.BOARD_MAGIC, container(p.BOARD_MAGIC, b"a"),
                     container(p.BOARD_MAGIC, struct.pack("<II", 0, 0xffffffff)),
                     container(p.BOARD_MAGIC, ie(0, struct.pack("<II", 1, 8000)))):
            with self.subTest(data=data[:25]), self.assertRaises(ValueError):
                p.select_board(data, DELL_KEY)

    def test_firmware_rejects_missing_duplicate_codeswap_wrong_ops(self):
        good = ie(0, b"version") + ie(3, b"firmware") + ie(4, b"otp") + ie(5, struct.pack("<I", 4)) + ie(6, struct.pack("<I", 3))
        for body in (good + ie(3, b"second"), good + ie(7, b"swap"),
                     ie(0, b"version"), good.replace(struct.pack("<I", 4), struct.pack("<I", 9))):
            with self.subTest(size=len(body)), self.assertRaises(ValueError):
                p.parse_firmware(container(p.FW_MAGIC, body))


if __name__ == "__main__":
    unittest.main()
