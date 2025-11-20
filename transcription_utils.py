# -*- coding: utf-8 -*-

"""
Утилиты для работы с транскрипциями: преобразование слов и выделение найденных паттернов.
"""

import re
from text_utils import syllabify_word, format_word_with_stress, text_to_phonemes

def highlight_phonetic_match_in_word(word: str, stress_position: int | None, search_pattern: re.Pattern) -> str:
    """
    Выделяет в слове слоги, соответствующие фонетическому паттерну.

    Логика работы:
    1. Слово транскрибируется в последовательность фонем.
    2. В этой последовательности ищутся все совпадения с паттерном.
    3. Слово разбивается на слоги (в орфографическом виде).
    4. Определяется, какие слоги нужно подсветить, на основе позиций найденных фонем.
    5. Слово форматируется с ударением и выделением нужных слогов тегом <b>.

    Args:
        word (str): Исходное слово.
        stress_position (int | None): Позиция ударения.
        search_pattern (re.Pattern): Скомпилированное регулярное выражение для поиска.

    Returns:
        str: HTML-строка с выделенными слогами.
    """
    if not word or not search_pattern:
        return format_word_with_stress(word, stress_position)

    # 1. Транскрибируем слово
    phonetic_representation = " ".join(text_to_phonemes(word))
    
    # 2. Находим все совпадения паттерна в фонетической строке
    matches = list(search_pattern.finditer(phonetic_representation))
    if not matches:
        return format_word_with_stress(word, stress_position)

    # 3. Разбиваем слово на слоги
    syllables = syllabify_word(word)
    if not syllables:
        return format_word_with_stress(word, stress_position)

    # 4. Определяем, какие слоги нужно подсветить
    # Создаем карту "индекс символа в слове -> индекс слога"
    char_to_syllable_map = {}
    char_idx = 0
    for i, syllable in enumerate(syllables):
        for _ in syllable:
            char_to_syllable_map[char_idx] = i
            char_idx += 1

    # Создаем карту "индекс фонемы -> индекс символа в слове"
    # Это упрощенная карта, которая не учитывает сложные случаи (одна буква - два звука и т.д.),
    # но для цели выделения слога ее достаточно.
    phoneme_to_char_map = list(range(len(word)))

    syllables_to_highlight = set()
    phonemes_list = phonetic_representation.split()

    for match in matches:
        match_start_phoneme_idx = len(phonetic_representation[:match.start()].split())
        match_end_phoneme_idx = len(phonetic_representation[:match.end()].split()) -1

        # Находим соответствующие символы в исходном слове
        start_char_idx = phoneme_to_char_map[match_start_phoneme_idx] if match_start_phoneme_idx < len(phoneme_to_char_map) else 0
        end_char_idx = phoneme_to_char_map[match_end_phoneme_idx] if match_end_phoneme_idx < len(phoneme_to_char_map) else len(word) - 1

        # Определяем слоги, которые покрываются найденным диапазоном
        for i in range(start_char_idx, end_char_idx + 1):
            if i in char_to_syllable_map:
                syllables_to_highlight.add(char_to_syllable_map[i])

    # 5. Собираем итоговое слово с выделением и ударением
    final_word_parts = []
    stressed_syllable_idx = -1
    if stress_position is not None:
        char_idx_counter = 0
        for i, syllable in enumerate(syllables):
            if char_idx_counter <= stress_position < char_idx_counter + len(syllable):
                stressed_syllable_idx = i
                break
            char_idx_counter += len(syllable)
    
    for i, syllable in enumerate(syllables):
        part = syllable
        if i == stressed_syllable_idx:
            # Вставляем ударение после первой гласной в слоге
            vowel_found = False
            for char_pos, char in enumerate(part):
                 if char.lower() in "аеёиоуыэюя":
                    part = part[:char_pos+1] + "\u0301" + part[char_pos+1:]
                    vowel_found = True
                    break
            if not vowel_found: # Если в слоге нет гласной (маловероятно, но возможно)
                part += "\u0301"

        if i in syllables_to_highlight:
            final_word_parts.append(f"<b>{part}</b>")
        else:
            final_word_parts.append(part)

    return "".join(final_word_parts)
