#!/usr/bin/env python3
"""Exclude legacy UI defaults when the replacement ONU UI is enabled.

Run from the OpenWrt source directory, before make defconfig.
Keep negative package exclusions and unrelated PON drivers/backends intact.
"""
from pathlib import Path
import re


def prepare(root):
    legacy = re.compile(
        r"(?<![\w-])(?:luci-app-(?:pon|iptv)|luci-i18n-(?:pon|iptv)-[\w-]+)(?![\w-])"
    )
    changed = False
    for path in (root / "target/linux/airoha").rglob("*"):
        if not path.is_file() or (path.name != "Makefile" and path.suffix != ".mk"):
            continue
        original = path.read_text(encoding="utf-8")
        updated = legacy.sub("", original)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            print(f"Removed legacy PON/IPTV defaults: {path}")
            changed = True
    if changed:
        # Feeds have already scanned the target. Regenerate device package
        # defaults before defconfig, preserving package metadata/build caches.
        for pattern in (".targetinfo", ".config-target.in", ".scantargetinfo", "info/.targetinfo-*"):
            for path in (root / "tmp").glob(pattern):
                if path.is_file():
                    path.unlink()


if __name__ == "__main__":
    prepare(Path.cwd())
