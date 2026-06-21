"""SQLite persistence for vocabulary game progress."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "progress.db"

PRIORITY_ORDER = {"test": 0, "high": 1, "normal": 2}
DEFAULT_DIFFICULTY = 50.0
WRONG_BUMP = 12.0
CORRECT_DROP = 8.0
VALID_GRADES = ("ב'", "ג'", "ד'", "ה'", "ו'")
DEFAULT_GRADE = "ה'"
DEFAULT_AVATAR = "🦄"
VALID_AVATARS = ("🦄", "🐱", "🐶", "🐼", "🦊", "🐰", "🐨", "🐯")
GRADE_TO_LESSON = {"ב'": 1, "ג'": 2, "ד'": 3, "ה'": 4, "ו'": 4}


def default_password(name: str) -> str:
    return f"{name.strip()}123"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _sql_str(value: str) -> str:
    return value.replace("'", "''")


def _table_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    return column in columns


def _migrate_teacher_words(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(teacher_words)")}
    if "lesson_name" not in columns:
        conn.execute("ALTER TABLE teacher_words ADD COLUMN lesson_name TEXT NOT NULL DEFAULT ''")
    if "priority" not in columns:
        conn.execute("ALTER TABLE teacher_words ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")
    if "test_date" not in columns:
        conn.execute("ALTER TABLE teacher_words ADD COLUMN test_date TEXT")
    conn.execute(
        """
        UPDATE teacher_words
        SET lesson_name = 'שיעור ' || lesson
        WHERE lesson_name = '' OR lesson_name IS NULL
        """
    )


def _migrate_students_profile(conn: sqlite3.Connection) -> None:
    if not _table_has_column(conn, "students", "grade"):
        conn.execute(
            f"ALTER TABLE students ADD COLUMN grade TEXT NOT NULL DEFAULT '{_sql_str(DEFAULT_GRADE)}'"
        )
    if not _table_has_column(conn, "students", "avatar"):
        conn.execute(
            f"ALTER TABLE students ADD COLUMN avatar TEXT NOT NULL DEFAULT '{_sql_str(DEFAULT_AVATAR)}'"
        )
    if not _table_has_column(conn, "students", "password"):
        conn.execute("ALTER TABLE students ADD COLUMN password TEXT NOT NULL DEFAULT ''")
    _ensure_student_passwords(conn)


def _ensure_student_passwords(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, name, password FROM students WHERE password IS NULL OR password = ''"
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE students SET password = ? WHERE id = ?",
            (default_password(row["name"]), row["id"]),
        )


def _migrate_student_scope(conn: sqlite3.Connection) -> None:
    _migrate_students_profile(conn)
    student_row = conn.execute("SELECT id FROM students ORDER BY id LIMIT 1").fetchone()
    if not student_row:
        return
    default_student_id = student_row["id"]

    for table in ("answers", "sessions"):
        if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone():
            if not _table_has_column(conn, table, "student_id"):
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN student_id INTEGER NOT NULL DEFAULT {default_student_id}"
                )

    wp_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='word_performance'"
    ).fetchone()
    if wp_exists and not _table_has_column(conn, "word_performance", "student_id"):
        conn.executescript(
            f"""
            CREATE TABLE word_performance_new (
                student_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                times_seen INTEGER NOT NULL DEFAULT 0,
                times_correct INTEGER NOT NULL DEFAULT 0,
                times_wrong INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT,
                difficulty_score REAL NOT NULL DEFAULT 50.0,
                PRIMARY KEY (student_id, word),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );
            INSERT INTO word_performance_new (
                student_id, word, times_seen, times_correct, times_wrong,
                last_seen, difficulty_score
            )
            SELECT {default_student_id}, word, times_seen, times_correct, times_wrong,
                   last_seen, difficulty_score
            FROM word_performance;
            DROP TABLE word_performance;
            ALTER TABLE word_performance_new RENAME TO word_performance;
            """
        )


def init_db() -> None:
    grade_default = _sql_str(DEFAULT_GRADE)
    avatar_default = _sql_str(DEFAULT_AVATAR)
    with get_connection() as conn:
        conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                grade TEXT NOT NULL DEFAULT '{grade_default}',
                avatar TEXT NOT NULL DEFAULT '{avatar_default}',
                password TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                lesson INTEGER NOT NULL,
                english_word TEXT NOT NULL,
                question_type TEXT NOT NULL,
                section TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                lesson INTEGER NOT NULL,
                section TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_state (
                student_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (student_id, key),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS teacher_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lesson INTEGER NOT NULL,
                lesson_name TEXT NOT NULL DEFAULT '',
                english TEXT NOT NULL,
                hebrew TEXT NOT NULL,
                example_en TEXT NOT NULL,
                example_he TEXT NOT NULL DEFAULT '',
                priority TEXT NOT NULL DEFAULT 'normal',
                test_date TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS word_performance (
                student_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                times_seen INTEGER NOT NULL DEFAULT 0,
                times_correct INTEGER NOT NULL DEFAULT 0,
                times_wrong INTEGER NOT NULL DEFAULT 0,
                last_seen TEXT,
                difficulty_score REAL NOT NULL DEFAULT 50.0,
                PRIMARY KEY (student_id, word),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS daily_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                session_date TEXT NOT NULL,
                words_json TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                score INTEGER,
                total INTEGER,
                completed_at TEXT,
                UNIQUE(student_id, session_date),
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );
            """
        )
        _migrate_teacher_words(conn)
        _migrate_student_scope(conn)
        _ensure_student_passwords(conn)
        _migrate_daily_sessions(conn)
        _migrate_student_stories(conn)


