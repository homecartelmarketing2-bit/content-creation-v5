import glob
import os
import shutil
import subprocess
import sys


DIST_NAME = "Content Creation Automation Marketing"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist", DIST_NAME)
SPEC_FILE = os.path.join(PROJECT_DIR, f"{DIST_NAME}.spec")


def find_playwright_chromium():
    base = os.path.join(os.environ["LOCALAPPDATA"], "ms-playwright")
    chromium_dirs = sorted(glob.glob(os.path.join(base, "chromium-*")), reverse=True)
    if not chromium_dirs:
        raise RuntimeError(f"No Playwright Chromium folder found in {base}. Run: playwright install chromium")

    for folder in chromium_dirs:
        for child in ("chrome-win64", "chrome-win"):
            chrome_dir = os.path.join(folder, child)
            if os.path.exists(os.path.join(chrome_dir, "chrome.exe")):
                return chrome_dir

    raise RuntimeError(f"No chrome.exe found under {chromium_dirs[0]}")


def main():
    print("=" * 60)
    print(f"Building {DIST_NAME}")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", SPEC_FILE, "--noconfirm"],
        cwd=PROJECT_DIR,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)

    standalone_exe = os.path.join(PROJECT_DIR, "dist", f"{DIST_NAME}.exe")
    if os.path.exists(standalone_exe):
        os.remove(standalone_exe)

    chromium_src = find_playwright_chromium()
    chromium_dst = os.path.join(DIST_DIR, "chromium")
    if os.path.exists(chromium_dst):
        shutil.rmtree(chromium_dst)
    shutil.copytree(chromium_src, chromium_dst)
    print(f"Bundled Chromium: {chromium_dst}")

    data_dir = os.path.join(DIST_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    zip_base = os.path.join(PROJECT_DIR, "dist", DIST_NAME)
    shutil.make_archive(zip_base, "zip", os.path.join(PROJECT_DIR, "dist"), DIST_NAME)
    print(f"Created: {zip_base}.zip")


if __name__ == "__main__":
    main()
