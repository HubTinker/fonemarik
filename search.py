# -*- coding: utf-8 -*-

"""
Модуль для поиска слов в базе данных по фонологическим и другим критериям.
Это центральный модуль бизнес-логики.
"""

import sqlite3
import re
from typing import List, Dict, Any, Optional

from dsl_parser import parse_query
from text_utils import text_to_phonemes
from phoneme_mapper import get_letter_range_for_phoneme_range
from phonology_rules import (
    HARD_CONSONANTS,
    SOFT_CONSONANTS,
    VOICED_CONSONANTS,
    VOICELESS_CONSONANTS,
)

DB_FILE = "dictionary.db"


def map_phonemes_to_letters(
    word: str, word_phonemes_str: str, match_object: re.Match
) -> Optional[tuple]:
    """
    Сопоставляет найденную последовательность фонем с оригинальными буквами в слове.

    Алгоритм: используем text_to_phonemes для генерации фонем из исходного слова,
    отслеживая, какие буквы производят каждую фонему.
    """
    if not word or not word_phonemes_str or not match_object:
        return None

    from text_utils import text_to_phonemes

    # 1. Считаем фонемы до совпадения
    phonemes_before_match = len(
        word_phonemes_str[: match_object.start()].strip().split()
    )
    num_phonemes_in_match = len(match_object.group(0).strip().split())

    # 2. Генерируем фонемы из исходного слова с отслеживанием позиций
    sounds = []
    letter_ranges_for_sounds = []  # (start_pos, end_pos, sound_index)

    i = 0
    while i < len(word):
        char = word[i]
        start_pos = i

        # Проверяем, является ли следующий символ апострофом
        if i + 1 < len(word) and word[i + 1] == "'":
            sounds.append(word[i : i + 2])
            letter_ranges_for_sounds.append((i, i + 2, len(sounds) - 1))
            i += 2
        # Мягкий знак после согласной
        elif (
            i + 1 < len(word)
            and word[i + 1] == "ь"
            and word[i].lower() in "бвгджзйклмнпрстфхцчшщ"
        ):
            sounds.append(word[i] + "'")
            letter_ranges_for_sounds.append((i, i + 2, len(sounds) - 1))
            i += 2
        # Пропускаем ь и ъ
        elif word[i] not in "ьъ":
            sounds.append(word[i])
            letter_ranges_for_sounds.append((i, i + 1, len(sounds) - 1))
            i += 1
        else:
            i += 1

    # 3. Проверяем индексы
    if phonemes_before_match >= len(
        sounds
    ) or phonemes_before_match + num_phonemes_in_match > len(sounds):
        return None

    # 4. Находим позиции звуков в исходном слове
    start_sound_idx = phonemes_before_match
    end_sound_idx = phonemes_before_match + num_phonemes_in_match - 1

    start_pos_in_word = None
    end_pos_in_word = None

    for start_pos, end_pos, sound_idx in letter_ranges_for_sounds:
        if sound_idx == start_sound_idx:
            start_pos_in_word = start_pos
        if sound_idx == end_sound_idx:
            end_pos_in_word = end_pos

    if start_pos_in_word is None or end_pos_in_word is None:
        return None

    # 5. Возвращаем результат
    try:
        substring = word[start_pos_in_word:end_pos_in_word]
    except Exception:
        return None

    return (start_pos_in_word, end_pos_in_word, substring)


