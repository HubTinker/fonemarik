# -*- coding: utf-8 -*-

"""
Модуль для обновления словаря в базе данных из внешних файлов.
Отвечает за парсинг, валидацию и неразрушающее добавление/обновление данных.
"""

import json
import csv
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterator

# Импортируем новую функцию из database.py
from database import add_or_update_words, DB_FILE

# Нам также понадобятся функции для обработки фонем
from text_utils import text_to_phonemes


def _validate_and_prepare_data(
    words_iterator: Iterator[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Валидирует и подготавливает данные о словах к вставке в БД.
    Проверяет наличие 'word', вычисляет фонемы, если их нет,
    и обеспечивает наличие всех полей со значением None по умолчанию.
    """
    prepared_data = []
    # Список всех полей, чтобы обеспечить их наличие в словаре
    all_fields = [
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

    for item in words_iterator:
        if not isinstance(item, dict) or "word" not in item or not item["word"]:
            print(f"Пропущена невалидная запись: {item}")
            continue

        # Приводим все ключи к нижнему регистру для унификации
        item = {k.lower(): v for k, v in item.items()}

        # Если фонем нет, генерируем их
        if "phonemes_list" not in item:
            word = item["word"]
            # text_to_phonemes возвращает список фонем
            phonemes_list = text_to_phonemes(word)
            item["phonemes_list"] = " ".join(phonemes_list)

        # Гарантируем, что все поля существуют, чтобы избежать ошибок при вставке
        final_item = {}
        for field in all_fields:
            final_item[field] = item.get(field)

        prepared_data.append(final_item)

    return prepared_data


def _parse_json(file_path: Path) -> List[Dict[str, Any]]:
    """Парсит JSON файл, который может быть списком объектов."""
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, list):
            return _validate_and_prepare_data(iter(data))
    return []


def _parse_csv(file_path: Path) -> List[Dict[str, Any]]:
    """Парсит CSV файл. Первая строка должна содержать заголовки."""
    with file_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return _validate_and_prepare_data(iter(reader))


def update_dictionary_from_file(file_path: str, conn: sqlite3.Connection):
    """
    Главная функция, которая определяет тип файла, парсит его и обновляет БД.

    Args:
        file_path (str): Путь к файлу с данными.
        conn (sqlite3.Connection): Активное соединение с базой данных.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    words_data = []
    if path.suffix == ".json":
        words_data = _parse_json(path)
    elif path.suffix == ".csv":
        words_data = _parse_csv(path)
    else:
        raise ValueError(f"Неподдерживаемый формат файла: {path.suffix}")

    if not words_data:
        print("Не найдено данных для обновления.")
        return

    try:
        add_or_update_words(conn, words_data)
        print(f"Обновление из файла {file_path} успешно завершено.")
    except Exception as e:
        print(f"Не удалось обновить словарь из файла {file_path}: {e}")
        # Ошибка уже обработана и откачена в add_or_update_words,
        # здесь мы ее просто логируем.


if __name__ == "__main__":
    # Пример использования и отладки
    # Создадим тестовые файлы

    # 1. Тестовый JSON
    test_json_data = [
        {"word": "тестслово", "part_of_speech": "s", "frequency": 1.23},
        {
            "word": "обновление",
            "part_of_speech": "s",
            "frequency": 99.0,
        },  # Это слово может уже быть в БД
        {"word": "новоеслово"},
    ]
    json_path = Path("test_update.json")
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(test_json_data, f, ensure_ascii=False, indent=2)

    # 2. Тестовый CSV
    test_csv_data = [
        ["word", "part_of_speech", "frequency"],
        ["тестcsv", "s", "3.21"],
        ["ещеоднослово", "v", "10.5"],
    ]
    csv_path = Path("test_update.csv")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(test_csv_data)

    # Запуск обновления
    conn = sqlite3.connect(DB_FILE)
    try:
        print("--- Тестирование обновления из JSON ---")
        update_dictionary_from_file(str(json_path), conn)

        print("\n--- Тестирование обновления из CSV ---")
        update_dictionary_from_file(str(csv_path), conn)

    finally:
        conn.close()
        # json_path.unlink() # Удаляем временные файлы
        # csv_path.unlink()
        print("\nОтладочный запуск завершен.")
