# -*- coding: utf-8 -*-
"""
Модуль для создания и использования mapping'а фонем на буквы слова.
Решает проблему рассинхронизации фонемизации при выделении.
"""

import json
from typing import List, Tuple, Optional


def create_phoneme_letter_mapping(word: str, phonemes_list: str) -> str:
    """
    Создает mapping между фонемами и буквами слова при заполнении БД.

    Алгоритм:
    - Проходим по буквам слова
    - Для каждой фонемы определяем, какие буквы её составляют
    - Учитываем мягкие знаки и апострофы

    Args:
        word: Исходное слово (буквы) - "аббревиатура"
        phonemes_list: Список фонем через пробел - "а б' б' р' э в' и а т у р а"

    Returns:
        JSON-строка с mapping'ом: список кортежей [letter_start, letter_end, phoneme_idx]

    Пример:
        word = "аббревиатура"
        phonemes = "а б' б' р' э в' и а т у р а"

        Результат:
        [
            [0, 1, 0],     # фонема 0 ('а') = буквы [0:1] = 'а'
            [1, 3, 1],     # фонема 1 ('б'') = буквы [1:3] = 'бб'
            [3, 4, 2],     # фонема 2 ('б'') = буквы [3:4] = 'б'
            ...
        ]
    """
    if not phonemes_list or not word:
        return "[]"

    phonemes = phonemes_list.split()
    mapping = []

    letter_idx = 0

    for phoneme_idx, phoneme in enumerate(phonemes):
        start_letter = letter_idx

        # Фонема мягкая согласная (заканчивается на апостроф)
        if len(phoneme) >= 2 and phoneme[-1] == "'":
            # Ищем букву, которая производит эту фонему
            if letter_idx < len(word):
                if letter_idx + 1 < len(word) and word[letter_idx + 1] == "ь":
                    # Согласная + мягкий знак
                    letter_idx += 2
                elif letter_idx + 1 < len(word) and word[letter_idx + 1] in "яёюие":
                    # Согласная перед мягкой гласной
                    letter_idx += 1
                else:
                    # Просто согласная
                    letter_idx += 1
        else:
            # Обычный звук (гласный или твердый согласный)
            if letter_idx < len(word):
                # Пропускаем мягкие и твёрдые знаки
                if word[letter_idx] in "ьъ":
                    letter_idx += 1
                else:
                    letter_idx += 1

        mapping.append([start_letter, letter_idx, phoneme_idx])

    try:
        return json.dumps(mapping, ensure_ascii=False)
    except Exception:
        return "[]"


def get_letter_range_for_phoneme_range(
    phoneme_to_letter_map_json: str,
    phoneme_start_idx: int,
    phoneme_end_idx: int,
    word: Optional[str] = None,
) -> Optional[Tuple[int, int]]:
    """
    По mapping'у и индексам фонем возвращает диапазон букв для выделения.

    Если перед слогом есть удвоенные буквы, смещает выделение на один символ вправо,
    чтобы не захватывать вторую букву из пары удвоенных.

    Args:
        phoneme_to_letter_map_json: JSON из БД (phoneme_to_letter_map)
        phoneme_start_idx: Индекс первой фонемы в найденном диапазоне
        phoneme_end_idx: Индекс последней фонемы (включительно)
        word: Опционально исходное слово для проверки удвоенных букв

    Returns:
        Кортеж (letter_start, letter_end) или None если ошибка

    Пример:
        Если найдены фонемы с индексами 6-7 (фонемы "и а"):
        - Из mapping получаем: фонема 6 начинается с буквы 6, фонема 7 заканчивается буквой 8
        - Возвращаем (6, 8)

        Для слова "аббревиатура" с удвоенной "бб":
        - Если letter_start = 1 и перед ним (буква 0) удвоенная с буквой 1, смещаем на 1 вправо
    """
    if not phoneme_to_letter_map_json:
        return None

    try:
        mapping = json.loads(phoneme_to_letter_map_json)
    except (json.JSONDecodeError, TypeError):
        return None

    if not mapping or phoneme_start_idx < 0 or phoneme_end_idx >= len(mapping):
        return None

    try:
        # Получаем буквы для первой фонемы
        start_entry = mapping[phoneme_start_idx]
        letter_start = start_entry[0]

        # Получаем буквы для последней фонемы
        end_entry = mapping[phoneme_end_idx]
        letter_end = end_entry[1]

        # Проверка на удвоенные буквы перед слогом
        if word and letter_start > 0 and letter_start < len(word):
            # Проверяем, есть ли удвоенная буква перед начальной позицией
            prev_char = word[letter_start - 1]
            curr_char = word[letter_start]

            # Если предыдущая буква такая же как текущая (удвоенная), смещаем выделение
            if prev_char == curr_char and prev_char not in "ьъ":
                # Смещаем start_idx на 1 вправо, но увеличиваем и end_idx если нужно
                # чтобы сохранить выделение
                letter_start += 1
                if letter_end == letter_start:
                    letter_end += 1

        return (letter_start, letter_end)
    except (IndexError, TypeError):
        return None


if __name__ == "__main__":
    # Тест
    test_word = "аббревиатура"
    test_phonemes = "а б' б' р' э в' и а т у р а"

    mapping_json = create_phoneme_letter_mapping(test_word, test_phonemes)
    print(f"Слово: {test_word}")
    print(f"Фонемы: {test_phonemes}")
    print(f"Mapping: {mapping_json}")

    # Тест получения диапазона (фонемы 6-7: "и а")
    # Теперь передаем параметр word для проверки удвоенных букв
    letter_range = get_letter_range_for_phoneme_range(mapping_json, 6, 7, test_word)
    print(f"Фонемы 6-7 соответствуют буквам: {letter_range}")
    if letter_range:
        start, end = letter_range
        print(f"Выделяемый текст: '{test_word[start:end]}'")
