'''
This script prints all the main folders under the /NVIDIA/Assets and /Environments directory on nucleus server
cd isaac-sim
source ./kit/setup_python_env.sh 
./python.sh /home/ubuntu/Motion_MVP1/Tests/Test2.py
'''

import omni.client

HAS_CONTENT = 0x1

def list_all_subfolders(root_url: str, indent=0):
    result, entries = omni.client.list(root_url)
    if result != omni.client.Result.OK:
        print(" " * indent + f"[ERROR] Cannot access {root_url}: {result}")
        return

    for e in entries:
        is_file = bool(e.flags & HAS_CONTENT)
        full_path = f"{root_url}/{e.relative_path}"

        if not is_file:
            print(" " * indent + f"[DIR] {full_path}")
            list_all_subfolders(full_path, indent + 2)


# ---- RUN ----
ASSETS_ROOT = "omniverse://35.227.93.135/NVIDIA/Assets"
ENV_ROOT = "omniverse://35.227.93.135/NVIDIA/Environments"

print("\n=== ASSETS ===")
list_all_subfolders(ASSETS_ROOT)

print("\n=== ENVIRONMENTS ===")
list_all_subfolders(ENV_ROOT)
