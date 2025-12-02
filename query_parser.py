# -*- coding: utf-8 -*-

"""
Модуль для разбора фонологических запросов и преобразования их в регулярные выражения.
"""

import re
from phonology_rules import (
    VOICED_CONSONANTS,
    VOICELESS_CONSONANTS,
    HARD_CONSONANTS,
    SOFT_CONSONANTS,
    ALL_CONSONANTS,
    VOWELS,
)

# Карта для преобразования букв в фонемы (упрощенная)
# Гласные, которые смягчают предыдущую согласную
SOFTENING_VOWELS = {"я", "ё", "ю", "и", "е"}

# Трансляция букв гласных в их фонемное представление
VOWEL_LETTER_TO_PHONEME = {
    "а": "а",
    "о": "о",
    "у": "у",
    "ы": "ы",
    "э": "э",
    "я": "а",
    "ё": "о",
    "ю": "у",
    "и": "и",
    "е": "е",
}

# Гласные, которые в начале слова или после гласной дают "й" + гласный звук
YOTATED_VOWELS = {"я": "а", "ё": "о", "ю": "у", "е": "э"}

# Теги для фонемных групп
TAG_TO_PHONEMES = {
    "звонк": VOICED_CONSONANTS,
    "глух": VOICELESS_CONSONANTS,
    "тверд": HARD_CONSONANTS,
    "мягк": SOFT_CONSONANTS,
    "согл": ALL_CONSONANTS,
    "гласн": VOWELS,
    "любой": ALL_CONSONANTS | VOWELS,
}


def _process_text_part(text_part: str) -> str:
    """
    Интеллектуально обрабатывает текстовую часть запроса, преобразуя её
    в последовательность фонем для регулярного выражения.
    """
    phonemes = []
    i = 0
    n = len(text_part)

    # Множество всех согласных букв для быстрой проверки
    consonant_letters = {p.replace("'", "") for p in ALL_CONSONANTS}

    while i < n:
        char = text_part[i]

        if char in consonant_letters:
            # Смотрим на следующий символ для определения мягкости
            if i + 1 < n:
                next_char = text_part[i + 1]
                if next_char == "ь":
                    # Явная мягкость: "ть", "рь" -> "т'", "р'"
                    phonemes.append(f"{char}'")
                    i += 2  # Пропускаем согласную и мягкий знак
                    continue
                elif next_char in SOFTENING_VOWELS:
                    # Мягкость через гласную: "ря", "ти" -> "р' а", "т' и"
                    phonemes.append(f"{char}'")
                    phonemes.append(VOWEL_LETTER_TO_PHONEME[next_char])
                    i += 2  # Пропускаем оба символа
                    continue
                elif next_char == "ъ":
                    # Твердый знак просто игнорируется, согласная остается твердой
                    phonemes.append(char)
                    i += 2
                    continue

            # Если нет признаков мягкости, согласная твердая
            phonemes.append(char)
            i += 1

        elif char in VOWEL_LETTER_TO_PHONEME:
            # Проверяем, является ли гласная йотированной и стоит ли она в начале
            # или после другой гласной (что _process_text_part не отслеживает,
            # но для простых случаев, как "яр", это сработает, т.к. "я" первая).
            is_yotated_position = not phonemes or phonemes[-1] in VOWELS

            if char in YOTATED_VOWELS and is_yotated_position:
                phonemes.append("й")
                phonemes.append(YOTATED_VOWELS[char])
            else:
                phonemes.append(VOWEL_LETTER_TO_PHONEME[char])
            i += 1

        elif char == "'":
            # Если пользователь сам ввел апостроф для обозначения мягкости
            if phonemes:
                last_phoneme = phonemes[-1]
                if last_phoneme in consonant_letters and not last_phoneme.endswith("'"):
                    phonemes[-1] = f"{last_phoneme}'"
            i += 1

        else:
            # Игнорируем неалфавитные символы (пробелы, дефисы и т.д.)
            i += 1

    # Преобразуем фонемы к формату базы данных (с учетом пробелов перед апострофами)
    processed_phonemes = []
    for phoneme in phonemes:
        if phoneme.endswith("'"):
            # Для фонем с апострофом (мягкие согласные), 
            # в базе данных они хранятся как: "б '"
            processed_phonemes.append(phoneme[:-1] + r" '")
        else:
            processed_phonemes.append(phoneme)
    return r" ".join(processed_phonemes)


def parse_query_to_regex(query: str) -> str:
    """
    Преобразует пользовательский запрос в регулярное выражение для поиска по списку фонем.
    Версия 2.0: интеллектуальная обработка букв.
    """
    bracket_pattern = re.compile(r"(\[[^\]]+\])")
    parts = bracket_pattern.split(query)
    result_parts = []

    for part in parts:
        if not part:
            continue

        if bracket_pattern.match(part):
            # Обработка тегов [ ] остаётся прежней
            content = part.strip("[]")
            if "," in content:
                phonemes = [p.strip() for p in content.split(",")]
                escaped_phonemes = [re.escape(p) for p in phonemes if p]
                if escaped_phonemes:
                    result_parts.append(f"({'|'.join(escaped_phonemes)})")
            elif content in TAG_TO_PHONEMES:
                phonemes = TAG_TO_PHONEMES[content]
                escaped_phonemes = [re.escape(p) for p in phonemes]
                result_parts.append(f"({'|'.join(escaped_phonemes)})")
            else:
                # Если внутри скобок не тег и не перечисление, обрабатываем как текст
                result_parts.append(_process_text_part(content))
        else:
            # Обычный текст без скобок
            cleaned_part = "".join(part.split())
            if cleaned_part:
                result_parts.append(_process_text_part(cleaned_part))

    final_regex = " ".join(filter(None, result_parts))
    return re.sub(r"\s+", " ", final_regex).strip()


if __name__ == "__main__":
    test_queries = [
        "м[гласн]р",
        "[тверд] [звонк]",
        "с [мягк] [гласн]",
        "п р [гласн] [глух] т",
        "[любой] [любой] [любой]",
        # Новые тесты для проверки расширенного синтаксиса
        "ра",  # Простой слог: р а
        "ря",  # Слог с мягкой согласной: р' а
        "тьма",  # Мягкий знак: т' м а
        "конь",  # Мягкий знак в конце: к о н'
        "объезд",  # Твердый знак: о б й э з д
        "п'еса",  # Апостроф как знак мягкости: п' э с а
        "[т,д]рактор",  # Перечисление в начале слова
        "м[а,о]шина",  # Перечисление в середине слова
        "[гласн][т,д][гласн]",  # Комбинация тега и перечисления
    ]

    for q in test_queries:
        regex = parse_query_to_regex(q)
        print(f"Запрос: '{q}'\n  -> Regex: '{regex}'\n")
