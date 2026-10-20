"""Create an owned API37 AVD with the supported Android CLI, not avdmanager.

A device profile supplies hardware defaults; its default image and any generated
userdata are NOT runtime evidence. The owned test case pins the inspected x86_64
image and starts with its own fresh data. getprop/getconf still verify the boot.
"""
from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess
import tempfile
import stat


def _read_properties(path: Path) -> dict[str, str]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 65_536:
        raise ValueError("AVD configuration must be one bounded regular file")
    data = path.read_text(encoding="utf-8")
    values = {}
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or key in values:
            raise ValueError("Ambiguous AVD configuration")
        values[key] = value
    return values


def _owned_home(work: Path, name: str) -> Path:
    if re.fullmatch(r"analyst-install-\d+-\d+", name) is None:
        raise ValueError("Invalid owned AVD name")
    home = work / "avd"
    home.mkdir(exist_ok=True)
    if home.is_symlink() or home.resolve() != home or any(home.iterdir()):
        raise ValueError("Owned AVD home must be empty and unlinked")
    return home


def _image_directory(sdk: Path, image: str) -> tuple[Path, str]:
    allowed = {
        "system-images;android-37.0;google_apis;x86_64": "google_apis",
        "system-images;android-37.0;google_apis_ps16k;x86_64": "google_apis_ps16k",
    }
    if image not in allowed:
        raise ValueError("Android 17 image required")
    directory = sdk.joinpath(*image.split(";"))
    if not (directory / "system.img").is_file():
        raise ValueError("Pinned Android 17 system image is not installed")
    return directory, allowed[image]


def _profile_hardware(sdk: Path, seed: Path, run) -> dict[str, str]:
    home = seed / "avd"
    home.mkdir()
    executable = sdk / "cmdline-tools/latest/bin" / ("android.exe" if os.name == "nt" else "android")
    env = dict(os.environ, ANDROID_AVD_HOME=str(home), ANDROID_USER_HOME=str(seed / "user"))
    run([str(executable), "--no-metrics", f"--sdk={sdk}", "emulator", "create", "Medium_Phone_API_37"],
        env=env, check=True, capture_output=True, text=True, timeout=600)
    candidates = list(home.glob("*.avd"))
    if len(candidates) != 1:
        raise ValueError("Android CLI did not create one owned profile")
    profile = candidates[0]
    if profile.is_symlink() or profile.resolve().parent != home.resolve():
        raise ValueError("Profile escapes owned storage")
    values = _read_properties(profile / "config.ini")
    # Never reuse generated userdata, snapshots or external SD-card paths.
    return {key: value for key, value in values.items()
            if key.startswith("hw.") and "path" not in key.lower()}


def create_owned_profile(sdk: Path, work: Path, name: str, image: str, run=subprocess.run) -> Path:
    """All writes stay in a fresh work-owned AVD home; never touch user devices."""
    sdk, work = sdk.resolve(strict=True), work.resolve(strict=True)
    directory, tag = _image_directory(sdk, image)
    home = _owned_home(work, name)
    with tempfile.TemporaryDirectory(prefix="android17-profile-", dir=work) as temporary:
        values = _profile_hardware(sdk, Path(temporary), run)
    values.update({"AvdId": name, "avd.ini.displayname": name, "avd.ini.encoding": "UTF-8",
                   "abi.type": "x86_64", "hw.cpu.arch": "x86_64", "hw.mainKeys": "no",
                   "image.sysdir.1": str(directory) + os.sep, "tag.id": tag,
                   "tag.display": "Google APIs", "PlayStore.enabled": "false"})
    destination = home / (name + ".avd")
    destination.mkdir()
    (destination / "config.ini").write_text("".join(f"{k}={v}\n" for k, v in sorted(values.items())), encoding="utf-8")
    (home / (name + ".ini")).write_text(
        f"avd.ini.encoding=UTF-8\npath={destination}\ntarget=android-37.0\n", encoding="utf-8")
    return destination
