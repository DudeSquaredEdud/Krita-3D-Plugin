import os
import shutil

with open('krita_3d_pose/manifest.json') as f:
    for line in f:
        if "version" in line:
            version_number = line.split("\"")[3]
            break

dir = f"releases/{version_number}/"

if not os.path.exists(dir):
    os.makedirs(dir)

shutil.copytree("krita_3d_pose/",dir+"krita_3d_pose/")
shutil.copytree("pose_engine/",dir+"pose_engine/")
shutil.copy("krita_3d_pose.desktop",dir+"krita_3d_pose.desktop")
shutil.copy("install.py",dir+"install.py")

shutil.make_archive(f"k3d_{version_number}", 'zip', dir)