def find_words(
    query: str,
    syllable_count: Optional[List[int]] = None,
    part_of_speech: Optional[str] = None,
    position: str = "any",  # 'any', 'start', 'end', or comma-separated like 'start,end'
    search_in: str = "phonemes",  # 'phonemes' or 'word'
    sort_by_frequency: bool = False,
    stress_sound: Optional[str] = None,
    phonological_hardness: Optional[str] = None,  # 'hard' or 'soft'
    phonological_voicing: Optional[str] = None,  # 'voiced' or 'voiceless'
    exclude_sounds: Optional[str] = None,
    conn: Optional[sqlite3.Connection] = None,
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
        exclude_sounds: Строка со звуками/тегами для исключения, разделенными запятой.
        stress_sound: Фильтр по ударному гласному.
        phonological_hardness: Фильтр по твердости/мягкости ('hard' или 'soft').
        phonological_voicing: Фильтр по звонкости/глухости ('voiced' или 'voiceless').
        conn: Соединение с базой данных.

    Returns:
        Список словарей, где каждый словарь представляет найденное слово.
    """
    global_conditions = []
    regex_str = ""

    if search_in == "phonemes":
        try:
            # Всегда используем унифицированный DSL-парсер
            dsl_result = parse_query(query)
            regex_str = dsl_result["sequence_regex"]
            global_conditions = dsl_result["global_conditions"]
        except ValueError as e:
            # Если парсер выдает ошибку (например, неверный синтаксис),
            # возвращаем пустой результат, чтобы избежать падения.
            print(f"Ошибка разбора запроса '{query}': {e}")
            return []
    else:
        # Для поиска по слову оставляем простое экранирование
        regex_str = re.escape(query)

    if not regex_str and not global_conditions:
        return []

    # --- Адаптация регулярного выражения в зависимости от позиции ---
    # position может быть 'any', 'start', 'end', 'middle', или 'start,end' и т.д.
    positions = {p.strip() for p in position.split(",")}

    # Если 'any' присутствует или список пуст, то позиция не важна
    if "any" in positions or not positions:
        final_regex_str = regex_str
    else:
        # Собираем части для сложного regex
        regex_parts = []
        if "start" in positions:
            regex_parts.append(f"^{regex_str}")
        if "middle" in positions:
            # Ищет не в начале и не в конце
            regex_parts.append(f".+{regex_str}.+")
        if "end" in positions:
            regex_parts.append(f"{regex_str}$")

        # Если выбрано и начало, и конец, и середина, это эквивалентно 'any'
        if {"start", "middle", "end"}.issubset(positions):
            final_regex_str = regex_str
        # Если выбрано начало и середина, то это "не в конце"
        elif {"start", "middle"}.issubset(positions):
            final_regex_str = f"(^{regex_str}|.+{regex_str}.+)"
        # Если выбрана середина и конец, то это "не в начале"
        elif {"middle", "end"}.issubset(positions):
            final_regex_str = f"(.+{regex_str}.+|{regex_str}$)"
        else:
            final_regex_str = "|".join(regex_parts)

    try:
        # Если regex пустой, но есть глобальные условия, нам не нужна компиляция
        if not final_regex_str and global_conditions:
            search_regex = None
        else:
            search_regex = re.compile(final_regex_str, re.IGNORECASE)
    except re.error:
        return []

    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_FILE)
        close_conn = True

    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    sql_query = "SELECT * FROM dictionary WHERE 1=1"
    params = []

    if syllable_count:
        placeholders = ",".join("?" for _ in syllable_count)
        sql_query += f" AND syllable_count IN ({placeholders})"
        params.extend(syllable_count)

    if part_of_speech is not None and part_of_speech != "Любая":
        sql_query += " AND part_of_speech = ?"
        params.append(part_of_speech)

    if stress_sound:
        sql_query += " AND stress_sound = ?"
        params.append(stress_sound)

    if sort_by_frequency:
        sql_query += " ORDER BY frequency DESC"
    else:
        sql_query += " ORDER BY word ASC"

    cursor.execute(sql_query, params)
    all_candidates = cursor.fetchall()
    if close_conn:
        conn.close()

    found_words = []
    search_field = "phonemes_list" if search_in == "phonemes" else "word"

    final_results = []
    for row in all_candidates:
        target_text = row[search_field]

        if not target_text:
            continue

        match = None
        if search_regex:
            match = search_regex.search(target_text)
            if not match:
                continue
        # Если regex нет, но есть глобальные условия, то match не нужен
        elif not global_conditions:
            continue

        word_data = dict(row)

        # --- Новая логика проверки фонологических признаков ---
        if match and search_in == "phonemes":
            matched_phonemes_str = match.group(0)
            if not _check_phonological_features(
                matched_phonemes_str, phonological_hardness, phonological_voicing
            ):
                continue

        if global_conditions:
            if not _check_global_conditions(word_data, global_conditions):
                continue

        # --- Проверка на исключение звуков ---
        if exclude_sounds:
            if not _check_exclusions(word_data, exclude_sounds):
                continue

        if match:
            word_data["matched_phonemes"] = match.group(0)
        else:
            if not regex_str and global_conditions:
                word_data["matched_phonemes"] = target_text

        if search_in == "phonemes" and match:
            phoneme_to_letter_map = (
                row["phoneme_to_letter_map"]
                if "phoneme_to_letter_map" in row.keys()
                else None
            )
            if phoneme_to_letter_map:
                try:
                    phonemes_before_match = len(
                        target_text[: match.start()].strip().split()
                    )
                    num_phonemes_in_match = len(match.group(0).strip().split())
                    phoneme_start_idx = phonemes_before_match
                    phoneme_end_idx = phonemes_before_match + num_phonemes_in_match - 1
                    letter_range = get_letter_range_for_phoneme_range(
                        phoneme_to_letter_map,
                        phoneme_start_idx,
                        phoneme_end_idx,
                        word_data["word"],
                    )
                    if letter_range:
                        start_idx, end_idx = letter_range
                        if 0 <= start_idx < end_idx <= len(word_data["word"]):
                            word_data["matched_span"] = (start_idx, end_idx)
                            word_data["matched_part"] = word_data["word"][
                                start_idx:end_idx
                            ]
                        else:
                            word_data["matched_part"] = None
                    else:
                        word_data["matched_part"] = None
                except Exception:
                    word_data["matched_part"] = None
            else:
                letters_part = map_phonemes_to_letters(
                    word_data["word"], target_text, match
                )
                if letters_part:
                    word_data["matched_part"] = letters_part[2]
                    word_data["matched_span"] = (letters_part[0], letters_part[1])
                else:
                    word_data["matched_part"] = None
        elif search_in == "phonemes" and not match:
            word_data["matched_part"] = word_data["word"]
        else:
            word_data["matched_part"] = match.group(0) if match else target_text

        final_results.append(word_data)

    return final_results


def _check_phonological_features(
    phonemes_str: str, hardness: Optional[str], voicing: Optional[str]
) -> bool:
    """
    Проверяет, содержит ли строка фонем хотя бы один согласный,
    соответствующий заданным признакам.
    """
    if not hardness and not voicing:
        return True

    phonemes = phonemes_str.strip().split()
    consonants_in_match = [
        p for p in phonemes if p in HARD_CONSONANTS or p in SOFT_CONSONANTS
    ]

    # Если в найденном фрагменте нет согласных, а фильтры есть, то совпадения нет
    if not consonants_in_match and (hardness or voicing):
        return False

    # --- Проверка на соответствие ХОТЯ БЫ ОДНОГО согласного ---
    # Если фильтр есть, но ни один согласный ему не удовлетворяет, то False.

    if hardness == "hard":
        if not any(p in HARD_CONSONANTS for p in consonants_in_match):
            return False

    if hardness == "soft":
        if not any(p in SOFT_CONSONANTS for p in consonants_in_match):
            return False

    if voicing == "voiced":
        if not any(p in VOICED_CONSONANTS for p in consonants_in_match):
            return False

    if voicing == "voiceless":
        if not any(p in VOICELESS_CONSONANTS for p in consonants_in_match):
            return False

    return True


def _check_global_conditions(
    word_data: Dict[str, Any], conditions: List[Dict[str, Any]]
) -> bool:
    """
    Проверяет, удовлетворяет ли слово глобальным условиям (например, количество определенных звуков).
    """
    phonemes = word_data["phonemes_list"].split()

    for condition in conditions:
        cond_type = condition["type"]
        cond_value = condition["value"]
        min_q, max_q = condition["quantifier"]

        if cond_type == "STRESS":
            stress_pos = int(cond_value)
            if (
                "stress_position" not in word_data
                or word_data["stress_position"] != stress_pos
            ):
                return False

        target_phonemes = set()
        if cond_type == "LITERAL":
            target_phonemes = {cond_value}
        elif cond_type == "TAG":
            from dsl_parser import TAG_MAP

            tag_names = cond_value.split(",")
            for name in tag_names:
                if len(name) == 1:
                    target_phonemes.add(name)
                elif name in TAG_MAP:
                    target_phonemes.update(list(TAG_MAP[name]))

        if not target_phonemes:
            continue

        count = sum(1 for p in phonemes if p in target_phonemes)

        if not (min_q <= count and (max_q is None or count <= max_q)):
            return False

    return True


def _check_exclusions(word_data: Dict[str, Any], exclude_str: str) -> bool:
    """
    Проверяет, содержит ли слово запрещенные звуки или категории звуков.
    Возвращает False, если найдено хотя бы одно исключение.
    """
    if not exclude_str:
        return True

    from dsl_parser import TAG_MAP

    phonemes_in_word = set(word_data["phonemes_list"].split())

    # Разбираем строку исключений на отдельные фонемы и теги
    exclusions = {item.strip() for item in exclude_str.split(",") if item.strip()}

    # Собираем полный сет фонем для исключения
    phonemes_to_exclude = set()
    for ex in exclusions:
        if ex in TAG_MAP:
            phonemes_to_exclude.update(TAG_MAP[ex])
        else:
            # Добавляем как литерал (например, "а" или "б'")
            phonemes_to_exclude.add(ex)

    # Если есть пересечение между фонемами слова и фонемами для исключения, слово не подходит
    if not phonemes_in_word.isdisjoint(phonemes_to_exclude):
        return False

    return True


if __name__ == "__main__":
    # Пример использования и тестирования

    # 1. Поиск "м" + любой гласный + "р" в фонемах
    test_query_1 = "м[гласн]р"
    results_1 = find_words(
        query=test_query_1, search_in="phonemes", sort_by_frequency=True
    )
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
    results_3 = find_words(
        query=test_query_3, part_of_speech="s", position="end", search_in="phonemes"
    )
    print(f"Результаты для существительных, оканчивающихся на фонему 'к':")
    for word_data in results_3[:5]:
        print(f"  - {word_data['word']} ({word_data['phonemes_list']})")
    print("-" * 20)

    # 4. Тест с глобальным условием
    test_query_4 = "дом (согл)(2)"
    results_4 = find_words(query=test_query_4, search_in="phonemes")
    print(f"\nРезультаты для DSL-запроса с глобальным условием '{test_query_4}':")
    for word_data in results_4[:10]:
        print(
            f"  - {word_data['word']} ({word_data['phonemes_list']}) -> "
            f"Найдено: '{word_data['matched_part']}'"
        )
    print("-" * 20)


def _get_phonemes_for_word(word: str, conn: sqlite3.Connection) -> Optional[str]:
    """
    Ищет слово в базе данных и возвращает его эталонную транскрипцию.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT phonemes_list FROM dictionary WHERE word = ?", (word,))
    result = cursor.fetchone()
    if result:
        return result[0]
    return None


def find_words_intelligent(
    query: str,
    syllable_count: Optional[List[int]] = None,
    part_of_speech: Optional[str] = None,
    position: str = "any",
    search_in: str = "phonemes",
    sort_by_frequency: bool = False,
    exclude_sounds: Optional[str] = None,
    phonological_hardness: Optional[str] = None,
    phonological_voicing: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Интеллектуальная обертка для find_words.
    Если query - это слово из словаря, использует его эталонную транскрипцию для поиска.
    В противном случае, обрабатывает query как фонемный шаблон.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row

    final_query = query
    is_word_in_db = False

    if search_in == "phonemes" and not re.search(r"[\[\]\*,]", query):
        phonemes_from_db = _get_phonemes_for_word(query.lower(), conn)
        if phonemes_from_db:
            final_query = phonemes_from_db
            is_word_in_db = True

    if is_word_in_db:
        position = "any"

    results = find_words(
        query=final_query,
        syllable_count=syllable_count,
        part_of_speech=part_of_speech,
        position=position,
        search_in=search_in,
        sort_by_frequency=sort_by_frequency,
        exclude_sounds=exclude_sounds,
        phonological_hardness=phonological_hardness,
        phonological_voicing=phonological_voicing,
        conn=conn,
    )

    conn.close()
    return results
