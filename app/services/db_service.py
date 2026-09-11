import sqlite3
import json
import os

from app.config import Config
from app.services.key_service import encrypt_api_key, key_last4


def get_db_connection():
    """
    Create and return a SQLite database connection.
    Row factory allows rows to be accessed like dictionaries.
    """
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================
# USER API CONFIGURATION MIGRATION
# ============================================================

def migrate_user_api_config(conn):
    """
    Safely create or migrate the user_api_config table.

    OLD DATABASE SCHEMA:
        user_id
        api_key
        model
        updated_at

    NEW DATABASE SCHEMA:
        user_id
        encrypted_api_key
        api_key_last4
        api_key_enabled
        model
        updated_at

    Existing users are preserved.

    Existing plaintext API keys are encrypted during migration.
    """

    cursor = conn.cursor()

    # --------------------------------------------------------
    # Check whether user_api_config table exists
    # --------------------------------------------------------

    table_exists = cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name = 'user_api_config'
    """).fetchone()

    # --------------------------------------------------------
    # CASE 1:
    # Table does not exist.
    # Create the new table.
    # --------------------------------------------------------

    if not table_exists:

        cursor.execute("""
        CREATE TABLE user_api_config (
            user_id TEXT PRIMARY KEY,
            encrypted_api_key TEXT,
            api_key_last4 TEXT,
            api_key_enabled INTEGER NOT NULL DEFAULT 0,
            model TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """)

        return

    # --------------------------------------------------------
    # Get existing columns
    # --------------------------------------------------------

    columns = [
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(user_api_config)"
        ).fetchall()
    ]

    # --------------------------------------------------------
    # CASE 2:
    # Already using new schema.
    # Nothing needs to be migrated.
    # --------------------------------------------------------

    if "encrypted_api_key" in columns:
        return

    # --------------------------------------------------------
    # CASE 3:
    # Old schema contains plaintext api_key.
    # Migrate it safely.
    # --------------------------------------------------------

    if "api_key" in columns:

        encryption_secret = os.getenv(
            "USER_KEY_ENCRYPTION_SECRET"
        )

        if not encryption_secret:
            raise RuntimeError(
                "USER_KEY_ENCRYPTION_SECRET is not configured. "
                "Existing user API keys cannot be migrated safely."
            )

        # Read existing records before replacing the table.
        old_rows = cursor.execute("""
            SELECT user_id, api_key, model, updated_at
            FROM user_api_config
        """).fetchall()

        # ----------------------------------------------------
        # Create temporary new table
        # ----------------------------------------------------

        cursor.execute("""
        CREATE TABLE user_api_config_new (
            user_id TEXT PRIMARY KEY,
            encrypted_api_key TEXT,
            api_key_last4 TEXT,
            api_key_enabled INTEGER NOT NULL DEFAULT 0,
            model TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """)

        # ----------------------------------------------------
        # Migrate each existing user
        # ----------------------------------------------------

        for row in old_rows:

            user_id = row["user_id"]
            plaintext_key = row["api_key"] or ""
            model = row["model"]
            updated_at = row["updated_at"]

            if plaintext_key:

                # Encrypt the existing personal API key.
                encrypted_key = encrypt_api_key(
                    plaintext_key
                )

                # Store only the last 4 characters for display.
                last4 = key_last4(
                    plaintext_key
                )

                enabled = 1

            else:

                encrypted_key = None
                last4 = ""
                enabled = 0

            cursor.execute("""
            INSERT INTO user_api_config_new
            (
                user_id,
                encrypted_api_key,
                api_key_last4,
                api_key_enabled,
                model,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                encrypted_key,
                last4,
                enabled,
                model,
                updated_at
            ))

        # ----------------------------------------------------
        # Replace old table with new table
        # ----------------------------------------------------

        cursor.execute("""
            DROP TABLE user_api_config
        """)

        cursor.execute("""
            ALTER TABLE user_api_config_new
            RENAME TO user_api_config
        """)

        return

    # --------------------------------------------------------
    # Unexpected database schema
    # --------------------------------------------------------

    raise RuntimeError(
        "Unsupported user_api_config database schema. "
        "Expected either 'api_key' or 'encrypted_api_key'."
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = get_db_connection()
    cursor = conn.cursor()

    # --------------------------------------------------------
    # 1. Users Table
    # --------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --------------------------------------------------------
    # 2. Sessions Table
    # --------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        title TEXT NOT NULL,
        is_pinned BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    )
    """)

    # --------------------------------------------------------
    # 3. Messages Table
    # --------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        sender TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id)
            REFERENCES sessions(id)
            ON DELETE CASCADE
    )
    """)

    # --------------------------------------------------------
    # 4. Subjects Table
    # --------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        semester INTEGER NOT NULL,
        description TEXT,
        syllabus TEXT
    )
    """)

    # --------------------------------------------------------
    # 5. User Progress
    # --------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        subject_code TEXT NOT NULL,
        progress_percentage INTEGER DEFAULT 0,
        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id)
            REFERENCES users(id)
            ON DELETE CASCADE
    )
    """)

    # --------------------------------------------------------
    # 6. Generated Notes / Questions Cache
    # --------------------------------------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS generated_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_code TEXT NOT NULL,
        note_type TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # --------------------------------------------------------
    # 7. User API Configuration
    #
    # Create the new schema or migrate the old schema.
    # --------------------------------------------------------

    migrate_user_api_config(conn)

    # --------------------------------------------------------
    # Backward compatibility for Sessions table
    # --------------------------------------------------------

    try:
        cursor.execute("""
            ALTER TABLE sessions
            ADD COLUMN user_id TEXT
            REFERENCES users(id)
            ON DELETE CASCADE
        """)
    except sqlite3.OperationalError:
        # Column already exists.
        pass

    try:
        cursor.execute("""
            ALTER TABLE sessions
            ADD COLUMN is_pinned BOOLEAN DEFAULT 0
        """)
    except sqlite3.OperationalError:
        # Column already exists.
        pass

    # --------------------------------------------------------
    # Indexes
    # --------------------------------------------------------

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_sessions_user_id
        ON sessions(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_messages_session_id
        ON messages(session_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_progress_user
        ON user_progress(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_notes_subject
        ON generated_notes(subject_code, note_type)
    """)

    # Commit database structure changes.
    conn.commit()

    # --------------------------------------------------------
    # Seed Subjects
    #
    # Only seed if there are no subjects.
    #
    # IMPORTANT:
    # We do NOT delete existing subjects every time the
    # application starts.
    # --------------------------------------------------------

    subject_count = cursor.execute("""
        SELECT COUNT(*) AS count
        FROM subjects
    """).fetchone()["count"]

    if subject_count == 0:
        seed_subjects(conn)

    conn.close()


# ============================================================
# SEED MCA SUBJECTS
# ============================================================

def seed_subjects(conn):

    subjects_data = [

        # ====================================================
        # SEMESTER 1
        # ====================================================

        {
            "code": "MCA-101",
            "name": "Programming in C",
            "semester": 1,
            "description":
                "Foundational programming concepts using the C language.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Data Types",
                        "Control Structures",
                        "Functions",
                        "Pointers",
                        "File I/O"
                    ]
                }
            ]
        },

        {
            "code": "MCA-102",
            "name": "Mathematics",
            "semester": 1,
            "description":
                "Discrete math and foundations for computing.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Set Theory",
                        "Graph Theory",
                        "Logic",
                        "Combinatorics"
                    ]
                }
            ]
        },

        {
            "code": "MCA-103",
            "name": "Digital Computer Organization",
            "semester": 1,
            "description":
                "Hardware organization, logic gates, and architecture.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Logic Gates",
                        "K-Maps",
                        "Registers",
                        "Memory Hierarchy"
                    ]
                }
            ]
        },

        {
            "code": "MCA-104",
            "name": "Database Concepts",
            "semester": 1,
            "description":
                "Fundamentals of databases and ER modeling.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "DBMS Architecture",
                        "ER Models",
                        "Relational Algebra",
                        "SQL Basics"
                    ]
                }
            ]
        },

        {
            "code": "MCA-105",
            "name": "Communication Skills",
            "semester": 1,
            "description":
                "Professional communication and soft skills.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Verbal Communication",
                        "Writing Skills",
                        "Presentations"
                    ]
                }
            ]
        },

        # ====================================================
        # SEMESTER 2
        # ====================================================

        {
            "code": "MCA-201",
            "name": "Data Structures",
            "semester": 2,
            "description":
                "Design and analysis of basic data structures.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Arrays",
                        "Linked Lists",
                        "Stacks & Queues",
                        "Trees",
                        "Graphs"
                    ]
                }
            ]
        },

        {
            "code": "MCA-202",
            "name": "Java Programming",
            "semester": 2,
            "description":
                "Object-oriented programming using Java.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "OOP Concepts",
                        "Inheritance",
                        "Multithreading",
                        "Exception Handling"
                    ]
                }
            ]
        },

        {
            "code": "MCA-203",
            "name": "Operating Systems",
            "semester": 2,
            "description":
                "Core operating system concepts and process management.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Process Management",
                        "Deadlocks",
                        "Memory Management",
                        "File Systems"
                    ]
                }
            ]
        },

        {
            "code": "MCA-204",
            "name": "DBMS",
            "semester": 2,
            "description":
                "Advanced database management, normalization, and transactions.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Normalization",
                        "Transactions",
                        "Concurrency Control",
                        "SQL Tuning"
                    ]
                }
            ]
        },

        {
            "code": "MCA-205",
            "name": "Computer Networks",
            "semester": 2,
            "description":
                "Networking models, layers, and protocols.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "OSI Model",
                        "TCP/IP",
                        "Routing",
                        "Application Layer"
                    ]
                }
            ]
        },

        # ====================================================
        # SEMESTER 3
        # ====================================================

        {
            "code": "MCA-301",
            "name": "Python Programming",
            "semester": 3,
            "description":
                "Advanced Python for software and web development.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Python Basics",
                        "OOP in Python",
                        "Data Science libraries",
                        "Web APIs"
                    ]
                }
            ]
        },

        {
            "code": "MCA-302",
            "name": "Software Engineering",
            "semester": 3,
            "description":
                "Software development life cycles and methodologies.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "SDLC",
                        "Agile",
                        "UML",
                        "Testing & Maintenance"
                    ]
                }
            ]
        },

        {
            "code": "MCA-303",
            "name": "Machine Learning",
            "semester": 3,
            "description":
                "Fundamentals of supervised and unsupervised learning.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Regression",
                        "Classification",
                        "Clustering",
                        "Neural Networks"
                    ]
                }
            ]
        },

        {
            "code": "MCA-304",
            "name": "Artificial Intelligence",
            "semester": 3,
            "description":
                "AI search algorithms and knowledge representation.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Search Algorithms",
                        "Logic",
                        "Expert Systems",
                        "NLP basics"
                    ]
                }
            ]
        },

        {
            "code": "MCA-305",
            "name": "Cloud Computing",
            "semester": 3,
            "description":
                "Cloud architecture, virtualization, and services.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "IaaS, PaaS, SaaS",
                        "AWS Basics",
                        "Docker",
                        "Kubernetes"
                    ]
                }
            ]
        },

        # ====================================================
        # SEMESTER 4
        # ====================================================

        {
            "code": "MCA-401",
            "name": "Major Project",
            "semester": 4,
            "description":
                "Final semester major implementation project.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Project Planning",
                        "Implementation",
                        "Testing",
                        "Deployment"
                    ]
                }
            ]
        },

        {
            "code": "MCA-402",
            "name": "Internship",
            "semester": 4,
            "description":
                "Industry experience and internship.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Industry Experience"
                    ]
                }
            ]
        },

        {
            "code": "MCA-403",
            "name": "Seminar",
            "semester": 4,
            "description":
                "Technical seminar on recent trends.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Research",
                        "Presentation"
                    ]
                }
            ]
        },

        {
            "code": "MCA-404",
            "name": "Electives",
            "semester": 4,
            "description":
                "Advanced elective subjects.",
            "syllabus": [
                {
                    "unit": "Overview",
                    "topics": [
                        "Elective Topics"
                    ]
                }
            ]
        }
    ]

    cursor = conn.cursor()

    for subject in subjects_data:

        cursor.execute("""
        INSERT OR REPLACE INTO subjects
        (
            code,
            name,
            semester,
            description,
            syllabus
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            subject["code"],
            subject["name"],
            subject["semester"],
            subject["description"],
            json.dumps(subject["syllabus"])
        ))

    conn.commit()


# ============================================================
# USERS
# ============================================================

def create_user(user_id, username, password_hash):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO users
        (
            id,
            username,
            password_hash
        )
        VALUES (?, ?, ?)
    """, (
        user_id,
        username,
        password_hash
    ))

    conn.commit()
    conn.close()


def get_user_by_username(username):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE username = ?
    """, (username,))

    row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None


# ============================================================
# SESSIONS
# ============================================================

def create_session(session_id, user_id, title):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO sessions
        (
            id,
            user_id,
            title
        )
        VALUES (?, ?, ?)
    """, (
        session_id,
        user_id,
        title
    ))

    conn.commit()
    conn.close()


def get_sessions(user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM sessions
        WHERE user_id = ?
        ORDER BY is_pinned DESC, created_at DESC
    """, (user_id,))

    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def delete_session(session_id, user_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM sessions
        WHERE id = ?
        AND user_id = ?
    """, (
        session_id,
        user_id
    ))

    conn.commit()
    conn.close()


def rename_session(session_id, user_id, new_title):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sessions
        SET title = ?
        WHERE id = ?
        AND user_id = ?
    """, (
        new_title,
        session_id,
        user_id
    ))

    conn.commit()
    conn.close()


