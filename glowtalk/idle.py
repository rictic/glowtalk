import platform
import time
from abc import ABC, abstractmethod

class IdleChecker(ABC):
    @abstractmethod
    def get_idle_time(self) -> float:
        """Returns the number of seconds the system has been idle."""
        pass

class WindowsIdleChecker(IdleChecker):
    def __init__(self):
        import ctypes
        from ctypes import Structure, wintypes

        class LASTINPUTINFO(Structure):
            _fields_ = [
                ('cbSize', wintypes.UINT),
                ('dwTime', wintypes.DWORD)
            ]

        self.lastInputInfo = LASTINPUTINFO()
        self.lastInputInfo.cbSize = ctypes.sizeof(self.lastInputInfo)
        self.ctypes = ctypes

    def get_idle_time(self):
        self.ctypes.windll.user32.GetLastInputInfo(self.ctypes.byref(self.lastInputInfo))
        current_tick = self.ctypes.windll.kernel32.GetTickCount()
        return (current_tick - self.lastInputInfo.dwTime) / 1000.0

class LinuxIdleChecker(IdleChecker):
    def __init__(self):
        try:
            from Xlib import display, X
            from Xlib.ext import screensaver
        except ImportError:
            raise ImportError("Please install python-xlib: pip install python-xlib")

        self.display = display.Display()
        self.screensaver = self.display.get_extension_data(screensaver.extname)

        if not self.screensaver.present:
            raise RuntimeError("Screensaver extension not present")

    def get_idle_time(self):
        info = self.screensaver.query_info(self.display.screen().root)
        return info.idle / 1000.0  # Convert from ms to seconds

class MacIdleChecker(IdleChecker):
    def __init__(self):
        try:
            from Quartz import (
                CGEventSourceSecondsSinceLastEventType,
                kCGEventSourceStateHIDSystemState,
                kCGAnyInputEventType,
            )
        except ImportError:
            raise ImportError(
                "MacOS-specific features require additional dependencies. "
                "Please install them with: uv pip install glowtalk[macos]"
            )

        self.get_idle_time_since_last_event = CGEventSourceSecondsSinceLastEventType
        self.system_state = kCGEventSourceStateHIDSystemState
        self.any_input = kCGAnyInputEventType

    def get_idle_time(self):
        return self.get_idle_time_since_last_event(
            self.system_state,
            self.any_input
        )

def create_idle_checker() -> IdleChecker:
    """Factory function to create the appropriate idle checker for the current platform."""
    system = platform.system()
    if system == "Windows":
        return WindowsIdleChecker()
    elif system == "Linux":
        return LinuxIdleChecker()
    elif system == "Darwin":  # macOS
        return MacIdleChecker()
    else:
        raise NotImplementedError(f"System {system} is not supported")

def run_when_idle(task_function, idle_threshold_seconds=300):
    """
    Runs the specified function only when the system is idle.

    If the function has nothing to do, it should not return immediately, but
    either block until it has work to do and then return, or sleep for a bit
    and then return.

    The function will be called repeatedly.

    Args:
        task_function: Function to run when system is idle
        idle_threshold_seconds (int): Number of seconds to consider system as idle
    """
    try:
        idle_checker = create_idle_checker()
    except ImportError as e:
        print(f"Error: {e}")
        return
    except NotImplementedError as e:
        print(f"Error: {e}")
        return

    print(f"Running on {platform.system()}")
    print(f"Waiting for system to be idle for {idle_threshold_seconds} seconds...")

    while True:
        try:
            while idle_checker.get_idle_time() > idle_threshold_seconds:
                task_function()

            # Check if system becomes active
            print("System is active, not working...")
            while idle_checker.get_idle_time() < idle_threshold_seconds:
                time.sleep(1)

        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)  # Wait a bit before retrying

# Example usage
if __name__ == "__main__":
    def example_task():
        print("work work work work work...")
        time.sleep(1)

    run_when_idle(example_task, idle_threshold_seconds=10)
