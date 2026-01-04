'''
This script prints all the main folders under the /NVIDIA directory on nucleus server
cd isaac-sim
source ./kit/setup_python_env.sh 
./python.sh /home/ubuntu/Motion_MVP1/Tests/Test2.py
'''

import omni.client

HAS_CONTENT = 0x1  # internal omniverse flag

def list_nucleus_dir(url: str):
    result, entries = omni.client.list(url)
    if result != omni.client.Result.OK:
        raise RuntimeError(f"Failed to list {url}: {result}")

    out = []
    for e in entries:
        is_file = bool(e.flags & HAS_CONTENT)
        out.append({
            "name": e.relative_path,
            "is_file": is_file,
            "is_dir": not is_file,
            "flags": e.flags
        })
    return out


# TEST
root = "omniverse://35.227.93.135/NVIDIA"
items = list_nucleus_dir(root)

for i in items:
    print(i)