def _migrate_student_stories(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS student_stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            story_type TEXT NOT NULL,
            story_date TEXT NOT NULL,
            title TEXT NOT NULL,
            story_en TEXT NOT NULL,
            story_he TEXT NOT NULL,
            words_json TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """
    )


def _migrate_daily_sessions(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            session_date TEXT NOT NULL,
            words_json TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            score INTEGER,
            total INTEGER,
            completed_at TEXT,
            UNIQUE(student_id, session_date),
            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
        )
        """
    )


def verify_student_password(student_id: int, password: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT password FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()
    if not row:
        return False
    return row["password"] == password.strip()


def _normalize_word(word: str) -> str:
    return word.strip().lower()


def _default_performance(word: str = "") -> dict[str, Any]:
    return {
        "word": word,
        "times_seen": 0,
        "times_correct": 0,
        "times_wrong": 0,
        "last_seen": None,
        "difficulty_score": DEFAULT_DIFFICULTY,
    }


def _recalculate_difficulty(
    times_seen: int,
    times_correct: int,
    times_wrong: int,
    current_score: float,
    is_correct: bool,
) -> float:
    if times_seen <= 1:
        score = DEFAULT_DIFFICULTY
    else:
        score = current_score

    if is_correct:
        score -= CORRECT_DROP
    else:
        score += WRONG_BUMP

    if times_seen >= 2:
        accuracy = times_correct / times_seen
        score += (0.5 - accuracy) * 20

    return round(max(0.0, min(100.0, score)), 1)


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------


def get_students() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, name, grade, avatar, password, created_at FROM students ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_student(student_id: int) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id, name, grade, avatar, password, created_at FROM students WHERE id = ?",
            (student_id,),
        ).fetchone()
    return dict(row) if row else None


def _validate_grade(grade: str) -> str:
    if grade not in VALID_GRADES:
        raise ValueError("כיתה לא תקינה")
    return grade


def _validate_avatar(avatar: str) -> str:
    if avatar not in VALID_AVATARS:
        raise ValueError("אווטאר לא תקין")
    return avatar


