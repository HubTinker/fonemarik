import sqlite3
from pathlib import Path

DB_FILE = "dictionary.db"


def initialize_database(conn=None):
    """
    Инициализирует базу данных SQLite и создает таблицу для словаря.
    Если conn передан, использует его, иначе создает новое соединение.
    """
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_FILE)
        close_conn = True

    cursor = conn.cursor()

    # Удаляем таблицу, если она существует, для чистоты тестов
    cursor.execute("DROP TABLE IF EXISTS dictionary")

    # Создаем таблицу
    cursor.execute(
        """
    CREATE TABLE dictionary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL UNIQUE,
        part_of_speech TEXT,
        syllable_count INTEGER,
        stress_position INTEGER,
        transcription_ipa TEXT,
        transcription_cyrillic TEXT,
        stress_sound TEXT,
        phonemes_list TEXT,
        phoneme_to_letter_map TEXT,
        frequency REAL
    )
    """
    )

    print("Таблица 'dictionary' создана с колонкой phoneme_to_letter_map.")

    conn.commit()
    if close_conn:
        conn.close()
    print(f"База данных '{DB_FILE}' успешно инициализирована.")


if __name__ == "__main__":
    initialize_database()
