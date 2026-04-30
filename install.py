import logging
import os
import shutil
import subprocess
import sys
import platform
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

def get_krita_dir():
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Windows":
        return os.path.join(os.getenv("APPDATA"), "krita", "pykrita")
    elif system == "Darwin": # macOS
        return os.path.join(home, "Library", "Application Support", "krita", "pykrita")
    else: # Linux
        return os.path.join(home, ".local", "share", "krita", "pykrita")

def check_package_installed(krita_dir, package_name, min_version=None):

    import glob

    pattern = os.path.join(krita_dir, f"{package_name}-*.dist-info")
    matches = glob.glob(pattern)

    if not matches:
        pkg_dir = os.path.join(krita_dir, package_name)
        if os.path.isdir(pkg_dir):
            return True
        return False

    if min_version is None:
        return True

    import re
    for match in matches:
        version_match = re.search(rf"{package_name}-(\d+\.\d+(?:\.\d+)?)", match)
        if version_match:
            installed_version = version_match.group(1)
            installed_parts = [int(x) for x in installed_version.split('.')]
            min_parts = [int(x) for x in min_version.split('.')]
            max_len = max(len(installed_parts), len(min_parts))
            installed_parts.extend([0] * (max_len - len(installed_parts)))
            min_parts.extend([0] * (max_len - len(min_parts)))
            if installed_parts >= min_parts:
                return True

    return False

def clean_pip_packages(krita_dir, packages_to_keep, log: Optional[logging.Logger] = None):

    package_patterns = [
        "numpy", "numpy-*.dist-info",
        "PyOpenGL", "PyOpenGL-*.dist-info",
        "PyOpenGL_accelerate", "PyOpenGL_accelerate-*.dist-info",
        "matplotlib", "matplotlib-*.dist-info",
        "opencv", "opencv-*.dist-info",
        "cv2",
        "seaborn", "seaborn-*.dist-info",
        "types_seaborn", "types_seaborn-*.dist-info",
        "pandas", "pandas-*.dist-info",
        "pandas_stubs", "pandas_stubs-*.dist-info",
    ]

    import glob
    for pattern in package_patterns:
        for path in glob.glob(os.path.join(krita_dir, pattern)):
            if os.path.exists(path):
                basename = os.path.basename(path)
                if log:
                    log.info(f"Removing old package: {basename}")
                else:
                    print(f"Removing old package: {basename}")
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                except OSError as e:
                    if log:
                        log.warning(f"Failed to remove {basename}: {e}")
                    else:
                        print(f"Failed to remove {basename}: {e}")