def toggle_pin_session(session_id, user_id, is_pinned):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sessions
        SET is_pinned = ?
        WHERE id = ?
        AND user_id = ?
    """, (
        1 if is_pinned else 0,
        session_id,
        user_id
    ))

    conn.commit()
    conn.close()


# ============================================================
# MESSAGES
# ============================================================

def save_message(session_id, sender, content):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages
        (
            session_id,
            sender,
            content
        )
        VALUES (?, ?, ?)
    """, (
        session_id,
        sender,
        content
    ))

    conn.commit()
    conn.close()


def get_session_messages(session_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            sender,
            content,
            timestamp
        FROM messages
        WHERE session_id = ?
        ORDER BY id ASC
    """, (session_id,))

    rows = cursor.fetchall()

    conn.close()

    return [dict(row) for row in rows]


def delete_message(message_id):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM messages
        WHERE id = ?
    """, (message_id,))

    conn.commit()
    conn.close()


# ============================================================
# SUBJECTS
# ============================================================

def get_subjects():

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM subjects
        ORDER BY semester ASC, code ASC
    """)

    rows = cursor.fetchall()

    conn.close()

    subjects = []

    for row in rows:

        subject = dict(row)

        if subject.get("syllabus"):
            subject["syllabus"] = json.loads(
                subject["syllabus"]
            )
        else:
            subject["syllabus"] = []

        subjects.append(subject)

    return subjects


def get_subject_by_code(code):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM subjects
        WHERE code = ?
    """, (code,))

    row = cursor.fetchone()

    conn.close()

    if row:

        subject = dict(row)

        if subject.get("syllabus"):
            subject["syllabus"] = json.loads(
                subject["syllabus"]
            )
        else:
            subject["syllabus"] = []

        return subject

    return None


# ============================================================
# GENERATED NOTES / QUESTIONS CACHE
# ============================================================

def get_generated_note(subject_code, note_type):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT content
        FROM generated_notes
        WHERE subject_code = ?
        AND note_type = ?
    """, (
        subject_code,
        note_type
    ))

    row = cursor.fetchone()

    conn.close()

    return row["content"] if row else None


def save_generated_note(subject_code, note_type, content):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO generated_notes
        (
            subject_code,
            note_type,
            content
        )
        VALUES (?, ?, ?)
    """, (
        subject_code,
        note_type,
        content
    ))

    conn.commit()
    conn.close()
