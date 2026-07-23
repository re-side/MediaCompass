"""Core package for the Media Compass educational project."""

from .models import MediaItem
from .recommender import recommend

__all__ = ["MediaItem", "recommend"]
