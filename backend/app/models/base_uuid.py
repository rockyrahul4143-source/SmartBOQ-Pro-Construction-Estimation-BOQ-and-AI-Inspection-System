"""
SQLite + PostgreSQL compatible UUID column.
Uses sqlalchemy's built-in UUIDType which works with both backends.
"""
from sqlalchemy import types
import uuid


class GUID(types.TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type when available, otherwise stores as String(36).
    """
    impl = types.String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(str(value))

    def process_literal_param(self, value, dialect):
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)
