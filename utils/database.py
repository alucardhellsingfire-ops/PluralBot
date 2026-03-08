"""
Database utility — SQLite backend for PluralCord.
All data is stored locally, per-server.
"""

import aiosqlite
import datetime
import json
from typing import Optional, List, Dict, Any


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def _create_tables(self):
        await self._conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        -- One system per Discord user per guild
        CREATE TABLE IF NOT EXISTS systems (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            guild_id        TEXT NOT NULL,
            system_name     TEXT NOT NULL DEFAULT 'My System',
            system_tag      TEXT,
            description     TEXT,
            color           TEXT DEFAULT '#7289DA',
            avatar_url      TEXT,
            privacy_default TEXT DEFAULT 'private',
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, guild_id)
        );

        -- System members (alters/headmates)
        CREATE TABLE IF NOT EXISTS members (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id       INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            name            TEXT NOT NULL,
            display_name    TEXT,
            pronouns        TEXT,
            description     TEXT,
            role            TEXT,
            color           TEXT,
            avatar_url      TEXT,
            proxy_prefix    TEXT,
            proxy_suffix    TEXT,
            birthday        TEXT,
            is_archived     INTEGER DEFAULT 0,
            is_private      INTEGER DEFAULT 0,
            extra_fields    TEXT DEFAULT '{}',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        -- Member groups/subsystems
        CREATE TABLE IF NOT EXISTS groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            description TEXT,
            color       TEXT,
            parent_id   INTEGER REFERENCES groups(id) ON DELETE SET NULL
        );

        -- Group membership
        CREATE TABLE IF NOT EXISTS group_members (
            group_id    INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            member_id   INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            PRIMARY KEY (group_id, member_id)
        );

        -- Front tracking
        CREATE TABLE IF NOT EXISTS fronts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            member_id   INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            started_at  TEXT NOT NULL DEFAULT (datetime('now')),
            ended_at    TEXT,
            note        TEXT,
            is_custom   INTEGER DEFAULT 0
        );

        -- Current front (for fast lookup)
        CREATE TABLE IF NOT EXISTS current_front (
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            member_id   INTEGER NOT NULL REFERENCES members(id) ON DELETE CASCADE,
            note        TEXT,
            since       TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (system_id, member_id)
        );

        -- Journal entries
        CREATE TABLE IF NOT EXISTS journal (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            member_id   INTEGER REFERENCES members(id) ON DELETE SET NULL,
            title       TEXT,
            content     TEXT NOT NULL,
            tags        TEXT DEFAULT '[]',
            is_private  INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );

        -- Polls
        CREATE TABLE IF NOT EXISTS polls (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            question    TEXT NOT NULL,
            options     TEXT NOT NULL DEFAULT '[]',
            votes       TEXT NOT NULL DEFAULT '{}',
            is_open     INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now')),
            closed_at   TEXT,
            message_id  TEXT
        );

        -- Notes / Reminders per member
        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            member_id   INTEGER REFERENCES members(id) ON DELETE SET NULL,
            content     TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        -- System friends (other systems this system has friended)
        CREATE TABLE IF NOT EXISTS friends (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id       INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            friend_system_id INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            status          TEXT DEFAULT 'pending',
            created_at      TEXT DEFAULT (datetime('now')),
            UNIQUE(system_id, friend_system_id)
        );

        -- Front notification channels per guild
        CREATE TABLE IF NOT EXISTS notification_channels (
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            channel_id  TEXT NOT NULL,
            guild_id    TEXT NOT NULL,
            PRIMARY KEY (system_id, guild_id)
        );

        -- Custom fields definitions
        CREATE TABLE IF NOT EXISTS custom_fields (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            system_id   INTEGER NOT NULL REFERENCES systems(id) ON DELETE CASCADE,
            field_name  TEXT NOT NULL,
            field_type  TEXT DEFAULT 'text'
        );
        """)
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # SYSTEM METHODS
    # -------------------------------------------------------------------------

    async def get_system(self, user_id: str, guild_id: str) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM systems WHERE user_id=? AND guild_id=?",
            (user_id, guild_id)
        ) as cur:
            return await cur.fetchone()

    async def get_system_by_id(self, system_id: int) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM systems WHERE id=?", (system_id,)
        ) as cur:
            return await cur.fetchone()

    async def create_system(self, user_id: str, guild_id: str, name: str) -> int:
        cur = await self._conn.execute(
            "INSERT INTO systems (user_id, guild_id, system_name) VALUES (?,?,?)",
            (user_id, guild_id, name)
        )
        await self._conn.commit()
        return cur.lastrowid

    async def update_system(self, system_id: int, **kwargs):
        if not kwargs:
            return
        fields = ', '.join(f'{k}=?' for k in kwargs)
        values = list(kwargs.values()) + [system_id]
        await self._conn.execute(f"UPDATE systems SET {fields} WHERE id=?", values)
        await self._conn.commit()

    async def delete_system(self, system_id: int):
        await self._conn.execute("DELETE FROM systems WHERE id=?", (system_id,))
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # MEMBER METHODS
    # -------------------------------------------------------------------------

    async def get_members(self, system_id: int, include_archived=False) -> List[aiosqlite.Row]:
        query = "SELECT * FROM members WHERE system_id=?"
        if not include_archived:
            query += " AND is_archived=0"
        query += " ORDER BY name COLLATE NOCASE"
        async with self._conn.execute(query, (system_id,)) as cur:
            return await cur.fetchall()

    async def get_member(self, member_id: int) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM members WHERE id=?", (member_id,)
        ) as cur:
            return await cur.fetchone()

    async def get_member_by_name(self, system_id: int, name: str) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM members WHERE system_id=? AND name LIKE ? AND is_archived=0",
            (system_id, name)
        ) as cur:
            return await cur.fetchone()

    async def search_member(self, system_id: int, query: str) -> List[aiosqlite.Row]:
        q = query.strip().lower()
        async with self._conn.execute(
            """SELECT * FROM members WHERE system_id=?
               AND (LOWER(name) LIKE ? OR LOWER(display_name) LIKE ?) AND is_archived=0
               ORDER BY name COLLATE NOCASE""",
            (system_id, f'%{q}%', f'%{q}%')
        ) as cur:
            return await cur.fetchall()

    async def create_member(self, system_id: int, name: str, **kwargs) -> int:
        fields = ['system_id', 'name'] + list(kwargs.keys())
        placeholders = ', '.join(['?'] * len(fields))
        values = [system_id, name] + list(kwargs.values())
        cur = await self._conn.execute(
            f"INSERT INTO members ({', '.join(fields)}) VALUES ({placeholders})",
            values
        )
        await self._conn.commit()
        return cur.lastrowid

    async def update_member(self, member_id: int, **kwargs):
        if not kwargs:
            return
        fields = ', '.join(f'{k}=?' for k in kwargs)
        values = list(kwargs.values()) + [member_id]
        await self._conn.execute(f"UPDATE members SET {fields} WHERE id=?", values)
        await self._conn.commit()

    async def delete_member(self, member_id: int):
        await self._conn.execute("DELETE FROM members WHERE id=?", (member_id,))
        await self._conn.commit()

    async def get_member_by_proxy(self, system_id: int, content: str):
        """Find a member whose proxy tags match the given message content."""
        async with self._conn.execute(
            "SELECT * FROM members WHERE system_id=? AND is_archived=0 AND (proxy_prefix IS NOT NULL OR proxy_suffix IS NOT NULL)",
            (system_id,)
        ) as cur:
            members = await cur.fetchall()
        for m in members:
            prefix = m['proxy_prefix'] or ''
            suffix = m['proxy_suffix'] or ''
            if prefix and suffix:
                if content.startswith(prefix) and content.endswith(suffix):
                    return m, content[len(prefix):len(content)-len(suffix)].strip()
            elif prefix:
                if content.startswith(prefix):
                    return m, content[len(prefix):].strip()
            elif suffix:
                if content.endswith(suffix):
                    return m, content[:len(content)-len(suffix)].strip()
        return None, None

    # -------------------------------------------------------------------------
    # FRONT METHODS
    # -------------------------------------------------------------------------

    async def get_current_front(self, system_id: int) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            """SELECT cf.*, m.name, m.display_name, m.color, m.avatar_url, m.pronouns
               FROM current_front cf
               JOIN members m ON m.id = cf.member_id
               WHERE cf.system_id=?""",
            (system_id,)
        ) as cur:
            return await cur.fetchall()

    async def set_front(self, system_id: int, member_id: int, note: str = None):
        await self._conn.execute(
            "INSERT OR REPLACE INTO current_front (system_id, member_id, note, since) VALUES (?,?,?,datetime('now'))",
            (system_id, member_id, note)
        )
        await self._conn.execute(
            "INSERT INTO fronts (system_id, member_id, note) VALUES (?,?,?)",
            (system_id, member_id, note)
        )
        await self._conn.commit()

    async def clear_front(self, system_id: int):
        """End all current fronts for a system."""
        await self._conn.execute(
            """UPDATE fronts SET ended_at=datetime('now')
               WHERE system_id=? AND ended_at IS NULL""",
            (system_id,)
        )
        await self._conn.execute(
            "DELETE FROM current_front WHERE system_id=?",
            (system_id,)
        )
        await self._conn.commit()

    async def remove_from_front(self, system_id: int, member_id: int):
        await self._conn.execute(
            """UPDATE fronts SET ended_at=datetime('now')
               WHERE system_id=? AND member_id=? AND ended_at IS NULL""",
            (system_id, member_id)
        )
        await self._conn.execute(
            "DELETE FROM current_front WHERE system_id=? AND member_id=?",
            (system_id, member_id)
        )
        await self._conn.commit()

    async def get_front_history(self, system_id: int, limit: int = 50) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            """SELECT f.*, m.name, m.display_name, m.color
               FROM fronts f
               JOIN members m ON m.id = f.member_id
               WHERE f.system_id=?
               ORDER BY f.started_at DESC
               LIMIT ?""",
            (system_id, limit)
        ) as cur:
            return await cur.fetchall()

    async def get_front_stats(self, system_id: int) -> List[aiosqlite.Row]:
        """Returns aggregate front time per member."""
        async with self._conn.execute(
            """SELECT m.name, m.display_name, m.color,
                      COUNT(*) as switch_count,
                      SUM(
                        CASE WHEN f.ended_at IS NOT NULL
                          THEN (julianday(f.ended_at) - julianday(f.started_at)) * 24 * 60
                          ELSE (julianday('now') - julianday(f.started_at)) * 24 * 60
                        END
                      ) as total_minutes
               FROM fronts f
               JOIN members m ON m.id = f.member_id
               WHERE f.system_id=?
               GROUP BY f.member_id
               ORDER BY total_minutes DESC""",
            (system_id,)
        ) as cur:
            return await cur.fetchall()

    # -------------------------------------------------------------------------
    # JOURNAL METHODS
    # -------------------------------------------------------------------------

    async def create_journal_entry(self, system_id: int, content: str, **kwargs) -> int:
        fields = ['system_id', 'content'] + list(kwargs.keys())
        placeholders = ', '.join(['?'] * len(fields))
        values = [system_id, content] + list(kwargs.values())
        cur = await self._conn.execute(
            f"INSERT INTO journal ({', '.join(fields)}) VALUES ({placeholders})",
            values
        )
        await self._conn.commit()
        return cur.lastrowid

    async def get_journal_entries(self, system_id: int, member_id: int = None,
                                   limit: int = 10, offset: int = 0) -> List[aiosqlite.Row]:
        if member_id:
            query = "SELECT * FROM journal WHERE system_id=? AND member_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (system_id, member_id, limit, offset)
        else:
            query = "SELECT * FROM journal WHERE system_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (system_id, limit, offset)
        async with self._conn.execute(query, params) as cur:
            return await cur.fetchall()

    async def get_journal_entry(self, entry_id: int) -> Optional[aiosqlite.Row]:
        async with self._conn.execute("SELECT * FROM journal WHERE id=?", (entry_id,)) as cur:
            return await cur.fetchone()

    async def update_journal_entry(self, entry_id: int, **kwargs):
        kwargs['updated_at'] = datetime.datetime.utcnow().isoformat()
        fields = ', '.join(f'{k}=?' for k in kwargs)
        values = list(kwargs.values()) + [entry_id]
        await self._conn.execute(f"UPDATE journal SET {fields} WHERE id=?", values)
        await self._conn.commit()

    async def delete_journal_entry(self, entry_id: int):
        await self._conn.execute("DELETE FROM journal WHERE id=?", (entry_id,))
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # POLL METHODS
    # -------------------------------------------------------------------------

    async def create_poll(self, system_id: int, question: str, options: list) -> int:
        cur = await self._conn.execute(
            "INSERT INTO polls (system_id, question, options, votes) VALUES (?,?,?,?)",
            (system_id, question, json.dumps(options), json.dumps({}))
        )
        await self._conn.commit()
        return cur.lastrowid

    async def get_poll(self, poll_id: int) -> Optional[aiosqlite.Row]:
        async with self._conn.execute("SELECT * FROM polls WHERE id=?", (poll_id,)) as cur:
            return await cur.fetchone()

    async def get_active_polls(self, system_id: int) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM polls WHERE system_id=? AND is_open=1 ORDER BY created_at DESC",
            (system_id,)
        ) as cur:
            return await cur.fetchall()

    async def vote_poll(self, poll_id: int, member_name: str, option_index: int):
        poll = await self.get_poll(poll_id)
        if not poll:
            return False
        votes = json.loads(poll['votes'])
        votes[member_name] = option_index
        await self._conn.execute(
            "UPDATE polls SET votes=? WHERE id=?",
            (json.dumps(votes), poll_id)
        )
        await self._conn.commit()
        return True

    async def close_poll(self, poll_id: int):
        await self._conn.execute(
            "UPDATE polls SET is_open=0, closed_at=datetime('now') WHERE id=?",
            (poll_id,)
        )
        await self._conn.commit()

    async def update_poll_message(self, poll_id: int, message_id: str):
        await self._conn.execute(
            "UPDATE polls SET message_id=? WHERE id=?",
            (message_id, poll_id)
        )
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # NOTES METHODS
    # -------------------------------------------------------------------------

    async def add_note(self, system_id: int, content: str, member_id: int = None) -> int:
        cur = await self._conn.execute(
            "INSERT INTO notes (system_id, member_id, content) VALUES (?,?,?)",
            (system_id, member_id, content)
        )
        await self._conn.commit()
        return cur.lastrowid

    async def get_notes(self, system_id: int, member_id: int = None) -> List[aiosqlite.Row]:
        if member_id:
            async with self._conn.execute(
                "SELECT * FROM notes WHERE system_id=? AND member_id=? ORDER BY created_at DESC",
                (system_id, member_id)
            ) as cur:
                return await cur.fetchall()
        async with self._conn.execute(
            "SELECT * FROM notes WHERE system_id=? ORDER BY created_at DESC",
            (system_id,)
        ) as cur:
            return await cur.fetchall()

    async def delete_note(self, note_id: int):
        await self._conn.execute("DELETE FROM notes WHERE id=?", (note_id,))
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # GROUPS METHODS
    # -------------------------------------------------------------------------

    async def create_group(self, system_id: int, name: str, **kwargs) -> int:
        fields = ['system_id', 'name'] + list(kwargs.keys())
        placeholders = ', '.join(['?'] * len(fields))
        values = [system_id, name] + list(kwargs.values())
        cur = await self._conn.execute(
            f"INSERT INTO groups ({', '.join(fields)}) VALUES ({placeholders})",
            values
        )
        await self._conn.commit()
        return cur.lastrowid

    async def get_groups(self, system_id: int) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM groups WHERE system_id=? ORDER BY name COLLATE NOCASE",
            (system_id,)
        ) as cur:
            return await cur.fetchall()

    async def get_group(self, group_id: int) -> Optional[aiosqlite.Row]:
        async with self._conn.execute("SELECT * FROM groups WHERE id=?", (group_id,)) as cur:
            return await cur.fetchone()

    async def get_group_by_name(self, system_id: int, name: str) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(
            "SELECT * FROM groups WHERE system_id=? AND name LIKE ?",
            (system_id, name)
        ) as cur:
            return await cur.fetchone()

    async def add_member_to_group(self, group_id: int, member_id: int):
        await self._conn.execute(
            "INSERT OR IGNORE INTO group_members (group_id, member_id) VALUES (?,?)",
            (group_id, member_id)
        )
        await self._conn.commit()

    async def remove_member_from_group(self, group_id: int, member_id: int):
        await self._conn.execute(
            "DELETE FROM group_members WHERE group_id=? AND member_id=?",
            (group_id, member_id)
        )
        await self._conn.commit()

    async def get_group_members(self, group_id: int) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            """SELECT m.* FROM members m
               JOIN group_members gm ON gm.member_id = m.id
               WHERE gm.group_id=? ORDER BY m.name COLLATE NOCASE""",
            (group_id,)
        ) as cur:
            return await cur.fetchall()

    async def delete_group(self, group_id: int):
        await self._conn.execute("DELETE FROM groups WHERE id=?", (group_id,))
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # FRIENDS METHODS
    # -------------------------------------------------------------------------

    async def send_friend_request(self, system_id: int, friend_system_id: int) -> bool:
        try:
            await self._conn.execute(
                "INSERT INTO friends (system_id, friend_system_id, status) VALUES (?,?,'pending')",
                (system_id, friend_system_id)
            )
            await self._conn.commit()
            return True
        except Exception:
            return False

    async def accept_friend_request(self, system_id: int, friend_system_id: int):
        await self._conn.execute(
            "UPDATE friends SET status='accepted' WHERE system_id=? AND friend_system_id=?",
            (friend_system_id, system_id)
        )
        await self._conn.execute(
            "INSERT OR IGNORE INTO friends (system_id, friend_system_id, status) VALUES (?,?,'accepted')",
            (system_id, friend_system_id)
        )
        await self._conn.commit()

    async def get_friends(self, system_id: int) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            """SELECT f.*, s.system_name, s.user_id, s.guild_id
               FROM friends f
               JOIN systems s ON s.id = f.friend_system_id
               WHERE f.system_id=? AND f.status='accepted'""",
            (system_id,)
        ) as cur:
            return await cur.fetchall()

    async def get_pending_requests(self, system_id: int) -> List[aiosqlite.Row]:
        async with self._conn.execute(
            """SELECT f.*, s.system_name, s.user_id
               FROM friends f
               JOIN systems s ON s.id = f.system_id
               WHERE f.friend_system_id=? AND f.status='pending'""",
            (system_id,)
        ) as cur:
            return await cur.fetchall()

    async def remove_friend(self, system_id: int, friend_system_id: int):
        await self._conn.execute(
            "DELETE FROM friends WHERE (system_id=? AND friend_system_id=?) OR (system_id=? AND friend_system_id=?)",
            (system_id, friend_system_id, friend_system_id, system_id)
        )
        await self._conn.commit()

    # -------------------------------------------------------------------------
    # NOTIFICATION METHODS
    # -------------------------------------------------------------------------

    async def set_notification_channel(self, system_id: int, channel_id: str, guild_id: str):
        await self._conn.execute(
            "INSERT OR REPLACE INTO notification_channels (system_id, channel_id, guild_id) VALUES (?,?,?)",
            (system_id, channel_id, guild_id)
        )
        await self._conn.commit()

    async def get_notification_channel(self, system_id: int, guild_id: str) -> Optional[str]:
        async with self._conn.execute(
            "SELECT channel_id FROM notification_channels WHERE system_id=? AND guild_id=?",
            (system_id, guild_id)
        ) as cur:
            row = await cur.fetchone()
            return row['channel_id'] if row else None