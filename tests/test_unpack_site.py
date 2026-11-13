"""Only synthetic local tar fixtures are read; nothing is published."""
import io
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_site
import unpack_site


class UnpackSiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / 'artifact.tar'
        self.output = self.root / 'output'

    def write(self, entries):
        with tarfile.open(self.archive, 'w') as bundle:
            for name, kind, data in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.size = len(data) if kind == tarfile.REGTYPE else 0
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = '../outside'
                bundle.addfile(member, io.BytesIO(data) if member.isreg() else None)

    def reject(self):
        before = {p.name for p in self.root.iterdir()}
        with self.assertRaisesRegex(unpack_site.UnpackError, '^invalid site artifact$'):
            unpack_site.unpack(self.archive, self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(before, {p.name for p in self.root.iterdir()})

    def test_valid_site_round_trips_and_existing_destination_is_preserved(self):
        site = build_site.build_site(self.root / 'source')
        with tarfile.open(self.archive, 'w') as bundle:
            bundle.add(site, arcname='.')
        expected = unpack_site.check_published._expected(site)
        self.assertEqual(unpack_site.unpack(self.archive, self.output), self.output)
        self.assertEqual(unpack_site.check_published._expected(self.output), expected)
        with self.assertRaises(unpack_site.UnpackError):
            unpack_site.unpack(self.archive, self.output)
        self.assertEqual(unpack_site.check_published._expected(self.output), expected)

    def test_artifact_without_required_guide_is_not_promoted(self):
        site = build_site.build_site(self.root / 'source')
        (site / 'install.html').unlink()
        with tarfile.open(self.archive, 'w') as bundle:
            bundle.add(site, arcname='.')
        self.reject()

    def test_links_special_files_and_unsafe_paths_never_write_outside(self):
        entries = [(name, tarfile.REGTYPE, b'private') for name in
                   ('../outside', '/outside', '././outside', 'a/../outside',
                    'a//outside', 'a\\outside', 'a/b/c/d/e/f', 'bad:name')]
        entries.extend(('link', kind, b'') for kind in
                       (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE,
                        tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.CONTTYPE))
        for entry in entries:
            with self.subTest(entry=entry[:2]):
                self.write([entry])
                self.reject()

    def test_duplicate_normalized_names_and_file_directory_conflicts_fail(self):
        for entries in (
            [('a', tarfile.REGTYPE, b'a'), ('./a', tarfile.REGTYPE, b'b')],
            [('a', tarfile.DIRTYPE, b''), ('./a/', tarfile.DIRTYPE, b'')],
            [('a', tarfile.REGTYPE, b'a'), ('a/b', tarfile.REGTYPE, b'b')],
            [('a/b', tarfile.REGTYPE, b'a'), ('a', tarfile.REGTYPE, b'b')],
        ):
            self.write(entries)
            self.reject()

    def test_corrupt_or_unexpected_site_content_is_not_promoted(self):
        self.write([('index.html', tarfile.REGTYPE, b'unverified')])
        self.reject()
        site = build_site.build_site(self.root / 'source')
        (site / 'repository/addons.xml.sha256').write_text('wrong')
        with tarfile.open(self.archive, 'w') as bundle:
            bundle.add(site, arcname='.')
        self.reject()
        self.archive.write_bytes(b'not tar')
        self.reject()

    def test_oversized_declared_member_is_rejected_before_reading_payload(self):
        member = tarfile.TarInfo('huge')
        member.size = unpack_site.MAX_BYTES + 1
        self.archive.write_bytes(member.tobuf() + b'\0' * 1024)
        self.reject()

    def test_member_and_archive_bounds_and_symlink_paths(self):
        self.write([('a', tarfile.REGTYPE, b'a'), ('b', tarfile.REGTYPE, b'b')])
        with patch.object(unpack_site, 'MAX_MEMBERS', 1):
            self.reject()
        with patch.object(unpack_site, 'MAX_BYTES', 1):
            self.reject()
        alias = self.root / 'alias'
        alias.symlink_to(self.archive)
        with self.assertRaises(unpack_site.UnpackError):
            unpack_site.unpack(alias, self.output)
        self.output.symlink_to(self.root / 'missing')
        with self.assertRaises(unpack_site.UnpackError):
            unpack_site.unpack(self.archive, self.output)
        self.assertTrue(self.output.is_symlink())


if __name__ == '__main__':
    unittest.main()
