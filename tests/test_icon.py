"""Current icon format is checked without changing historical archive policy."""
import struct
import unittest
import zlib
from tools import package


class IconTests(unittest.TestCase):
    def test_current_icon_is_bounded_opaque_512px_png(self):
        package.validate_icon((package.ADDON / 'resources/art/icon.png').read_bytes())

    def test_transparency_wrong_dimensions_and_corruption_are_rejected(self):
        data = (package.ADDON / 'resources/art/icon.png').read_bytes()
        for width, height, color in ((256, 512, 2), (512, 512, 6), (512, 512, 3)):
            header = struct.pack('>IIBBBBB', width, height, 8, color, 0, 0, 0)
            changed = data[:16] + header + zlib.crc32(b'IHDR' + header).to_bytes(4, 'big') + data[33:]
            with self.assertRaises(ValueError):
                package.validate_icon(changed)
        for changed in (data[:-1], data + b'private metadata', data[:50] + b'broken' + data[56:], b'not PNG'):
            with self.assertRaises(ValueError):
                package.validate_icon(changed)
