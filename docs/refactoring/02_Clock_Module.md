# Clock Module (WorldClock)

## Path: `backend/app/core/clock.py`

## Logic
The `WorldClock` handles the core game loop. It runs an `asyncio` task that ticks every real-world second, advancing game time by `time_scale` seconds.

## Key Implementation

```python
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Callable, Optional

logger = logging.getLogger(__name__)

class WorldClock:
    def __init__(self, start_time: datetime, time_scale: float = 60.0):
        self.current_time = start_time
        self.time_scale = time_scale  # 1 real second = X game seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._subscribers: List[Callable[[datetime], None]] = []

    def start(self):
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._tick_loop())
            logger.info("World Clock started")

    def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("World Clock stopped")

    def set_scale(self, scale: float):
        self.time_scale = scale
        logger.info(f"World Clock scale set to {scale}")

    def subscribe(self, callback: Callable[[datetime], None]):
        """Register a callback function to be called on every tick."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    async def _tick_loop(self):
        try:
            while self.is_running:
                await asyncio.sleep(1)  # Real world 1 second
                
                # Advance game time
                self.current_time += timedelta(seconds=self.time_scale)
                
                # Notify subscribers (async safely)
                for callback in self._subscribers:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(self.current_time)
                        else:
                            callback(self.current_time)
                    except Exception as e:
                        logger.error(f"Error in clock subscriber: {e}")
                        
        except asyncio.CancelledError:
            logger.info("Clock loop cancelled")
        except Exception as e:
            logger.error(f"Clock loop crash: {e}")
            self.is_running = False
