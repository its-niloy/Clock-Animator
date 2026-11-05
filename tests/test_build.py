"""A failed package build must keep the last usable release intact."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402


class BuildSafety(unittest.TestCase):
    def test_failed_validation_does_not_fall_back_or_replace_release(self):
        output = Path(__file__).resolve().parent / 'output'
        output.mkdir(exist_ok=True)
        with TemporaryDirectory(dir=output) as directory:
            root = Path(directory)
            package = root / 'clock_animator'
            package.mkdir()
            (package / 'blender_manifest.toml').write_text('version="1.0.0"')
            dist = root / 'dist'
            dist.mkdir()
            archive = dist / 'clock_animator-1.0.0.zip'
            archive.write_bytes(b'last known good package')
            failure = SimpleNamespace(returncode=1, stdout='Validation failed: required LICENSE not found', stderr='')
            with patch.object(build, 'ROOT', root), patch.object(build, 'PACKAGE', package), patch.object(build.subprocess, 'run', return_value=failure):
                with self.assertRaises(RuntimeError):
                    build.build('fake-blender')
            self.assertEqual(archive.read_bytes(), b'last known good package')
            self.assertEqual(list(dist.iterdir()), [archive])


if __name__ == '__main__':
    unittest.main()
