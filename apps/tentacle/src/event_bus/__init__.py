"""Event Bus implementation for Tentacle."""

from .redis_event_bus import RedisEventBus

__all__ = ['RedisEventBus']