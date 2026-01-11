# robot_task_controller.py
import time
import carb

class RobotTaskController:
    """
    Dummy controller: later you will replace execute_task() with your real stack call.
    """

    def __init__(self):
        self._busy = False

    def is_busy(self) -> bool:
        return self._busy

    def execute_task(self, task: dict) -> dict:
        """
        task example:
        {
          "task": "deliver",
          "object": "trolley",
          "destination": "station_1"
        }
        """
        if self._busy:
            return {
                "ok": False,
                "message": "Robot controller is busy. Try again."
            }

        self._busy = True
        try:
            # Dummy execution
            carb.log_info(f"[RobotTaskController] Executing: {task}")

            # Simulate doing something
            time.sleep(0.5)

            carb.log_info("[RobotTaskController] Done.")
            return {
                "ok": True,
                "message": f"Task executed successfully: {task}"
            }
        except Exception as e:
            carb.log_error(f"[RobotTaskController] Failed: {e}")
            return {
                "ok": False,
                "message": f"Task failed: {e}"
            }
        finally:
            self._busy = False
