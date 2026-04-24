import sys
import os
import platform

_path_setup_done = False

def ensure_path() -> None:
    global _path_setup_done

    if _path_setup_done:
        return

    _pose_engine_dir = os.path.dirname(os.path.realpath(__file__))
    _parent_dir = os.path.dirname(_pose_engine_dir)

    if _pose_engine_dir not in sys.path:
        sys.path.insert(0, _pose_engine_dir)

    if _parent_dir not in sys.path:
        sys.path.insert(0, _parent_dir)

    _path_setup_done = True


def get_parent_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def get_user_data_dir() -> str:
    system = platform.system()
    home = os.path.expanduser("~")
    if system == "Windows":
        base = os.getenv("APPDATA", os.path.join(home, "AppData", "Roaming"))
    elif system == "Darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = os.path.join(home, ".local", "share")
    data_dir = os.path.join(base, "krita3D_poses")
    os.makedirs(data_dir, exist_ok=True)
    return data_dir
