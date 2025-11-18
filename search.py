# -*- coding: utf-8 -*-

"""
Модуль для поиска слов в базе данных по фонологическим и другим критериям.
Это центральный модуль бизнес-логики.
"""

import sqlite3
import re
from typing import List, Dict, Any, Optional

from query_parser import parse_query_to_regex

DB_FILE = "dictionary.db"

def find_words(
    query: str,
    syllable_count: Optional[int] = None,
    part_of_speech: Optional[str] = None,
    position: str = "any",  # 'any', 'start', 'end'
    search_in: str = "phonemes",  # 'phonemes' or 'word'
    sort_by_frequency: bool = False,
    exclude_sounds: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Ищет слова в базе данных по заданным критериям.

    Args:
        query: Пользовательский запрос (фонемный или текстовый).
        syllable_count: Фильтр по количеству слогов.
        part_of_speech: Фильтр по части речи.
        position: Позиция шаблона в слове ('any', 'start', 'end').
        search_in: Область поиска ('phonemes' для транскрипции, 'word' для слова).
        sort_by_frequency: Если True, сортирует результаты по убыванию частотности.
        exclude_sounds: Строка со звуками для исключения, разделенными запятой.

    Returns:
        Список словарей, где каждый словарь представляет найденное слово.
    """
    if search_in == "phonemes":
        regex_str = parse_query_to_regex(query)
    else:
        # Для поиска по слову используем запрос как есть
        regex_str = query
        
    if not regex_str:
        return []
    # Адаптация регулярного выражения в зависимости от позиции
    if position == "start":
        regex_str = f"^{regex_str}"
    elif position == "end":
        regex_str = f"{regex_str}$"
    # Для 'any' оставляем как есть

    try:
        search_regex = re.compile(regex_str, re.IGNORECASE)
    except re.error:
        # В случае ошибки в регулярном выражении возвращаем пустой список
        return []

    conn = sqlite3.connect(DB_FILE)
    # Использование Row для доступа к колонкам по имени
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- Шаг 1: Базовый SQL-запрос для фильтрации ---
    # Мы будем фильтровать по SQL там, где это эффективно (слоги, часть речи),
    # а по регулярному выражению - в Python, т.к. SQLite не имеет встроенной
    # поддержки REGEXP для кириллицы по умолчанию.

    sql_query = "SELECT * FROM dictionary WHERE 1=1"
    params = []

    if syllable_count is not None:
        sql_query += " AND syllable_count = ?"
        params.append(syllable_count)

    if part_of_speech is not None and part_of_speech != "Любая":
        sql_query += " AND part_of_speech = ?"
        params.append(part_of_speech)

    # Добавляем сортировку
    if sort_by_frequency:
        sql_query += " ORDER BY frequency DESC"
    else:
        sql_query += " ORDER BY word ASC" # Сортировка по алфавиту по умолчанию

    cursor.execute(sql_query, params)
    all_candidates = cursor.fetchall()
    conn.close()

    # --- Шаг 2: Фильтрация по регулярному выражению в Python ---
    found_words = []
    search_field = "phonemes_list" if search_in == "phonemes" else "word"
    
    # --- Шаг 3: Фильтрация по исключенным звукам ---
    sounds_to_exclude = []
    if exclude_sounds:
        # Разделяем строку по запятым и убираем лишние пробелы
        sounds_to_exclude = [s.strip() for s in exclude_sounds.split(',') if s.strip()]

    final_results = []
    for row in all_candidates:
        target_text = row[search_field]
        if not (target_text and search_regex.search(target_text)):
            continue

        # Проверяем, содержит ли транскрипция какой-либо из исключаемых звуков
        if sounds_to_exclude:
            phonemes = row["phonemes_list"]
            if phonemes and any(excluded in phonemes for excluded in sounds_to_exclude):
                continue
        
        final_results.append(dict(row))

    return final_results


if __name__ == "__main__":
    # Пример использования и тестирования
    
    # 1. Поиск "м" + любой гласный + "р" в фонемах
    test_query_1 = "м[гласн]р"
    results_1 = find_words(query=test_query_1, search_in="phonemes", sort_by_frequency=True)
    print(f"Результаты для фонемного запроса '{test_query_1}':")
    for word_data in results_1[:5]:
        print(f"  - {word_data['word']} ({word_data['phonemes_list']})")
    print("-" * 20)

    # 2. Поиск слов, начинающихся на "абв" в написании
    test_query_2 = "абв"
    results_2 = find_words(query=test_query_2, position="start", search_in="word")
    print(f"Результаты для поиска по слову, начинающемуся на '{test_query_2}':")
    for word_data in results_2[:5]:
        print(f"  - {word_data['word']}")
    print("-" * 20)
    
    # 3. Поиск существительных (тег 's'), оканчивающихся на фонему "к"
    test_query_3 = "к"
    results_3 = find_words(query=test_query_3, part_of_speech="s", position="end", search_in="phonemes")
    print(f"Результаты для существительных, оканчивающихся на фонему 'к':")
    for word_data in results_3[:5]:
        print(f"  - {word_data['word']} ({word_data['phonemes_list']})")
    print("-" * 20)