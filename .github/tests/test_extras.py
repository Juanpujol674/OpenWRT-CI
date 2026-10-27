"""Exercise the real Bash config policy without downloading/building OpenWrt.

Run: python3 .github/tests/test_extras.py (requires Bash on PATH).
"""
import itertools
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = os.environ.get("BASH_EXE", "bash")


class PlatformTests(unittest.TestCase):
    def test_default_and_restored_matrices(self):
        default, restored = set(), set()
        for workflow in ("QCA-ALL", "QCB-ALL"):
            text = (ROOT / f".github/workflows/{workflow}.yml").read_text(encoding="utf-8")
            match = re.search(r"CONFIG:.*ENABLE_ALL_PLATFORMS == 'true' && '(\[.*?\])' \|\| '(\[.*?\])'", text)
            self.assertIsNotNone(match)
            restored.update(json.loads(match[1]))
            default.update(json.loads(match[2]))
        airoha = (ROOT / ".github/workflows/AIROHA-ALL.yml").read_text(encoding="utf-8")
        self.assertIn("CONFIG: [AIROHA-AN7581, AIROHA-AN7583]", airoha)
        default.update({"AIROHA-AN7581", "AIROHA-AN7583"})
        restored.update({"AIROHA-AN7581", "AIROHA-AN7583"})
        self.assertEqual(default, {"AIROHA-AN7581", "AIROHA-AN7583", "IPQ53XX", "IPQ60XX-WIFI-NO", "IPQ60XX-WIFI-YES"})
        owrt = (ROOT / ".github/workflows/OWRT-ALL.yml").read_text(encoding="utf-8")
        self.assertIn("if: ${{ vars.ENABLE_ALL_PLATFORMS == 'true' }}", owrt)
        restored.update({"ROCKCHIP", "X86"})
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
        self.env = dict(os.environ, GITHUB_WORKSPACE=ROOT.as_posix(), PYTHON3=Path(sys.executable).as_posix())

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
                self.assertIn("CONFIG_PACKAGE_luci-app-tailscale=y\n", text)
                if not platform.stem.startswith("AIROHA-AN758"):
                    self.assertNotIn("CONFIG_PACKAGE_luci-app-onu=", text)
                else:
                    self.assertIn("CONFIG_PACKAGE_luci-app-onu=y\n", text)

    def test_an7583_onu_can_be_disabled(self):
        env = dict(WRT_CONFIG="AIROHA-AN7583", WRT_ONU_APP="false")
        self.assert_success(self.run_script("config", **env))
        self.assert_success(self.run_script("verify", **env))
        self.assertIn("# CONFIG_PACKAGE_luci-app-onu is not set", self.config.read_text(encoding="utf-8"))

    def test_onu_switch_combinations_and_idempotence(self):
        for app, debug, status in itertools.product(("true", "false"), repeat=3):
            with self.subTest(app=app, debug=debug, status=status):
                env = dict(WRT_CONFIG="AIROHA-AN7581", WRT_ONU_APP=app,
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
        self.assert_success(self.run_script("config", WRT_CONFIG="AIROHA-AN7581"))
        original = self.config.read_text(encoding="utf-8")
        for missing in ("CONFIG_PACKAGE_luci-app-tailscale=y", "CONFIG_PACKAGE_luci-app-nikki=y", "CONFIG_PACKAGE_comgt-ncm=y",
                        "CONFIG_PACKAGE_kmod-usb-net-cdc-ncm=y", "CONFIG_PACKAGE_airoha-pond=y"):
            with self.subTest(missing=missing):
                self.config.write_text(original.replace(missing, ""), encoding="utf-8")
                result = self.run_script("verify", WRT_CONFIG="AIROHA-AN7581")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("::error::", result.stdout)
        self.config.write_text(original + "CONFIG_PACKAGE_luci-app-openclash=y\n", encoding="utf-8")
        self.assertNotEqual(self.run_script("verify", WRT_CONFIG="AIROHA-AN7581").returncode, 0)

    def test_onu_excludes_conflicting_device_defaults_only_when_enabled(self):
        target = self.cwd / "target/linux/airoha/image/an7581.mk"
        target.parent.mkdir(parents=True)
        original = (
            "DEVICE_PACKAGES := kmod-airoha-xpon airoha-ponctl airoha-pond "
            "luci-app-pon luci-i18n-pon-zh-cn \\\n"
            "  luci-app-iptv luci-i18n-iptv-zh-cn luci-app-pon-status\n"
            "DEVICE_PACKAGES += -luci-app-pon -luci-i18n-pon-zh-cn\n"
        )
        unrelated = self.cwd / "target/linux/qualcommax/image/ipq50xx.mk"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text(original, encoding="utf-8")
        for enabled in ("true", "false"):
            with self.subTest(enabled=enabled):
                target.write_text(original, encoding="utf-8")
                cache = self.cwd / "tmp/info/.targetinfo-airoha"
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text("stale defaults", encoding="utf-8")
                self.config.write_text("CONFIG_PACKAGE_luci-app-pon=y\nCONFIG_PACKAGE_luci-app-iptv=y\n", encoding="utf-8")
                env = dict(WRT_CONFIG="AIROHA-AN7581", WRT_ONU_APP=enabled)
                self.assert_success(self.run_script("config", **env))
                self.assert_success(self.run_script("verify", **env))
                self.assertEqual(unrelated.read_text(encoding="utf-8"), original)
                updated = target.read_text(encoding="utf-8")
                if enabled == "false":
                    self.assertEqual(updated, original)
                    self.assertTrue(cache.exists())
                    self.assertIn("CONFIG_PACKAGE_luci-app-pon=y", self.config.read_text(encoding="utf-8"))
                    continue
                self.assertNotIn(" luci-app-pon ", updated)
                self.assertNotIn(" luci-app-iptv ", updated)
                self.assertNotIn(" luci-i18n-pon-zh-cn ", updated)
                self.assertNotIn(" luci-i18n-iptv-zh-cn ", updated)
                self.assertIn("-luci-app-pon -luci-i18n-pon-zh-cn", updated)
                self.assertIn("kmod-airoha-xpon airoha-ponctl airoha-pond", updated)
                self.assertIn("luci-app-pon-status", updated)
                self.assertFalse(cache.exists())
                self.assert_success(self.run_script("config", **env))
                self.assertEqual(target.read_text(encoding="utf-8"), updated)
                with self.config.open("a", encoding="utf-8") as f:
                    f.write("CONFIG_PACKAGE_luci-app-pon=y\n")
                result = self.run_script("verify", **env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Legacy package conflicts", result.stdout)


class NetworkDefaultsTests(unittest.TestCase):
    def test_all_workflow_callers_use_requested_defaults(self):
        for workflow in (ROOT / ".github/workflows").glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            if "uses: ./.github/workflows/WRT-CORE.yml" in text:
                with self.subTest(workflow=workflow.name):
                    self.assertIn("WRT_IP: 192.168.1.1", text)
                    self.assertIn("WRT_WORD: ''", text)

    def test_generated_lan_and_wifi_settings(self):
        for password in ("", "testpass123"):
            with self.subTest(password=password), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                wifi = root / "package/network/config/wifi-scripts/files/lib/wifi/mac80211.uc"
                wifi.parent.mkdir(parents=True)
                wifi.write_text("set ${si}.ssid='${defaults?.ssid || 'OWRT'}'\n"
                                "set ${si}.encryption='${defaults?.encryption || 'psk2+ccmp'}'\n"
                                "set ${si}.key='${defaults?.key || '12345678'}'\n", encoding="utf-8")
                config = root / "package/base-files/files/bin/config_generate"
                config.parent.mkdir(parents=True)
                config.write_text("ipaddr='192.168.10.1'\nhostname='old'\n", encoding="utf-8")
                for directory in ("feeds/luci/collections", "feeds/luci/modules/luci-mod-system", "feeds/luci/modules/luci-mod-status"):
                    (root / directory).mkdir(parents=True)
                env = dict(os.environ, GITHUB_WORKSPACE=ROOT.as_posix(), WRT_THEME="aurora", WRT_IP="192.168.1.1",
                           WRT_NAME="OWRT", WRT_SSID="OWRT", WRT_WORD=password, WRT_MARK="test", WRT_DATE="test",
                           WRT_PACKAGE="", WRT_TARGET="airoha", WRT_WIFI="none")
                result = subprocess.run([BASH, str(ROOT / "Scripts/Settings.sh")], cwd=root, env=env,
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("ipaddr='192.168.1.1'", config.read_text(encoding="utf-8"))
                self.assertIn("ssid='OWRT'", wifi.read_text(encoding="utf-8"))
                self.assertIn("key='" + password + "'", wifi.read_text(encoding="utf-8"))
                encryption = "psk2+ccmp" if password else "none"
                self.assertIn("encryption='" + encryption + "'", wifi.read_text(encoding="utf-8"))
                self.assertNotIn("12345678", wifi.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
