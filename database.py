"""Работа с базой данных SQLite."""
import sqlite3
import os
from typing import Optional, List, Tuple

DB_PATH = os.getenv("DB_PATH", "secret_santa.db")


class Database:
    """Класс для работы с базой данных."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        """Получить соединение с базой данных."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Инициализировать базу данных и создать таблицы."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица участников
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL,
                wish TEXT NOT NULL,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Таблица распределений
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                giver_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (giver_id) REFERENCES participants(user_id),
                FOREIGN KEY (receiver_id) REFERENCES participants(user_id)
            )
        """)
        
        # Флаг завершения распределения
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def is_registered(self, user_id: int) -> bool:
        """Проверить, зарегистрирован ли пользователь."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM participants WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    
    def register_participant(self, user_id: int, username: str, full_name: str, wish: str) -> bool:
        """Зарегистрировать или обновить данные участника."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.is_registered(user_id):
            # Обновить существующего участника
            cursor.execute("""
                UPDATE participants 
                SET username = ?, full_name = ?, wish = ?
                WHERE user_id = ?
            """, (username, full_name, wish, user_id))
        else:
            # Добавить нового участника
            cursor.execute("""
                INSERT INTO participants (user_id, username, full_name, wish)
                VALUES (?, ?, ?, ?)
            """, (user_id, username, full_name, wish))
        
        conn.commit()
        conn.close()
        return True
    
    def get_participant(self, user_id: int) -> Optional[dict]:
        """Получить данные участника."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM participants WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_participants(self) -> List[dict]:
        """Получить список всех участников."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM participants ORDER BY registered_at")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def get_participant_count(self) -> int:
        """Получить количество участников."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM participants")
        result = cursor.fetchone()
        conn.close()
        return result["count"] if result else 0
    
    def is_assignment_done(self) -> bool:
        """Проверить, выполнено ли распределение."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'assignment_done'")
        result = cursor.fetchone()
        conn.close()
        return result is not None and result["value"] == "1"
    
    def mark_assignment_done(self):
        """Пометить распределение как выполненное."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES ('assignment_done', '1')
        """)
        conn.commit()
        conn.close()
    
    def clear_assignments(self):
        """Очистить все распределения."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM assignments")
        conn.commit()
        conn.close()
    
    def save_assignments(self, assignments: List[Tuple[int, int]]):
        """Сохранить распределения."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Очистить старые распределения
        self.clear_assignments()
        
        # Сохранить новые
        cursor.executemany("""
            INSERT INTO assignments (giver_id, receiver_id)
            VALUES (?, ?)
        """, assignments)
        
        conn.commit()
        conn.close()
    
    def get_assignment(self, giver_id: int) -> Optional[dict]:
        """Получить назначение для дарителя."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.* FROM participants p
            JOIN assignments a ON p.user_id = a.receiver_id
            WHERE a.giver_id = ?
        """, (giver_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None

