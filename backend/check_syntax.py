import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

print("Checking runtime.py...")
try:
    from backend.app.core.runtime import RuntimeEngine
    print("RuntimeEngine imported successfully.")
except Exception as e:
    print(f"Error importing RuntimeEngine: {e}")
    import traceback
    traceback.print_exc()

print("Checking routers/world.py...")
try:
    from backend.app.routers import world
    print("Router world imported successfully.")
except Exception as e:
    print(f"Error importing router world: {e}")
    import traceback
    traceback.print_exc()
