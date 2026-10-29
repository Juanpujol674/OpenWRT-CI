#!/usr/bin/env python3
"""Stage the official dist.zip in the OpenWrt rootfs overlay before building."""
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import zipfile

UI_URL = "https://github.com/Zephyruso/zashboard/releases/latest/download/dist.zip"


def prepare(root, archive):
    root = Path(root).resolve()
    template = root / "package/OpenWrt-nikki/nikki/files/nikki.conf"
    config = template.read_text(encoding="utf-8")
    section = re.search(r"(?m)^config mixin ['\"]mixin['\"]\s*\n(?:(?!^config ).*\n?)*", config)
    if not section:
        raise ValueError("Nikki mixin defaults not found; check upstream layout")
    defaults = section[0]
    for name, value in (("ui_path", "ui"), ("ui_name", "zashboard"), ("ui_url", UI_URL)):
        pattern = rf"(?m)^[ \t]*option ['\"]{name}['\"][^\n]*\n?"
        defaults = re.sub(pattern, "", defaults)
        defaults = defaults.rstrip() + f"\n\toption '{name}' '{value}'\n"
    config = config[:section.start()] + defaults + "\n" + config[section.end():]

    destination = root / "files/etc/nikki/run/ui/zashboard"
    # Validate and stage first, so a broken download leaves the overlay intact.
    with tempfile.TemporaryDirectory() as temporary:
        staging = Path(temporary) / "zashboard"
        staging.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                path = PurePosixPath(entry.filename)
                if (path.is_absolute() or ".." in path.parts or "\\" in entry.filename
                        or not path.parts or path.parts[0] != "dist"
                        or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise ValueError(f"Unexpected zashboard archive entry: {entry.filename}")
                relative = path.relative_to("dist")
                target = staging.joinpath(*relative.parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.open(entry) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o644)
        if not (staging / "index.html").is_file() or not (staging / "assets").is_dir():
            raise ValueError("zashboard archive must contain dist/index.html and dist/assets/")
        # Only replace this generated dashboard, preserving sibling dashboards.
        if destination.resolve() != destination or destination.is_symlink():
            raise ValueError("zashboard overlay destination must not be a symlink")
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staging, destination)
    template.write_text(config, encoding="utf-8", newline="\n")
    print("Preinstalled zashboard: /etc/nikki/run/ui/zashboard/index.html")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prepare-zashboard.py dist.zip (run in the OpenWrt source tree)")
    prepare(Path.cwd(), sys.argv[1])
