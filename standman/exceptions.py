"""
Custom exception definitions for standman.

This module provides framework-specific errors used in session
and port management.
"""

class OccupiedError(Exception):
    """Raised when a Port is already occupied by another session."""
    pass

class DeniedError(Exception):
    """Raised when a connection is denied by the policy or Port."""
    pass

