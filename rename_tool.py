import os
import shutil
import sys

def get_executable_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)  # For PyInstaller
    else:
        return os.path.dirname(os.path.abspath(__file__))

# print pwd
# print("current working directory: ", os.getcwd())
os.chdir(get_executable_dir())
# print("current working directory: ", os.getcwd())

SRC_DIR = './screenshots'
DST_DIR = os.path.join(SRC_DIR, 'all')

if not os.path.exists(DST_DIR):
    os.makedirs(DST_DIR)

for entry in os.listdir(SRC_DIR):
    subdir = os.path.join(SRC_DIR, entry)
    if entry == 'all' or not os.path.isdir(subdir):
        continue
    id_ = entry
    for fname in os.listdir(subdir):
        if not fname.lower().endswith('.png'):
            continue
        name, ext = os.path.splitext(fname)
        src_path = os.path.join(subdir, fname)
        dst_fname = f'{name}_{id_}{ext}'
        dst_path = os.path.join(DST_DIR, dst_fname)
        shutil.move(src_path, dst_path)
        print(f'Moved: {src_path} -> {dst_path}')