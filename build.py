#!/usr/bin/env python3
"""Build the firmware listed in build.yaml locally, the same list CI builds.

    ./build.py                     build everything
    ./build.py central_left_oled   build only the named artifacts

If ../zmk is a ZMK west workspace with a .venv (ZMK's local setup guide), it gets reused
as is. Otherwise the first run downloads ZMK and Zephyr into .zmk/zmk (about 2 GB).
Either way the extra modules are fetched into .zmk/ at the commits pinned in
config/west.yml. Needs git, cmake, ninja, dtc and Zephyr SDK 0.17.0
(ZEPHYR_SDK_INSTALL_DIR, default ~/zephyr-sdk-0.17.0).

Output: <artifact-name>.uf2 in the repo root, logs in .zmk/logs/.
JOBS sets how many builds run at once (default 4).
LOCAL_MODULES=nice-view-anim builds that module from ../nice-view-anim as it is on disk,
uncommitted changes included, instead of the commit pinned in config/west.yml.
"""
import os
import shutil
import subprocess
import sys
import venv
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".zmk"
REUSE = (ROOT.parent / "zmk/.west/config").exists() and (ROOT.parent / "zmk/.venv").exists()
ZMK = ROOT.parent / "zmk" if REUSE else CACHE / "zmk"
VENV = ZMK / ".venv" if REUSE else CACHE / ".venv"

# west and PyYAML live in the venv, so re-run this script with the venv's Python
if Path(sys.prefix).resolve() != VENV.resolve():
    if not VENV.exists():
        venv.create(VENV, with_pip=True)
    os.execv(VENV / "bin/python", [str(VENV / "bin/python"), __file__, *sys.argv[1:]])

os.environ["PATH"] = f"{VENV / 'bin'}{os.pathsep}{os.environ['PATH']}"
# CMake 4.x breaks Zephyr 3.5's SDK lookup unless these are set explicitly
os.environ["ZEPHYR_TOOLCHAIN_VARIANT"] = "zephyr"
os.environ.setdefault("ZEPHYR_SDK_INSTALL_DIR", str(Path.home() / "zephyr-sdk-0.17.0"))


def run(*cmd, cwd=ZMK, capture=False):
    return subprocess.run(cmd, cwd=cwd, check=True, text=True, capture_output=capture).stdout


if not REUSE:
    # ZMK Studio's nanopb generator needs protobuf and pkg_resources (gone from newer setuptools)
    run("pip", "install", "-q", "west", "setuptools<81", "protobuf", "grpcio-tools", cwd=CACHE)
import yaml  # noqa: E402

builds = yaml.safe_load((ROOT / "build.yaml").read_text())["include"]
wanted = set(sys.argv[1:])
if unknown := wanted - {b["artifact-name"] for b in builds}:
    sys.exit(f"unknown artifact: {', '.join(sorted(unknown))}")
builds = [b for b in builds if not wanted or b["artifact-name"] in wanted]

manifest = yaml.safe_load((ROOT / "config/west.yml").read_text())["manifest"]
url_bases = {r["name"]: r["url-base"] for r in manifest["remotes"]}
modules = [p for p in manifest["projects"] if p["name"] != "zmk"]
local = set(filter(None, os.environ.get("LOCAL_MODULES", "").split(",")))
if unknown := local - {m["name"] for m in modules}:
    sys.exit(f"unknown module in LOCAL_MODULES: {', '.join(sorted(unknown))}")
module_dirs = [ROOT.parent / m["name"] if m["name"] in local else CACHE / m["name"] for m in modules]
if missing := sorted(str(ROOT.parent / name) for name in local if not (ROOT.parent / name).is_dir()):
    sys.exit(f"LOCAL_MODULES checkout not found: {', '.join(missing)}")


def checkout(project):
    """Shallow-fetch a project from config/west.yml into .zmk/<name> at its pinned revision."""
    path = CACHE / project["name"]
    rev = project["revision"]
    if not (path / ".git").exists():
        path.mkdir(parents=True, exist_ok=True)
        run("git", "init", "-q", cwd=path)
    head = subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], cwd=path, capture_output=True, text=True)
    if head.stdout.strip() == rev:
        return
    print(f"fetching {project['name']} @ {rev}", flush=True)
    run("git", "fetch", "-q", "--depth", "1", f"{url_bases[project['remote']]}/{project['name']}", rev, cwd=path)
    run("git", "checkout", "-q", "--detach", "FETCH_HEAD", cwd=path)


for m, d in zip(modules, module_dirs):
    if m["name"] in local:
        print(f"using local {d}", flush=True)
    else:
        checkout(m)

if REUSE:
    # no version check, ../zmk is trusted to be on the ZMK release config/west.yml pins
    print(f"using ZMK in {ZMK} ({run('git', 'describe', '--tags', capture=True).strip()})", flush=True)
else:
    checkout(next(p for p in manifest["projects"] if p["name"] == "zmk"))
    if not (ZMK / ".west").exists():
        run("west", "init", "-l", "app")
    run("west", "update", "--narrow", "-o=--depth=1")
    run("pip", "install", "-q", "-r", "zephyr/scripts/requirements-base.txt")

extra_modules = ";".join(map(str, [ROOT, *module_dirs]))
(CACHE / "logs").mkdir(parents=True, exist_ok=True)


def build(b):
    name = b["artifact-name"]
    uf2 = ROOT / f"{name}.uf2"
    uf2.unlink(missing_ok=True)

    cmd = ["west", "build", "-p", "auto", "-s", "app", "-d", CACHE / "build" / name, "-b", b["board"]]
    if "snippet" in b:
        cmd += ["-S", b["snippet"]]
    # Zephyr_DIR pins CMake to this workspace's Zephyr, not whichever one another setup registered
    cmd += ["--", f"-DZephyr_DIR={ZMK}/zephyr/share/zephyr-package/cmake",
            f"-DZMK_CONFIG={ROOT}/config", f"-DZMK_EXTRA_MODULES={extra_modules}"]
    if "shield" in b:
        cmd.append(f"-DSHIELD={b['shield']}")
    cmd += b.get("cmake-args", "").split()

    with open(CACHE / f"logs/{name}.log", "w") as log:
        ok = subprocess.run(cmd, cwd=ZMK, stdout=log, stderr=subprocess.STDOUT).returncode == 0
    if ok:
        shutil.copy(CACHE / f"build/{name}/zephyr/zmk.uf2", uf2)
    print(f"ok    {name}" if ok else f"FAIL  {name} (see .zmk/logs/{name}.log)", flush=True)
    return ok


with ThreadPoolExecutor(int(os.environ.get("JOBS", 4))) as pool:
    results = list(pool.map(build, builds))
sys.exit(0 if all(results) else 1)