def _setup_installer_logger(log_file: Optional[str] = None, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("krita_3d_pose_installer")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


def main():
    parser = argparse.ArgumentParser(description="Install Krita 3D Pose Plugin")
    parser.add_argument("--clean", action="store_true", help="Force clean old dependencies before installing")
    parser.add_argument("--force-deps", action="store_true", help="Force reinstall dependencies even if already present")
    parser.add_argument("--solo", action="store_true", help="Skip installation of dependencies")
    parser.add_argument("--log-file", type=str, default=None,
                        help="Path to write install log (default: auto-generated next to install.py)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug-level console output")
    args = parser.parse_args()

    if args.log_file:
        log_file = args.log_file
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f"install_log_{timestamp}.log")

    log = _setup_installer_logger(log_file=log_file, verbose=args.verbose)
    log.info(f"Install log file: {log_file}")

    project_dir = os.path.dirname(os.path.abspath(__file__))
    krita_dir = get_krita_dir()

    log.info(f"Installing to: {krita_dir}")

    try:
        os.makedirs(krita_dir, exist_ok=True)
    except OSError as e:
        log.error(f"Failed to create krita directory {krita_dir}: {e}")
        return

    if args.clean:
        log.info("Cleaning old dependencies...")
        clean_pip_packages(krita_dir, [], log=log)

    items = ["krita_3d_pose", "pose_engine"]
    files = ["krita_3d_pose.desktop"]

    for item in items:
        src = os.path.join(project_dir, item)
        dst = os.path.join(krita_dir, item)
        if os.path.exists(src):
            log.info(f"Copying {item}...")
            try:
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            except (OSError, shutil.Error) as e:
                log.error(f"Failed to copy {item}: {e}")
                return
        else:
            log.warning(f"Source not found, skipping: {item}")

    bundled_poses_src = os.path.join(project_dir, "poses")
    bundled_poses_dst = os.path.join(krita_dir, "poses")
    if os.path.exists(bundled_poses_src):
        os.makedirs(bundled_poses_dst, exist_ok=True)
        for filename in os.listdir(bundled_poses_src):
            if filename.endswith(".json"):
                src_file = os.path.join(bundled_poses_src, filename)
                dst_file = os.path.join(bundled_poses_dst, filename)
                try:
                    shutil.copy2(src_file, dst_file)
                    log.debug(f"Copied pose: {filename}")
                except (OSError, shutil.Error) as e:
                    log.warning(f"Failed to copy pose {filename}: {e}")

    for f in files:
        src = os.path.join(project_dir, f)
        dst = os.path.join(krita_dir, f)
        if os.path.exists(src):
            try:
                shutil.copy2(src, dst)
                log.debug(f"Copied file: {f}")
            except (OSError, shutil.Error) as e:
                log.error(f"Failed to copy {f}: {e}")
                return
        else:
            log.warning(f"Source file not found, skipping: {f}")

    needs_numpy = args.force_deps or not check_package_installed(krita_dir, "numpy", "2.0.0")
    needs_pyopengl = args.force_deps or not check_package_installed(krita_dir, "PyOpenGL", "3.1.0")

    if not needs_numpy and not needs_pyopengl:
        log.info("All dependencies already installed. Skipping pip install.")
        log.info("Done! Restart Krita.")
        return

    if args.solo:
        log.info("Dependencies skipped (--solo mode).")
        log.info("Done! Restart Krita.")
        return

    system = platform.system()
    if system == "Linux":
        platform_tag = "manylinux_2_17_x86_64"
    elif system == "Windows":
        platform_tag = "win_amd64"
    elif system == "Darwin":
        if platform.machine() == "arm64":
            platform_tag = "macosx_11_0_arm64"
        else:
            platform_tag = "macosx_10_9_x86_64"
    else:
        platform_tag = None

    log.debug(f"Detected platform: system={system}, machine={platform.machine()}, tag={platform_tag}")

    pip_base = [
        sys.executable, "-m", "pip", "install", "--upgrade",
        "--target", krita_dir,
        "--python-version", "3.10",
        "--implementation", "cp",
        "--abi", "cp310",
    ]

    if platform_tag:
        pip_base.extend(["--platform", platform_tag])

    packages_to_install = []

    if needs_numpy:
        packages_to_install.append("numpy>=2.0.0,<2.3.0")

    if needs_pyopengl:
        packages_to_install.extend(["PyOpenGL>=3.1.0", "PyOpenGL_accelerate>=3.1.0"])

    if packages_to_install:
        log.info("Installing dependencies for Python 3.10 (Krita's Python version)...")
        log.info("Note: Warnings about system-wide packages can be ignored.")
        log.info("  These don't affect the plugin since Krita uses its own Python environment.")

        if needs_numpy:
            pip_cmd_numpy = pip_base + [
                "--only-binary", ":all:",
                "numpy>=2.0.0,<2.3.0"
            ]
            log.debug(f"numpy pip command: {pip_cmd_numpy}")
            try:
                log.info("Installing numpy...")
                subprocess.check_call(pip_cmd_numpy)
                log.info("numpy installed successfully.")
            except subprocess.CalledProcessError as e:
                log.error(f"Failed to install numpy: {e}")
                log.error("Please ensure 'pip' is installed.")
                return

        if needs_pyopengl:
            pip_cmd_pyopengl = [
                sys.executable, "-m", "pip", "install", "--upgrade",
                "--target", krita_dir,
                "PyOpenGL>=3.1.0", "PyOpenGL_accelerate>=3.1.0"
            ]
            log.debug(f"PyOpenGL pip command: {pip_cmd_pyopengl}")
            try:
                log.info("Installing PyOpenGL...")
                subprocess.check_call(pip_cmd_pyopengl)
                log.info("PyOpenGL installed successfully.")
            except subprocess.CalledProcessError as e:
                log.error(f"Failed to install PyOpenGL: {e}")
                log.error("Please ensure 'pip' is installed.")
                return

    log.info("Done! Restart Krita.")

if __name__ == "__main__":
    main()
