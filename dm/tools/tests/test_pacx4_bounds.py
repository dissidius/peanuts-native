"""Reject truncated PACx 403 tables without unhandled struct.error.

The 2026-11-20 scheduled shader_split fuzzer discovered a truncated 138-byte
chunk table. Its exact input is committed to fuzz/corpus/shader_split/ and
replayed automatically by test_fuzz_corpus.py as well as this focused test.
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
if old_game is None: del os.environ['DM_GAME']


def pacx403(root):
    """Minimal archive with a single uncompressed root chunk."""
    d = bytearray(0x40 + len(root))
    d[:8] = ss.PACX4
    struct.pack_into('<III', d, 0x10, 0x40, len(root), len(root))
    struct.pack_into('<II', d, 0x20, 0, 12)
    struct.pack_into('<III', d, 0x30, 1, len(root), len(root))
    d[0x40:] = root
    return d


class PACX4Bounds(unittest.TestCase):
    def test_valid_archive_without_shader_types(self):
        self.assertEqual(ss.pacx4_parts(pacx403(ss.PACX4_ROOT + bytes(0x38)), 'valid'), [])

    def test_table_declares_more_bytes_than_exist(self):
        d = pacx403(ss.PACX4_ROOT + bytes(0x38))
        struct.pack_into('<I', d, 0x24, 0x1000000)
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] bad: PACx 403 root chunk table:'):
            ss.pacx4_parts(d, 'bad')

    def test_table_cut_mid_entry(self):
        d = pacx403(ss.PACX4_ROOT + bytes(0x38))
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] cut: PACx 403 root chunk table:'):
            ss.pacx4_parts(d[:0x39], 'cut')

    def test_header_cut_before_table_sizes(self):
        d = pacx403(ss.PACX4_ROOT + bytes(0x38))
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] cut: PACx 403 header:'):
            ss.pacx4_parts(d[:0x24], 'cut')

    def test_short_root_with_shader_name(self):
        d = pacx403(ss.PACX4_ROOT + b'Shader')
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] short: PACx 402 root header:'):
            ss.pacx4_parts(d, 'short')

    def test_exact_fuzz_crash_rejects_cleanly(self):
        path = REPO / 'dm/tools/fuzz/corpus/shader_split/pacx4-truncated-chunk-table.bin'
        with self.assertRaisesRegex(SystemExit, r'^\[RED\] fuzzer: PACx 403 root chunk table:'):
            ss.pacx4_parts(path.read_bytes(), 'fuzzer')


if __name__ == '__main__':
    unittest.main()
