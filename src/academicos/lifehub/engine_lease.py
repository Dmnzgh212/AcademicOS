"""Single-manager ownership using a separate SQLite lock database."""
from pathlib import Path
import sqlite3


class EngineLease:
    """Hold an exclusive transaction without locking the platform data database.

    SQLite releases the lock when the process/connection dies. Keep the sidecar
    file: unlinking a locked file could let another manager lock a different inode.
    This is cooperative local-manager coordination, not an untrusted-host boundary.
    """

    def __init__(self, db_path: str | Path):
        db = Path(db_path).resolve()
        db.parent.mkdir(parents=True, exist_ok=True)
        self.path = db.with_name(db.name + ".engine-lock")
        self._connection = sqlite3.connect(self.path, timeout=0)
        try:
            self._connection.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            self._connection.close()
            if getattr(exc, "sqlite_errorcode", None) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                raise PermissionError(f"Engine database already owned by another manager: {db}") from exc
            raise

    def close(self):
        self._connection.close()
