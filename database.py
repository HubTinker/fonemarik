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

    # Создание таблиц для тренировочных коллекций
    cursor.execute(
        """
    -- Таблица для названий коллекций
    CREATE TABLE IF NOT EXISTS training_collections (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    )
    print("Таблица 'training_collections' создана.")

    cursor.execute(
        """
    -- Таблица для слов внутри коллекций
    CREATE TABLE IF NOT EXISTS training_collection_items (
        id INTEGER PRIMARY KEY,
        collection_id INTEGER NOT NULL,
        word_id INTEGER, -- Может быть NULL, если слово не из основного словаря
        word TEXT NOT NULL, -- Текст слова, для случаев, когда word_id не указан
        normalized_word TEXT,
        example_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (collection_id) REFERENCES training_collections(id) ON DELETE CASCADE
    );
    """
    )
    print("Таблица 'training_collection_items' создана.")

    # Добавление индексов
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_collection_id ON training_collection_items (collection_id);"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_word_id ON training_collection_items (word_id);"
    )
    print("Индексы для тренировочных таблиц созданы.")

    conn.commit()
    if close_conn:
        conn.close()
    print(f"База данных '{DB_FILE}' успешно инициализирована.")


def create_tables_if_not_exist():
    """
    Создает все необходимые таблицы в базе данных, если они еще не существуют.
    Эта функция безопасна для вызова при каждом запуске приложения.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Основная таблица словаря
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
            phoneme_to_letter_map TEXT,
            frequency REAL
        )
        """
        )
        # Таблицы для тренировочных коллекций
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS training_collections (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        )
        cursor.execute(
            """
        CREATE TABLE IF NOT EXISTS training_collection_items (
            id INTEGER PRIMARY KEY,
            collection_id INTEGER NOT NULL,
            word_id INTEGER,
            word TEXT NOT NULL,
            normalized_word TEXT,
            example_text TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (collection_id) REFERENCES training_collections(id) ON DELETE CASCADE
        );
        """
        )
        # Индексы
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_collection_id ON training_collection_items (collection_id);"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_word_id ON training_collection_items (word_id);"
        )
        conn.commit()


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


def get_db_connection():
    """Возвращает соединение с базой данных."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# --- Функции для управления коллекциями ---


def create_collection(title: str):
    """Создает новую тренировочную коллекцию."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO training_collections (title) VALUES (?)", (title,)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            print(f"Коллекция с названием '{title}' уже существует.")


def get_all_collections() -> List[sqlite3.Row]:
    """Возвращает список всех коллекций."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, created_at FROM training_collections ORDER BY created_at DESC"
        )
        return cursor.fetchall()


def add_words_to_collection(collection_id: int, words: List[str]):
    """Добавляет список слов в указанную коллекцию."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Сначала ищем word_id для существующих слов
        placeholders = ",".join("?" for _ in words)
        cursor.execute(
            f"SELECT id, word FROM dictionary WHERE word IN ({placeholders})", words
        )
        found_words = {row["word"]: row["id"] for row in cursor.fetchall()}

        data_to_insert = []
        for word in words:
            word_id = found_words.get(word)
            # Добавляем слово, даже если его нет в основном словаре
            data_to_insert.append((collection_id, word_id, word, word.lower()))

        cursor.executemany(
            "INSERT INTO training_collection_items (collection_id, word_id, word, normalized_word) VALUES (?, ?, ?, ?)",
            data_to_insert,
        )
        conn.commit()


def get_words_in_collection(collection_id: int) -> List[sqlite3.Row]:
    """Возвращает все слова из указанной коллекции."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, word FROM training_collection_items WHERE collection_id = ? ORDER BY created_at",
            (collection_id,),
        )
        return cursor.fetchall()


def delete_word_from_collection(item_id: int):
    """Удаляет слово из коллекции по его ID в training_collection_items."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM training_collection_items WHERE id = ?", (item_id,))
        conn.commit()


def delete_collection(collection_id: int):
    """Удаляет коллекцию и все связанные с ней слова."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # ON DELETE CASCADE должен сработать автоматически
        cursor.execute(
            "DELETE FROM training_collections WHERE id = ?", (collection_id,)
        )
        conn.commit()


if __name__ == "__main__":
    initialize_database()
