"""Offline checks for dashboard layout, Nikki defaults, and bad downloads."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("dashboard", ROOT / "Scripts/prepare-zashboard.py")
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.template = self.root / "package/OpenWrt-nikki/nikki/files/nikki.conf"
        self.template.parent.mkdir(parents=True)
        self.template.write_text("config mixin 'mixin'\n\toption 'ui_path' 'old-ui'\n"
                                 "\toption 'ui_url' 'old-url'\n\toption 'api_listen' '[::]:9090'\n"
                                 "\nconfig config 'config'\n\toption 'enabled' '0'\n", encoding="utf-8")
        self.destination = self.root / "files/etc/nikki/run/ui/zashboard"

    def archive(self, entries):
        archive = self.root / "dist.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            for name, contents in entries.items():
                bundle.writestr(name, contents)
        return archive

    def test_install_and_refresh_without_extra_dist_directory(self):
        sibling = self.destination.parent / "other/index.html"
        sibling.parent.mkdir(parents=True)
        sibling.write_text("other")
        archive = self.archive({"dist/": "", "dist/index.html": "dashboard",
                                "dist/assets/app.js": "app", "dist/favicon.ico": "icon"})
        dashboard.prepare(self.root, archive)
        self.assertEqual((self.destination / "index.html").read_text(), "dashboard")
        self.assertFalse((self.destination / "dist").exists())
        before = self.template.read_text(encoding="utf-8")
        for option in ("option 'ui_name' 'zashboard'", "option 'ui_path' 'ui'", dashboard.UI_URL,
                       "option 'api_listen' '[::]:9090'", "option 'enabled' '0'"):
            self.assertIn(option, before)
        (self.destination / "stale.js").write_text("old")
        dashboard.prepare(self.root, archive)
        self.assertFalse((self.destination / "stale.js").exists())
        self.assertEqual(sibling.read_text(), "other")
        self.assertEqual(self.template.read_text(encoding="utf-8"), before)

    def test_reject_broken_or_unsafe_archive_before_replacing_files(self):
        self.destination.mkdir(parents=True)
        (self.destination / "index.html").write_text("keep")
        before = self.template.read_bytes()
        for entries in ({"dist/assets/app.js": "missing index"},
                        {"dist/index.html": "missing assets"},
                        {"dist/../../escape": "unsafe"}, {"/absolute": "unsafe"}):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                dashboard.prepare(self.root, self.archive(entries))
            self.assertEqual((self.destination / "index.html").read_text(), "keep")
            self.assertEqual(self.template.read_bytes(), before)
        archive = self.root / "bad.zip"
        archive.write_text("HTTP error page")
        with self.assertRaises(zipfile.BadZipFile):
            dashboard.prepare(self.root, archive)


if __name__ == "__main__":
    unittest.main()
