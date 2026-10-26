"""Exercise the real Bash config policy without downloading/building OpenWrt.

Run: python3 .github/tests/test_extras.py (requires Bash on PATH).
"""
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = os.environ.get("BASH_EXE", "bash")


class PlatformTests(unittest.TestCase):
    def test_default_and_restored_matrices(self):
        default, restored = set(), set()
        for workflow in ("OWRT-ALL", "QCA-ALL", "QCB-ALL"):
            text = (ROOT / f".github/workflows/{workflow}.yml").read_text(encoding="utf-8")
            match = re.search(r"CONFIG:.*ENABLE_ALL_PLATFORMS == 'true' && '(\[.*?\])' \|\| '(\[.*?\])'", text)
            self.assertIsNotNone(match)
            restored.update(json.loads(match[1]))
            default.update(json.loads(match[2]))
        self.assertEqual(default, {"AIROHA", "IPQ53XX", "IPQ60XX-WIFI-NO", "IPQ60XX-WIFI-YES"})
        mtk = (ROOT / ".github/workflows/MTK-ALL.yml").read_text(encoding="utf-8")
        self.assertIn("if: ${{ vars.ENABLE_ALL_PLATFORMS == 'true' }}", mtk)
        restored.update({"MEDIATEK-WIFI-NO", "MEDIATEK-WIFI-YES"})
        profiles = {p.stem for p in ROOT.glob("Config/*.txt")} - {"GENERAL", "COMMON", "PRIVATE", "TEST"}
        self.assertEqual(restored, profiles)
        self.assertNotIn("TEST", default | restored)


class ExtrasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cwd = Path(self.temp.name)
        self.config = self.cwd / ".config"
        self.config.write_text("CONFIG_KEEP_ME=y\n", encoding="utf-8")
        self.env = dict(os.environ, GITHUB_WORKSPACE=ROOT.as_posix())

    def run_script(self, mode, **env):
        result = subprocess.run(
            [BASH, str(ROOT / "Scripts/Extras.sh"), mode],
            cwd=self.cwd, env=dict(self.env, **env), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        return result

    def assert_success(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_all_platforms_get_required_packages(self):
        for platform in ROOT.glob("Config/*.txt"):
            if platform.stem in {"COMMON", "GENERAL", "PRIVATE"}:
                continue
            with self.subTest(platform=platform.stem):
                self.config.write_text("CONFIG_KEEP_ME=y\nCONFIG_PACKAGE_luci-app-nikki=n\nCONFIG_PACKAGE_luci-app-momo=y\n", encoding="utf-8")
                self.assert_success(self.run_script("config", WRT_CONFIG=platform.stem))
                self.assert_success(self.run_script("verify", WRT_CONFIG=platform.stem))
                text = self.config.read_text(encoding="utf-8")
                self.assertIn("CONFIG_KEEP_ME=y\n", text)
                self.assertIn("CONFIG_PACKAGE_luci-app-nikki=y\n", text)
                self.assertIn("# CONFIG_PACKAGE_luci-app-momo is not set\n", text)
                self.assertEqual(text.count("CONFIG_PACKAGE_luci-app-nikki="), 1)
                self.assertIn("CONFIG_PACKAGE_comgt-ncm=y\n", text)
                if platform.stem != "AIROHA":
                    self.assertNotIn("CONFIG_PACKAGE_luci-app-onu=", text)

    def test_onu_switch_combinations_and_idempotence(self):
        for app, debug, status in itertools.product(("true", "false"), repeat=3):
            with self.subTest(app=app, debug=debug, status=status):
                env = dict(WRT_CONFIG="AIROHA", WRT_ONU_APP=app,
                           WRT_ONU_DEBUG=debug, WRT_ONU_STATUS=status)
                self.assert_success(self.run_script("config", **env))
                before = self.config.read_bytes()
                self.assert_success(self.run_script("config", **env))
                self.assertEqual(before, self.config.read_bytes())
                self.assert_success(self.run_script("verify", **env))
                text = self.config.read_text(encoding="utf-8")
                for package, enabled in [("luci-app-onu", app), ("airoha-ponctl", app),
                                         ("airoha-pond", app), ("airoha-pon-debug", debug),
                                         ("luci-app-pon-status", status)]:
                    self.assertEqual(f"CONFIG_PACKAGE_{package}=y\n" in text, enabled == "true")

    def test_verify_catches_dropped_and_reenabled_options(self):
        self.assert_success(self.run_script("config", WRT_CONFIG="AIROHA"))
        original = self.config.read_text(encoding="utf-8")
        for missing in ("CONFIG_PACKAGE_honk=y", "CONFIG_PACKAGE_comgt-ncm=y",
                        "CONFIG_KERNEL_DEBUG_INFO_BTF=y", "CONFIG_PACKAGE_airoha-pond=y"):
            with self.subTest(missing=missing):
                self.config.write_text(original.replace(missing, ""), encoding="utf-8")
                result = self.run_script("verify", WRT_CONFIG="AIROHA")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("::error::", result.stdout)
        self.config.write_text(original + "CONFIG_PACKAGE_luci-app-openclash=y\n", encoding="utf-8")
        self.assertNotEqual(self.run_script("verify", WRT_CONFIG="AIROHA").returncode, 0)


if __name__ == "__main__":
    unittest.main()