def create_student(
    name: str,
    grade: str = DEFAULT_GRADE,
    avatar: str = DEFAULT_AVATAR,
    password: str | None = None,
) -> int:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("יש להזין שם")
    grade = _validate_grade(grade)
    avatar = _validate_avatar(avatar)
    student_password = password.strip() if password else default_password(clean_name)
    if not student_password:
        raise ValueError("יש להזין סיסמה")
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO students (name, grade, avatar, password, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    clean_name,
                    grade,
                    avatar,
                    student_password,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            return int(cursor.lastrowid)
        except sqlite3.IntegrityError as exc:
            raise ValueError("תלמידה עם השם הזה כבר קיימת") from exc


def update_student(
    student_id: int,
    name: str | None = None,
    grade: str | None = None,
    avatar: str | None = None,
    password: str | None = None,
) -> None:
    student = get_student(student_id)
    if not student:
        raise ValueError("תלמידה לא נמצאה")

    new_name = name.strip() if name is not None else student["name"]
    new_grade = _validate_grade(grade) if grade is not None else student["grade"]
    new_avatar = _validate_avatar(avatar) if avatar is not None else student["avatar"]
    new_password = password.strip() if password is not None else student["password"]

    if not new_name:
        raise ValueError("יש להזין שם")
    if not new_password:
        raise ValueError("יש להזין סיסמה")

    with get_connection() as conn:
        try:
            conn.execute(
                """
                UPDATE students
                SET name = ?, grade = ?, avatar = ?, password = ?
                WHERE id = ?
                """,
                (new_name, new_grade, new_avatar, new_password, student_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("תלמידה עם השם הזה כבר קיימת") from exc


def delete_student(student_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))


def get_student_overview(student_id: int) -> dict[str, Any]:
    summary = get_learning_summary(student_id)
    student = get_student(student_id)
    return {
        "id": student_id,
        "name": student["name"] if student else "",
        "grade": student["grade"] if student else DEFAULT_GRADE,
        "avatar": student["avatar"] if student else DEFAULT_AVATAR,
        **summary,
    }


# ---------------------------------------------------------------------------
# Progress (per student)
# ---------------------------------------------------------------------------


def record_answer(
    student_id: int,
    lesson: int,
    english_word: str,
    question_type: str,
    section: str,
    is_correct: bool,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO answers (
                student_id, lesson, english_word, question_type, section, is_correct, answered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                lesson,
                english_word,
                question_type,
                section,
                1 if is_correct else 0,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    if section in ("practice", "daily", "story") and question_type != "comprehension":
        record_word_performance(student_id, english_word, is_correct)


def record_word_performance(student_id: int, word: str, is_correct: bool) -> None:
    key = _normalize_word(word)
    now = datetime.now().isoformat(timespec="seconds")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM word_performance WHERE student_id = ? AND word = ?",
            (student_id, key),
        ).fetchone()

        if row:
            times_seen = int(row["times_seen"]) + 1
            times_correct = int(row["times_correct"]) + (1 if is_correct else 0)
            times_wrong = int(row["times_wrong"]) + (0 if is_correct else 1)
            difficulty = _recalculate_difficulty(
                times_seen,
                times_correct,
                times_wrong,
                float(row["difficulty_score"]),
                is_correct,
            )
            conn.execute(
                """
                UPDATE word_performance
                SET times_seen = ?, times_correct = ?, times_wrong = ?,
                    last_seen = ?, difficulty_score = ?
                WHERE student_id = ? AND word = ?
                """,
                (times_seen, times_correct, times_wrong, now, difficulty, student_id, key),
            )
        else:
            times_seen = 1
            times_correct = 1 if is_correct else 0
            times_wrong = 0 if is_correct else 1
            difficulty = _recalculate_difficulty(
                times_seen, times_correct, times_wrong, DEFAULT_DIFFICULTY, is_correct
            )
            conn.execute(
                """
                INSERT INTO word_performance (
                    student_id, word, times_seen, times_correct, times_wrong,
                    last_seen, difficulty_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (student_id, key, times_seen, times_correct, times_wrong, now, difficulty),
            )


def get_word_performance(student_id: int, word: str) -> dict[str, Any]:
    key = _normalize_word(word)
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM word_performance WHERE student_id = ? AND word = ?",
            (student_id, key),
        ).fetchone()
    return dict(row) if row else _default_performance(key)


def get_all_word_performance(student_id: int) -> dict[str, dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM word_performance WHERE student_id = ?",
            (student_id,),
        ).fetchall()
    return {row["word"]: dict(row) for row in rows}


def get_difficult_words(student_id: int, limit: int = 10, min_seen: int = 1) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM word_performance
            WHERE student_id = ? AND times_seen >= ?
            ORDER BY difficulty_score DESC, times_wrong DESC, times_seen DESC
            LIMIT ?
            """,
            (student_id, min_seen, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_mastered_words(
    student_id: int,
    limit: int = 10,
    min_seen: int = 3,
    min_accuracy: float = 0.75,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM word_performance
            WHERE student_id = ?
              AND times_seen >= ?
              AND CAST(times_correct AS REAL) / times_seen >= ?
            ORDER BY difficulty_score ASC, times_correct DESC
            LIMIT ?
            """,
            (student_id, min_seen, min_accuracy, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_learning_summary(student_id: int) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS practiced_words,
                COALESCE(AVG(difficulty_score), 0) AS avg_difficulty,
                COALESCE(SUM(times_seen), 0) AS total_seen,
                COALESCE(SUM(times_correct), 0) AS total_correct,
                COALESCE(SUM(times_wrong), 0) AS total_wrong
            FROM word_performance
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        strong_count = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM word_performance
            WHERE student_id = ?
              AND times_seen >= 3
              AND CAST(times_correct AS REAL) / times_seen >= 0.75
              AND difficulty_score <= 35
            """,
            (student_id,),
        ).fetchone()["cnt"]
        difficult_count = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM word_performance
            WHERE student_id = ? AND times_seen >= 1 AND difficulty_score >= 60
            """,
            (student_id,),
        ).fetchone()["cnt"]
    return {
        "practiced_words": int(row["practiced_words"]),
        "avg_difficulty": round(float(row["avg_difficulty"]), 1),
        "total_seen": int(row["total_seen"]),
        "total_correct": int(row["total_correct"]),
        "total_wrong": int(row["total_wrong"]),
        "strong_words": int(strong_count),
        "difficult_words": int(difficult_count),
    }


def record_session(student_id: int, lesson: int, section: str, score: int, total: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (student_id, lesson, section, score, total, completed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                lesson,
                section,
                score,
                total,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def get_summary_stats(student_id: int) -> dict[str, int]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total_answers,
                COALESCE(SUM(is_correct), 0) AS correct_answers,
                COALESCE(SUM(CASE WHEN is_correct = 0 THEN 1 ELSE 0 END), 0) AS incorrect_answers
            FROM answers
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
    return {
        "total_answers": int(row["total_answers"]),
        "correct_answers": int(row["correct_answers"]),
        "incorrect_answers": int(row["incorrect_answers"]),
    }


def get_lesson_stats(student_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                lesson,
                COUNT(*) AS total_answers,
                COALESCE(SUM(is_correct), 0) AS correct_answers
            FROM answers
            WHERE student_id = ?
            GROUP BY lesson
            ORDER BY lesson
            """,
            (student_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_recent_sessions(student_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT lesson, section, score, total, completed_at
            FROM sessions
            WHERE student_id = ?
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_word_stats(student_id: int) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                english_word,
                COUNT(*) AS attempts,
                COALESCE(SUM(is_correct), 0) AS correct_count
            FROM answers
            WHERE student_id = ?
            GROUP BY english_word
            ORDER BY attempts DESC, english_word
            """,
            (student_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_state(student_id: int, key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_state WHERE student_id = ? AND key = ?",
            (student_id, key),
        ).fetchone()
    return row["value"] if row else default


def set_state(student_id: int, key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO app_state (student_id, key, value) VALUES (?, ?, ?)
            ON CONFLICT(student_id, key) DO UPDATE SET value = excluded.value
            """,
            (student_id, key, value),
        )


def reset_progress(student_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM answers WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM sessions WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM app_state WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM word_performance WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM daily_sessions WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM student_stories WHERE student_id = ?", (student_id,))


def today_str() -> str:
    return date.today().isoformat()


def get_daily_session(student_id: int, session_date: str | None = None) -> dict[str, Any] | None:
    day = session_date or today_str()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, student_id, session_date, words_json, completed, score, total, completed_at
            FROM daily_sessions
            WHERE student_id = ? AND session_date = ?
            """,
            (student_id, day),
        ).fetchone()
    return dict(row) if row else None


def save_daily_session_plan(student_id: int, plan: dict[str, Any], session_date: str | None = None) -> None:
    day = session_date or today_str()
    payload = json.dumps(plan, ensure_ascii=False)
    existing = get_daily_session(student_id, day)
    with get_connection() as conn:
        if existing:
            if existing.get("completed"):
                return
            conn.execute(
                """
                UPDATE daily_sessions SET words_json = ?
                WHERE student_id = ? AND session_date = ?
                """,
                (payload, student_id, day),
            )
        else:
            conn.execute(
                """
                INSERT INTO daily_sessions (student_id, session_date, words_json, completed)
                VALUES (?, ?, ?, 0)
                """,
                (student_id, day, payload),
            )


def complete_daily_session(
    student_id: int,
    score: int,
    total: int,
    session_date: str | None = None,
) -> None:
    day = session_date or today_str()
    now = datetime.now().isoformat(timespec="seconds")
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE daily_sessions
            SET completed = 1, score = ?, total = ?, completed_at = ?
            WHERE student_id = ? AND session_date = ?
            """,
            (score, total, now, student_id, day),
        )
        conn.execute(
            """
            INSERT INTO sessions (student_id, lesson, section, score, total, completed_at)
            VALUES (?, 0, 'daily', ?, ?, ?)
            """,
            (student_id, score, total, now),
        )


def is_daily_completed(student_id: int, session_date: str | None = None) -> bool:
    row = get_daily_session(student_id, session_date)
    return bool(row and row.get("completed"))


def get_review_word_candidates(student_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM word_performance
            WHERE student_id = ?
              AND times_seen >= 2
              AND CAST(times_correct AS REAL) / times_seen >= 0.6
            ORDER BY difficulty_score ASC, last_seen ASC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def save_student_story(
    student_id: int,
    story_type: str,
    title: str,
    story_en: str,
    story_he: str,
    words: list[Any],
    score: int,
    total: int,
    story_date: str | None = None,
) -> int:
    day = story_date or today_str()
    now = datetime.now().isoformat(timespec="seconds")
    words_payload = json.dumps(words, ensure_ascii=False)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO student_stories (
                student_id, story_type, story_date, title,
                story_en, story_he, words_json, score, total, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                story_type,
                day,
                title,
                story_en,
                story_he,
                words_payload,
                score,
                total,
                now,
            ),
        )
        return int(cursor.lastrowid)


def get_student_stories(student_id: int, limit: int = 30) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, student_id, story_type, story_date, title,
                   story_en, story_he, words_json, score, total, completed_at
            FROM student_stories
            WHERE student_id = ?
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (student_id, limit),
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["words"] = json.loads(item.pop("words_json"))
        results.append(item)
    return results


def get_story_word_usage(student_id: int, limit: int = 40) -> dict[str, int]:
    usage: dict[str, int] = {}
    for story in get_student_stories(student_id, limit=limit):
        for word in story.get("words", []):
            if isinstance(word, dict):
                key = _normalize_word(str(word.get("english", "")))
            else:
                key = _normalize_word(str(word))
            if key:
                usage[key] = usage.get(key, 0) + 1
    return usage


# ---------------------------------------------------------------------------
# Teacher words (shared across students)
# ---------------------------------------------------------------------------


def add_teacher_word(
    lesson: int,
    lesson_name: str,
    english: str,
    hebrew: str,
    example_en: str,
    priority: str = "normal",
    example_he: str = "",
    test_date: str | None = None,
) -> None:
    if priority not in PRIORITY_ORDER:
        priority = "normal"
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO teacher_words (
                lesson, lesson_name, english, hebrew, example_en, example_he,
                priority, test_date, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson,
                lesson_name.strip(),
                english.strip(),
                hebrew.strip(),
                example_en.strip(),
                example_he.strip(),
                priority,
                test_date,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def get_teacher_words() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id, lesson, lesson_name, english, hebrew, example_en, example_he,
                priority, test_date, created_at
            FROM teacher_words
            ORDER BY
                CASE priority
                    WHEN 'test' THEN 0
                    WHEN 'high' THEN 1
                    ELSE 2
                END,
                created_at DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def delete_teacher_word(word_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM teacher_words WHERE id = ?", (word_id,))
