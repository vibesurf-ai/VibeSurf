"""
VibeSurf Backend Database Package - Simplified

Single table design for task tracking and execution.
"""

from .manager import get_db_session
from .models import (
    Base,
    Task,
    TaskStatus,
)
from .queries import TaskQueries
