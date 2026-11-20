"""Reject damaged Camelot NARC archives cleanly from shader_split.scan_blob.

The full 2026-11-20 fuzz rerun found a NARC with no BTAF/GMIF sections.
A malformed archive must produce the parser's named [RED] rejection.
"""
import os
from pathlib import Path
import struct
import sys
import unittest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'dm/gfx/tools'))
old_game = os.environ.get('DM_GAME')
os.environ['DM_GAME'] = old_game or '010015100B514000'
import shader_split as ss
import cra
if old_game is None: del os.environ['DM_GAME']


def narc(*sections):
    d = bytearray(0x10)
    d[:4] = b'NARC'
    struct.pack_into('<HH', d, 0xc, 0x10, len(sections))
    for magic, payload in sections:
        d += magic + struct.pack('<I', 8 + len(payload)) + payload
    return bytes(d)


class NARCRejection(unittest.TestCase):
    def test_valid_empty_archive(self):
        d = narc((b'BTAF', struct.pack('<I', 0)), (b'GMIF', b''))
        self.assertEqual(cra.narc_members(d, 'valid'), [])
        out = []
        ss.scan_blob(d, 'valid', out)
        self.assertEqual(out, [])

    def test_missing_sections_reported(self):
        d = b'NARC' + bytes(12)
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] bad: no BTAF or GMIF'):
            ss.scan_blob(d, 'bad', [])

    def test_fuzz_corpus_missing_sections(self):
        path = REPO / 'dm/tools/fuzz/corpus/shader_split/narc-missing-sections.bin'
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] bad: no BTAF or GMIF'):
            ss.scan_blob(path.read_bytes(), 'bad', [])

    def test_truncated_header(self):
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] cut: incomplete NARC header'):
            ss.scan_blob(b'NARC', 'cut', [])

    def test_section_extends_beyond_archive(self):
        d = bytearray(narc((b'BTAF', struct.pack('<I', 0)), (b'GMIF', b'')))
        struct.pack_into('<I', d, 0x14, 0x1000)
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] section: a section past the end'):
            ss.scan_blob(d, 'section', [])

    def test_fat_member_count_exceeds_table(self):
        d = narc((b'BTAF', struct.pack('<I', 2)), (b'GMIF', b''))
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] count: BTAF member table past the end'):
            ss.scan_blob(d, 'count', [])


if __name__ == '__main__':
    unittest.main()
