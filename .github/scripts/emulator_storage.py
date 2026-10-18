"""Configure owned AVD storage/navigation and remove only the stopped attempt's data."""
from __future__ import annotations

import json
from pathlib import Path
import shutil

MIB = 1024 * 1024
DATA_BYTES = 4096 * MIB
HEADROOM_BYTES = 2048 * MIB
DATA_KEY = "disk.dataPartition.size"
MAIN_KEYS_KEY = "hw.mainKeys"


def _initial_data_bytes(image_dir: Path, sdk: Path) -> tuple[str, int]:
    if not image_dir.resolve().is_relative_to(sdk.resolve()):
        raise RuntimeError("System image escapes the selected SDK")
    source = image_dir / "userdata.img"
    if source.is_file():
        if not source.resolve().is_relative_to(image_dir.resolve()):
            raise RuntimeError("Initial userdata image escapes its system image")
        return "userdata.img", source.stat().st_size
    # Official modern images may provide data/ instead of a prebuilt filesystem.
    # The emulator's createUserData builds ext4 from that directory itself.
    directory = image_dir / "data"
    if directory.is_dir() and directory.resolve().is_relative_to(image_dir.resolve()):
        size = 0
        for path in directory.rglob("*"):
            if not path.resolve().is_relative_to(image_dir.resolve()):
                raise RuntimeError("Initial userdata entry escapes its system image")
            if path.is_file():
                size += path.stat().st_size
        return "data-directory", size
    entries = sorted(path.name for path in image_dir.iterdir()) if image_dir.is_dir() else []
    raise RuntimeError("Official userdata source is missing; system image entries: " + ", ".join(entries[:40]))


def configure_userdata(avd: Path, sdk: Path, image: str) -> None:
    layout, initial = _initial_data_bytes(sdk.joinpath(*image.split(";")), sdk)
    # Never shrink an official initial image. Four GiB is ample for the APKs,
    # Google services and synthetic fixtures; RAM and kernel page size are separate.
    # A source directory needs filesystem metadata space in addition to its files.
    minimum = initial + (HEADROOM_BYTES if layout == "data-directory" else 0)
    size = max(DATA_BYTES, ((minimum + MIB - 1) // MIB) * MIB)
    available = shutil.disk_usage(avd).free
    print("EMULATOR_STORAGE=" + json.dumps({"initial_layout": layout, "initial_image_bytes": initial,
          "data_partition_bytes": size, "free_bytes": available,
          "required_with_headroom_bytes": size + HEADROOM_BYTES}), flush=True)
    if available < size + HEADROOM_BYTES:
        raise RuntimeError("Insufficient runner disk space for the disposable AVD and verification evidence")
    config = avd / "config.ini"
    if config.is_symlink():
        raise ValueError("AVD configuration must be a regular owned file")
    lines = [line for line in config.read_text(encoding="utf-8").splitlines()
             if line.partition("=")[0].strip() not in {DATA_KEY, MAIN_KEYS_KEY}]
    # avdmanager without --device can inherit hardware Back/Home keys. In that
    # profile Android removes the navigation bar and its edge input monitor;
    # setting navigation_mode=2 alone cannot make a predictive gesture possible.
    # Select software navigation before boot, without changing density, image,
    # graphics, animation policy or any application-side Back implementation.
    config.write_text("\n".join([*lines, f"{DATA_KEY}={size}", f"{MAIN_KEYS_KEY}=no"]) + "\n",
                      encoding="utf-8")
    print("EMULATOR_NAVIGATION_CONFIG=" + json.dumps({MAIN_KEYS_KEY: "no"}), flush=True)


def remove_disposable_avd(avd_home: Path, attempt: Path, *, process) -> None:
    if process.poll() is None:
        raise RuntimeError("Refusing to remove data of a running emulator")
    if avd_home.is_symlink() or avd_home.name != "avd" or avd_home.resolve().parent != attempt.resolve():
        raise ValueError("Refusing to remove AVD data outside its own attempt")
    if avd_home.exists():
        shutil.rmtree(avd_home)
    print("EMULATOR_STORAGE_CLEANED=owned-stopped-attempt", flush=True)
