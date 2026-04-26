import os
import shutil
import subprocess
import sys
import platform
import argparse

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

def clean_pip_packages(krita_dir, packages_to_keep):
    
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
                print(f"Removing old package: {os.path.basename(path)}")
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

def main():
    parser = argparse.ArgumentParser(description="Install Krita 3D Pose Plugin")
    parser.add_argument("--clean", action="store_true", help="Force clean old dependencies before installing")
    parser.add_argument("--force-deps", action="store_true", help="Force reinstall dependencies even if already present")
    parser.add_argument("--solo", action="store_true", help="Skip installation of dependencies")
    args = parser.parse_args()
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    krita_dir = get_krita_dir()

    print(f"Installing to: {krita_dir}")

    os.makedirs(krita_dir, exist_ok=True)

    if args.clean:
        print("Cleaning old dependencies...")
        clean_pip_packages(krita_dir, [])

    items = ["krita_3d_pose", "pose_engine"]
    files = ["krita_3d_pose.desktop"]

    for item in items:
        src = os.path.join(project_dir, item)
        dst = os.path.join(krita_dir, item)
        if os.path.exists(src):
            print(f"Copying {item}...")
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    bundled_poses_src = os.path.join(project_dir, "poses")
    bundled_poses_dst = os.path.join(krita_dir, "poses")
    if os.path.exists(bundled_poses_src):
        os.makedirs(bundled_poses_dst, exist_ok=True)
        for filename in os.listdir(bundled_poses_src):
            if filename.endswith(".json"):
                src_file = os.path.join(bundled_poses_src, filename)
                dst_file = os.path.join(bundled_poses_dst, filename)
                shutil.copy2(src_file, dst_file)

    for f in files:
        src = os.path.join(project_dir, f)
        dst = os.path.join(krita_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    needs_numpy = args.force_deps or not check_package_installed(krita_dir, "numpy", "2.0.0")
    needs_pyopengl = args.force_deps or not check_package_installed(krita_dir, "PyOpenGL", "3.1.0")
    
    if not needs_numpy and not needs_pyopengl:
        print("All dependencies already installed. Skipping pip install.")
        print("Done! Restart Krita.")
        return

    if args.solo:
        print("Dependencies skipped!")
        print("Done! Restart Krita.")
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
        print("Installing dependencies for Python 3.10 (Krita's Python version)...")
        print("Note: Warnings about system-wide packages can be ignored.")
        print("  These don't affect the plugin since Krita uses its own Python environment.")

        if needs_numpy:
            pip_cmd_numpy = pip_base + [
                "--only-binary", ":all:",
                "numpy>=2.0.0,<2.3.0"
            ]
            try:
                print("Installing numpy...")
                subprocess.check_call(pip_cmd_numpy)
            except subprocess.CalledProcessError:
                print("Failed to install numpy. Please ensure 'pip' is installed.")
                return

        
        if needs_pyopengl:
            pip_cmd_pyopengl = [
                sys.executable, "-m", "pip", "install", "--upgrade",
                "--target", krita_dir,
                "PyOpenGL>=3.1.0",
                "PyOpenGL_accelerate>=3.1.0"
            ]
            try:
                print("Installing PyOpenGL...")
                subprocess.check_call(pip_cmd_pyopengl)
            except subprocess.CalledProcessError:
                print("Failed to install PyOpenGL. Please ensure 'pip' is installed.")
                return

    print("Done! Restart Krita.")

if __name__ == "__main__":
    main()