import sqlite3
from pathlib import Path
from typing import List, Dict, Any

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


def add_or_update_words(conn: sqlite3.Connection, words_data: List[Dict[str, Any]]):
    """
    Пакетное добавление или обновление слов в базе данных.
    Использует 'INSERT ... ON CONFLICT(word) DO UPDATE' для атомарности.

    Args:
        conn: Соединение с базой данных.
        words_data: Список словарей, где каждый словарь представляет слово.
    """
    cursor = conn.cursor()

    # Список всех возможных полей в таблице
    fields = [
        "word",
        "part_of_speech",
        "syllable_count",
        "stress_position",
        "transcription_ipa",
        "transcription_cyrillic",
        "stress_sound",
        "phonemes_list",
        "phoneme_to_letter_map",
        "frequency",
    ]

    # Подготовка запроса
    # Мы используем 'INSERT ... ON CONFLICT' для выполнения 'UPSERT'
    sql = f"""
    INSERT INTO dictionary ({', '.join(fields)})
    VALUES ({', '.join(':' + f for f in fields)})
    ON CONFLICT(word) DO UPDATE SET
        part_of_speech = excluded.part_of_speech,
        syllable_count = excluded.syllable_count,
        stress_position = excluded.stress_position,
        transcription_ipa = excluded.transcription_ipa,
        transcription_cyrillic = excluded.transcription_cyrillic,
        stress_sound = excluded.stress_sound,
        phonemes_list = excluded.phonemes_list,
        phoneme_to_letter_map = excluded.phoneme_to_letter_map,
        frequency = excluded.frequency;
    """

    try:
        # executemany для пакетной вставки/обновления
        cursor.executemany(sql, words_data)
        conn.commit()
        print(f"Успешно добавлено/обновлено {len(words_data)} слов.")
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Ошибка при обновлении базы данных: {e}")
        raise


if __name__ == "__main__":
    initialize_database()
