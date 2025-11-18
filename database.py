import sqlite3
from pathlib import Path

DB_FILE = "dictionary.db"


def initialize_database():
    """
    Инициализирует базу данных SQLite и создает таблицу для словаря.

    Таблица 'dictionary' будет содержать следующие поля:
    - id: INTEGER PRIMARY KEY AUTOINCREMENT
    - word: TEXT NOT NULL UNIQUE (слово)
    - part_of_speech: TEXT (часть речи)
    - syllable_count: INTEGER (количество слогов)
    - stress_position: INTEGER (позиция ударения, 1-based)
    - transcription_ipa: TEXT (транскрипция IPA)
    - transcription_cyrillic: TEXT (транскрипция кириллицей)
    - phonemes_list: TEXT (список фонем через пробел)
    - frequency: REAL (частота слова, ipm)
    """
    db_path = Path(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Создаем таблицу, если она не существует
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS dictionary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL UNIQUE,
        part_of_speech TEXT,
        syllable_count INTEGER,
        stress_position INTEGER,
        transcription_ipa TEXT,
        transcription_cyrillic TEXT,
        stress_sound TEXT,
        phonemes_list TEXT,
        frequency REAL
    )
    """
    )

    # Очищаем таблицу перед заполнением
    cursor.execute("DELETE FROM dictionary")
    print("Таблица 'dictionary' очищена.")

    conn.commit()
    conn.close()
    print(f"База данных '{DB_FILE}' успешно инициализирована.")


if __name__ == "__main__":
    initialize_database()
