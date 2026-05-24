from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Union

logger = logging.getLogger("fabouanes.event_bus")

# Type definitions for listeners (callable functions or async coroutines)
ListenerType = Callable[..., Union[None, Coroutine[Any, Any, None]]]

class EventBus:
    """Lightweight Event Bus for functional decoupling between modules."""
    
    def __init__(self):
        self._listeners: Dict[str, List[ListenerType]] = {}

    def subscribe(self, event_type: str, listener: ListenerType) -> None:
        """Register a callback or coroutine to listen to a specific event."""
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if listener not in self._listeners[event_type]:
            self._listeners[event_type].append(listener)
            logger.info("Subscribed %s to event %s", listener.__name__, event_type)

    def unsubscribe(self, event_type: str, listener: ListenerType) -> None:
        """Remove a registered listener from an event."""
        if event_type in self._listeners and listener in self._listeners[event_type]:
            self._listeners[event_type].remove(listener)
            logger.info("Unsubscribed %s from event %s", listener.__name__, event_type)

    def publish_sync(self, event_type: str, **kwargs: Any) -> None:
        """Synchronously publish an event to all registered listeners."""
        if event_type not in self._listeners:
            return
        for listener in self._listeners[event_type]:
            try:
                res = listener(**kwargs)
                # If listener returned a coroutine, schedule it on the running event loop
                if asyncio.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        # Fallback if no loop is running
                        asyncio.run(res)
            except Exception as e:
                logger.error("Error in sync listener %s for event %s: %s", listener.__name__, event_type, e, exc_info=True)

    async def publish_async(self, event_type: str, **kwargs: Any) -> None:
        """Asynchronously publish an event to all registered listeners."""
        if event_type not in self._listeners:
            return
        tasks = []
        for listener in self._listeners[event_type]:
            try:
                res = listener(**kwargs)
                if asyncio.iscoroutine(res):
                    tasks.append(res)
            except Exception as e:
                logger.error("Error invoking listener %s for event %s: %s", listener.__name__, event_type, e, exc_info=True)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

# Global singleton event bus instance
event_bus = EventBus()
