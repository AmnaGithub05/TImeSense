"""SQLite persistence for tasks, estimates, feedback, and user calibration."""

import sqlite3
from pathlib import Path

from .schemas import TaskExtraction


class TaskStore:
    """Store analysis records and maintain an exponential moving average."""

    def __init__(self, database_path: str, ema_alpha: float = 0.3) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.ema_alpha = ema_alpha
        with sqlite3.connect(self.database_path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS estimates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id),
                    estimated_minutes REAL NOT NULL,
                    adjusted_minutes REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL REFERENCES tasks(id),
                    user_id TEXT NOT NULL,
                    actual_minutes REAL NOT NULL,
                    speed_factor REAL NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS user_speed (
                    user_id TEXT PRIMARY KEY,
                    factor REAL NOT NULL DEFAULT 1.0
                );
                """
            )

    def speed_factor(self, user_id: str) -> float:
        """Return a user's calibration factor, defaulting to 1."""
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT factor FROM user_speed WHERE user_id = ?", (user_id,)
            ).fetchone()
        return float(row[0]) if row else 1.0

    def create_task(
        self, extraction: TaskExtraction, user_id: str = "default"
    ) -> tuple[int, float]:
        """Persist a task and estimate adjusted by the current speed factor."""
        factor = self.speed_factor(user_id)
        adjusted = max(1.0, extraction.estimated_minutes * factor)
        with sqlite3.connect(self.database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (user_id, category, summary) VALUES (?, ?, ?)",
                (user_id, extraction.category, extraction.summary),
            )
            task_id = cursor.lastrowid
            connection.execute(
                """
                INSERT INTO estimates (task_id, estimated_minutes, adjusted_minutes)
                VALUES (?, ?, ?)
                """,
                (task_id, extraction.estimated_minutes, adjusted),
            )
        return int(task_id), adjusted

    def record_feedback(
        self, task_id: int, actual_minutes: float, user_id: str
    ) -> float:
        """Update the user's EMA with actual/estimated duration."""
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT estimated_minutes FROM estimates
                WHERE task_id = ? ORDER BY id DESC LIMIT 1
                """,
                (task_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Unknown task id: {task_id}")
            ratio = actual_minutes / float(row[0])
            previous = self.speed_factor(user_id)
            factor = previous + self.ema_alpha * (ratio - previous)
            connection.execute(
                """
                INSERT INTO user_speed (user_id, factor) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET factor = excluded.factor
                """,
                (user_id, factor),
            )
            connection.execute(
                """
                INSERT INTO feedback (task_id, user_id, actual_minutes, speed_factor)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, user_id, actual_minutes, factor),
            )
        return factor
