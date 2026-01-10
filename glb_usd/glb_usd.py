# import aspose.threed as a3d

# scene = a3d.Scene.from_file("/home/ubuntu/Motion_MVP1/glb_usd/Assets_glb/crate_trellis3d.glb")
# scene.save("/home/ubuntu/Motion_MVP1/glb_usd/Assets_glb/crate_trellis3d.usd")

import asyncio
import omni.kit.asset_converter

input_path = "/home/ubuntu/Motion_MVP1/glb_usd/Assets_glb/crate_trellis3d.glb"
output_path = "/home/ubuntu/Motion_MVP1/glb_usd/Assets_usd/crate_trellis3d.usd"
# ----------------------------------------------

def progress_callback(current_step: int, total: int):
    # Show progress
    print(f"{current_step} of {total}")

async def convert(input_asset_path, output_asset_path):
    task_manager = converter.get_instance()
    task = task_manager.create_converter_task(input_asset_path, output_asset_path, progress_callback)
    success = await task.wait_until_finished()
    if not success:
        detailed_status_code = task.get_status()
        detailed_status_error_string = task.get_error_message()
        ...


asyncio.ensure_future(convert(input_path, output_path))

