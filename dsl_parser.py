# -*- coding: utf-8 -*-
"""
Парсер для обработки DSL-запросов.

Модуль отвечает за полный цикл разбора DSL-запроса:
1. Лексический анализ (токенизация).
2.  Синтаксический анализ (построение AST и выделение глобальных условий).
3.  Генерация регулярного выражения для поиска последовательностей.
"""
import re
from typing import List, Tuple, Dict, Any, Optional

# --- Константы и карты ---

from phonology_rules import (
    VOICED_CONSONANTS,
    VOICELESS_CONSONANTS,
    HARD_CONSONANTS,
    SOFT_CONSONANTS,
    ALL_CONSONANTS,
    VOWELS,
)

TAG_MAP = {
    "гласн": VOWELS,
    "согл": ALL_CONSONANTS,
    "тверд": HARD_CONSONANTS,
    "мягк": SOFT_CONSONANTS,
    "звонк": VOICED_CONSONANTS,
    "глух": VOICELESS_CONSONANTS,
    "шип": "жчшщ",
    "сон": "йлмнр",
}

# Регулярные выражения для токенизации
TOKEN_SPECIFICATION = [
    ("STRESS", r"уд\d+"),
    ("SEQUENCE", r"([а-яёыА-ЯЁЫ]|\([а-яёыА-ЯЁЫ,]+\))+"),
    ("LITERAL", r"[а-яёыА-ЯЁЫ]"),
    ("TAG", r"\([а-яёыА-ЯЁЫ,]+\)+"),
    ("QUANTIFIER", r"\(\d+(-(\d+)?)?\+?\)"),
    ("WILDCARD", r"\*\*?"),
    ("DOT", r"\."),
    ("ESCAPE", r"\\."),
    ("STRESS_MARKER", r"!!|!"),
    ("SPACE", r"\s+"),
    ("ERROR", r"."),
]
TOKEN_REGEX = re.compile(
    "|".join(f"(?P<{name}>{spec})" for name, spec in TOKEN_SPECIFICATION)
)


class DSLParser:
    """
    Класс, инкапсулирующий всю логику разбора DSL-запроса.
    """

    def parse(self, query: str) -> Dict[str, Any]:
        """
        Главный метод, выполняющий полный разбор запроса.

        Args:
            query: Строка запроса на DSL.

        Returns:
            Словарь, содержащий:
            - 'sequence_regex': Регулярное выражение для поиска последовательностей.
            - 'global_conditions': Список глобальных условий для проверки всего слова.
        """
        query = query.lower().replace("ё", "е")
        tokens = self._tokenize(query)
        sequence_tokens, global_conditions = self._distribute_tokens(
            tokens, original_query=query
        )

        sequence_regex = self._build_sequence_regex(sequence_tokens)

        return {
            "sequence_regex": sequence_regex,
            "global_conditions": global_conditions,
        }

    def _tokenize(self, query: str) -> List[Tuple[str, str]]:
        """Разбивает строку на токены."""
        tokens = []
        for mo in TOKEN_REGEX.finditer(query):
            kind = mo.lastgroup
            value = mo.group()

            if kind == "SPACE":
                continue
            if kind == "ERROR":
                raise ValueError(
                    f"Недопустимый символ или синтаксис в запросе: '{value}'"
                )

            tokens.append((kind, value))
        return tokens

    def _distribute_tokens(
        self, tokens: List[Tuple[str, str]], original_query: str = None
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Распределяет токены на 'sequence' (для регекса) и 'global' (для постобработки).
        STRESS_MARKER (! или !!) модифицирует *предыдущий* токен, добавляя ему атрибут 'stress'.
        """
        sequence_tokens = []
        global_conditions = []
        i = 0

        while i < len(tokens):
            kind, value = tokens[i]

            if i + 1 < len(tokens) and tokens[i + 1][0] == "QUANTIFIER":
                quant_kind, quant_value = tokens[i + 1]
                quantifier_tuple = self._parse_quantifier(quant_value)

                # Обновляем логику обработки квантификатора
                global_conditions.append(
                    {
                        "type": kind,  # Тип текущего токена
                        "value": value,  # Значение текущего токена
                        "quantifier": quantifier_tuple,
                    }
                )
                i += 2
            elif kind == "STRESS":
                stress_pos = int(value[2:])
                if stress_pos <= 0:
                    raise ValueError(
                        "Номер слога для ударения должен быть положительным числом."
                    )
                global_conditions.append(
                    {"type": "STRESS", "value": str(stress_pos), "quantifier": (1, 1)}
                )
                i += 1
            elif kind == "STRESS_MARKER":
                if sequence_tokens:
                    prev_token = sequence_tokens[-1]
                    if value == "!":
                        prev_token["stress"] = "stressed"
                    elif value == "!!":
                        prev_token["stress"] = "unstressed"
                i += 1
            elif kind == "ESCAPE":
                escaped_char = value[1]
                sequence_tokens.append({"type": "LITERAL", "value": escaped_char})
                i += 1
            elif kind == "DOT":
                sequence_tokens.append({"type": "LITERAL", "value": "."})
                i += 1
            elif kind == "LITERAL":
                sequence_tokens.append({"type": "LITERAL", "value": value})
                i += 1
            elif kind == "TAG":
                sequence_tokens.append(
                    {"type": "TAG", "value": value[1:-1]}
                )  # Убираем скобки
                i += 1
            else:
                sequence_tokens.append({"type": kind, "value": value})
                i += 1
        return sequence_tokens, global_conditions

    def _normalize_token_value(
        self, kind: str, value: str, original_query: str = None
    ) -> str:
        """Убирает скобки из тегов для дальнейшей обработки."""
        if kind == "SEQUENCE":
            return value
        if kind == "TAG":
            return value[1:-1]
        return value

    def _parse_quantifier(self, value: str) -> Tuple[int, Optional[int]]:
        """Парсит строковое представление квантификатора в кортеж (min, max)."""
        original_value = value
        value = value[1:-1]

        if value.startswith("-"):
            if value.lstrip("-").isdigit():
                raise ValueError("Число в кванторе не может быть отрицательным.")
            else:
                raise ValueError(f"Некорректный формат диапазона в кванторе: {value}")

        if not re.fullmatch(r"\d+(-\d+)?\+?", value):
            if not value or not value.replace("-", "").replace("+", "").isdigit():
                raise ValueError(f"Некорректный формат диапазона в кванторе: {value}")

        if value.endswith("+"):
            min_val = int(value[:-1])
            if min_val < 0:
                raise ValueError("Число в кванторе не может быть отрицательным.")
            return (min_val, None)

        if "-" in value:
            parts = value.split("-")
            if len(parts) != 2 or not parts[0] or (len(parts) > 1 and not parts[1]):
                if value.endswith("-"):
                    raise ValueError(
                        f"Некорректный формат диапазона в кванторе: {value}"
                    )
                raise ValueError(f"Некорректный формат диапазона в кванторе: {value}")

            min_val = int(parts[0])
            if len(parts) > 1:
                max_val = int(parts[1])
            else:
                max_val = min_val

            if min_val < 0 or max_val < 0:
                raise ValueError("Число в кванторе не может быть отрицательным.")
            if max_val < min_val:
                raise ValueError(
                    f"Верхняя граница ({max_val}) не может быть меньше нижней ({min_val})."
                )
            return (min_val, max_val)

        min_val = int(value)
        if min_val < 0:
            raise ValueError("Число в кванторе не может быть отрицательным.")
        return (min_val, min_val)

    def _build_sequence_regex(self, tokens: List[Dict]) -> str:
        """Строит регулярное выражение из токенов последовательности."""
        regex_parts = []
        for token in tokens:
            kind, value = token["type"], token["value"]
            stress_info = token.get("stress")

            if kind == "LITERAL":
                # Преобразуем буквенный литерал в фонему
                from text_utils import text_to_phonemes

                phoneme_list = text_to_phonemes(value)
                # Преобразуем фонемы к формату базы данных (с учетом пробелов перед апострофами)
                processed_phonemes = []
                for phoneme in phoneme_list:
                    if phoneme.endswith("'"):
                        # Для фонем с апострофом (мягкие согласные),
                        # в базе данных они хранятся как: "б '"
                        processed_phonemes.append(phoneme[:-1] + r"\s*'")
                    else:
                        processed_phonemes.append(phoneme)
                phoneme_sequence = r"\s+".join(processed_phonemes)
                regex_parts.append(phoneme_sequence)
            elif kind == "WILDCARD":
                if value == "*":
                    regex_parts.append("[^\\s']+")
                elif value == "**":
                    # (?:[^\\s']+\\s*)*?  - ноль или более фонем, нежадный поиск
                    # [^\\s']+          - одна или более фонем (любые символы кроме пробела и апострофа)
                    # \\s*              - ноль или более пробелов после фонемы
                    regex_parts.append("(?:[^\\s']+\\s*)*?")
            elif kind == "TAG":
                # Обработка тега - это может быть (гласн), (согл), (тверд) и т.д.
                tag_names = value.split(",")
                phonemes = set()
                for name in tag_names:
                    name = name.strip()  # Убираем пробелы
                    if (
                        len(name) == 1
                        and name.lower() in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                    ):
                        phonemes.add(name)
                        # Если это гласная, добавим также ударный вариант
                        if name.lower() in "аоуыэиейюяё":
                            phonemes.add(f"{name}'")
                    elif name in TAG_MAP:
                        phonemes.update(list(TAG_MAP[name]))
                        # Для гласных в тегах также добавим ударные варианты
                        if name in ["гласн"]:
                            stressed_variants = {f"{v}'" for v in TAG_MAP[name]}
                            phonemes.update(stressed_variants)
                    else:
                        raise ValueError(f"Неизвестный тег или символ: {name}")

                escaped_phonemes = [re.escape(p) for p in sorted(list(phonemes))]

                if stress_info == "stressed":
                    stressed_alternatives = [f"{p}'" for p in escaped_phonemes]
                    regex_parts.append(f"({'|'.join(stressed_alternatives)})")
                elif stress_info == "unstressed":
                    base_group = f"({'|'.join(escaped_phonemes)})"
                    regex_parts.append(f"{base_group}(?!')")
                else:
                    # Для базового варианта нужно учитывать особенности формата транскрипции в базе данных
                    # В базе данных ударные гласные представлены двумя способами:
                    # 1. Безударные: просто гласная (например, 'и')
                    # 2. Ударные: гласная + пробел + ' (например, 'и ' или как отдельные 'и' и ' ')
                    # Нужно создать паттерн, который будет учитывать оба формата
                    alternatives = (
                        set()
                    )  # Используем множество для избежания дубликатов
                    for p in escaped_phonemes:
                        if p in [
                            "а'",
                            "о'",
                            "у'",
                            "ы'",
                            "э'",
                            "и'",
                            "е'",
                            "ю'",
                            "я'",
                            "ё'",
                        ]:
                            # Для ударных гласных: может быть как 'и' (вместе), так и 'и ' (раздельно)
                            # Раздельный формат: гласная + пробел + '
                            alternatives.add(f"{p[:-1]}\\s*'")  # гласная + пробел + '
                            # Объединённый формат: гласная'
                            alternatives.add(p)
                            # И просто гласная (на случай если ударение записано по-другому)
                            alternatives.add(f"{p[:-1]}")
                        elif p in ["а", "о", "у", "ы", "э", "и", "е", "ю", "я", "ё"]:
                            # Для безударных гласных: может быть ударной вариант (в раздельном формате)
                            alternatives.add(p)  # безударный вариант
                            alternatives.add(
                                f"{p}\\s*'"
                            )  # ударный вариант в раздельном формате
                        else:
                            alternatives.add(p)
                    regex_parts.append(f"({'|'.join(sorted(list(alternatives)))})")
            elif kind == "SEQUENCE":
                # Для совместимости - обработка последовательности как раньше
                sub_parts = re.findall(r"[а-яёыА-ЯЁЫ]+|\([а-яёыА-ЯЁЫ,]+\)", value)

                # Если последовательность содержит и буквы, и теги, нужно учитывать
                # контекстное изменение фонем (например, согласная перед гласной может смягчиться)
                if len(sub_parts) > 1:
                    # Обработка комбинации букв и тегов с учетом контекста
                    from text_utils import text_to_phonemes
                    from itertools import product

                    sequence_regex_parts_internal = []

                    for idx, part in enumerate(sub_parts):
                        is_last_part_of_token = idx == len(sub_parts) - 1

                        if part.startswith("("):
                            # Обработка тега (например, (и,е))
                            tag_content = part[1:-1]
                            tag_names = tag_content.split(",")
                            
                            # Check if there's a following vowel in the sequence that would make consonants soft
                            has_following_vowel = False
                            for next_idx in range(idx + 1, len(sub_parts)):
                                next_part = sub_parts[next_idx]
                                if not next_part.startswith("("): # It's a literal
                                    # Check if the literal contains a vowel that makes preceding consonants soft
                                    from text_utils import SOFTENING_VOWELS
                                    if any(vowel in next_part for vowel in SOFTENING_VOWELS):
                                        has_following_vowel = True
                                        break
                            
                            phonemes = set()
                            for name in tag_names:
                                if (
                                    len(name) == 1
                                    and name.lower()
                                    in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                                ):
                                    # If this consonant tag is followed by a vowel that makes it soft, convert to phonemes
                                    if has_following_vowel and name.lower() in "бвгджзйклмнпрстфхцчшщ":
                                        # Process the combination to get the correct phoneme representation
                                        combined_text = name + "е"  # Use 'е' as a representative softening vowel
                                        phoneme_list = text_to_phonemes(combined_text)
                                        # Take only the consonant part (first phoneme) which should be soft
                                        if len(phoneme_list) > 0:
                                            consonant_phoneme = phoneme_list[0]
                                            if consonant_phoneme.endswith("'"):
                                                # For soft consonants in DB format
                                                phonemes.add(consonant_phoneme[:-1] + r" '")
                                            else:
                                                phonemes.add(consonant_phoneme)
                                    else:
                                        # Add the raw letter, it will be handled by the TAG_MAP logic below
                                        phonemes.add(name)
                                elif name in TAG_MAP:
                                    phonemes.update(list(TAG_MAP[name]))
                                else:
                                    raise ValueError(
                                        f"Неизвестный тег или символ: {name}"
                                    )

                            # If we have phonemes from context processing, use them; otherwise use original approach
                            if phonemes and any(p.endswith(" '") for p in phonemes if isinstance(p, str)):
                                # Use the context-processed phonemes
                                escaped_phonemes = [re.escape(p) for p in sorted(list(phonemes))]
                            else:
                                # Fall back to original approach for tags that are not consonants
                                phonemes.clear()  # Clear the set
                                for name in tag_names:
                                    if (
                                        len(name) == 1
                                        and name.lower()
                                        in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                                    ):
                                        phonemes.add(name)
                                    elif name in TAG_MAP:
                                        phonemes.update(list(TAG_MAP[name]))
                                    else:
                                        raise ValueError(
                                            f"Неизвестный тег или символ: {name}"
                                        )
                                escaped_phonemes = [re.escape(p) for p in sorted(list(phonemes))]

                            if is_last_part_of_token and stress_info == "stressed":
                                stressed_alternatives = [
                                    f"{p}'" for p in escaped_phonemes
                                ]
                                sequence_regex_parts_internal.append(
                                    f"({'|'.join(stressed_alternatives)})"
                                )
                            elif is_last_part_of_token and stress_info == "unstressed":
                                base_group = f"({'|'.join(escaped_phonemes)})"
                                sequence_regex_parts_internal.append(
                                    f"{base_group}(?!')"
                                )
                            else:
                                sequence_regex_parts_internal.append(
                                    f"({'|'.join(escaped_phonemes)})"
                                )
                        else:  # Это буквенный литерал
                            # Преобразуем буквенный литерал в фонемы
                            phoneme_list = text_to_phonemes(part)
                            # Преобразуем фонемы к формату базы данных (с учетом пробелов перед апострофами)
                            processed_phonemes = []
                            for phoneme in phoneme_list:
                                if phoneme.endswith("'"):
                                    # Для фонем с апострофом (мягкие согласные),
                                    # в базе данных они хранятся как: "б '"
                                    processed_phonemes.append(phoneme[:-1] + r"\s*'")
                                else:
                                    processed_phonemes.append(phoneme)

                            phoneme_sequence = r"\s+".join(processed_phonemes)

                            if is_last_part_of_token and stress_info == "stressed":
                                # Добавляем апостроф к последней фонеме, если она гласная
                                if phoneme_list:
                                    last_phoneme = phoneme_list[-1]
                                    # Проверяем, является ли последняя фонема гласной (без апострофа)
                                    if last_phoneme in "аоуыэи" or last_phoneme in [
                                        "а",
                                        "о",
                                        "у",
                                        "ы",
                                        "э",
                                        "и",
                                        "е",
                                        "ю",
                                        "я",
                                        "ё",
                                    ]:
                                        # Обработка ударной гласной - find the corresponding processed phoneme and modify it
                                        # Find the last phoneme that corresponds to the vowel
                                        for j in range(
                                            len(processed_phonemes) - 1, -1, -1
                                        ):
                                            if processed_phonemes[j].startswith(
                                                last_phoneme
                                            ) and not processed_phonemes[j].endswith(
                                                "'"
                                            ):
                                                processed_phonemes[j] = (
                                                    f"{last_phoneme}'"
                                                )
                                                break
                                        phoneme_sequence = r"\s+".join(
                                            processed_phonemes
                                        )
                            elif is_last_part_of_token and stress_info == "unstressed":
                                # Проверяем, является ли последняя фонема гласной
                                if phoneme_list:
                                    last_phoneme = phoneme_list[-1]
                                    if last_phoneme in "аоуыэи" or last_phoneme in [
                                        "а",
                                        "о",
                                        "у",
                                        "ы",
                                        "э",
                                        "и",
                                        "е",
                                        "ю",
                                        "я",
                                        "ё",
                                    ]:
                                        # Заменяем последнюю фонему на вариант с отрицанием апострофа
                                        # Find the corresponding processed phoneme and modify it
                                        for j in range(
                                            len(processed_phonemes) - 1, -1, -1
                                        ):
                                            if processed_phonemes[j].startswith(
                                                last_phoneme
                                            ) and not processed_phonemes[j].endswith(
                                                "'"
                                            ):
                                                processed_phonemes[j] = (
                                                    f"{last_phoneme}(?!')"
                                                )
                                                break
                                        phoneme_sequence = r"\s+".join(
                                            processed_phonemes
                                        )

                            sequence_regex_parts_internal.append(phoneme_sequence)

                    # Для внутренних частей последовательности используем пробелы
                    regex_parts.append(r"\s+".join(sequence_regex_parts_internal))
                else:
                    # Старая логика для последовательностей без тегов
                    sequence_regex_parts_internal = []
                    for i, part in enumerate(sub_parts):
                        is_last_part_of_token = i == len(sub_parts) - 1

                        if part.startswith("("):
                            tag_content = part[1:-1]
                            tag_names = tag_content.split(",")
                            phonemes = set()
                            for name in tag_names:
                                if (
                                    len(name) == 1
                                    and name.lower()
                                    in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
                                ):
                                    phonemes.add(name)
                                elif name in TAG_MAP:
                                    phonemes.update(list(TAG_MAP[name]))
                                else:
                                    raise ValueError(
                                        f"Неизвестный тег или символ: {name}"
                                    )

                            escaped_phonemes = [
                                re.escape(p) for p in sorted(list(phonemes))
                            ]

                            if is_last_part_of_token and stress_info == "stressed":
                                stressed_alternatives = [
                                    f"{p}'" for p in escaped_phonemes
                                ]
                                sequence_regex_parts_internal.append(
                                    f"({'|'.join(stressed_alternatives)})"
                                )
                            elif is_last_part_of_token and stress_info == "unstressed":
                                base_group = f"({'|'.join(escaped_phonemes)})"
                                sequence_regex_parts_internal.append(
                                    f"{base_group}(?!')"
                                )
                            else:
                                sequence_regex_parts_internal.append(
                                    f"({'|'.join(escaped_phonemes)})"
                                )
                        else:  # Это буквенный литерал, который нужно преобразовать в фонемы
                            # Используем логику из text_utils для преобразования букв в фонемы
                            from text_utils import text_to_phonemes

                            phoneme_list = text_to_phonemes(part)
                            # Преобразуем фонемы к формату базы данных (с учетом пробелов перед апострофами)
                            processed_phonemes = []
                            for phoneme in phoneme_list:
                                if phoneme.endswith("'"):
                                    # Для фонем с апострофом (мягкие согласные),
                                    # в базе данных они хранятся как: "б '"
                                    processed_phonemes.append(phoneme[:-1] + r"\s*'")
                                else:
                                    processed_phonemes.append(phoneme)

                            phoneme_sequence = r"\s+".join(processed_phonemes)

                            if is_last_part_of_token and stress_info == "stressed":
                                # Добавляем апостроф к последней фонеме, если она гласная
                                if phoneme_list:
                                    last_phoneme = phoneme_list[-1]
                                    # Проверяем, является ли последняя фонема гласной (без апострофа)
                                    if last_phoneme in "аоуыэи" or last_phoneme in [
                                        "а",
                                        "о",
                                        "у",
                                        "ы",
                                        "э",
                                        "и",
                                        "е",
                                        "ю",
                                        "я",
                                        "ё",
                                    ]:
                                        # Обработка ударной гласной - find the corresponding processed phoneme and modify it
                                        # Find the last phoneme that corresponds to the vowel
                                        for j in range(
                                            len(processed_phonemes) - 1, -1, -1
                                        ):
                                            if processed_phonemes[j].startswith(
                                                last_phoneme
                                            ) and not processed_phonemes[j].endswith(
                                                "'"
                                            ):
                                                processed_phonemes[j] = (
                                                    f"{last_phoneme}'"
                                                )
                                                break
                                        phoneme_sequence = r"\s+".join(
                                            processed_phonemes
                                        )
                            elif is_last_part_of_token and stress_info == "unstressed":
                                # Проверяем, является ли последняя фонема гласной
                                if phoneme_list:
                                    last_phoneme = phoneme_list[-1]
                                    if last_phoneme in "аоуыэи" or last_phoneme in [
                                        "а",
                                        "о",
                                        "у",
                                        "ы",
                                        "э",
                                        "и",
                                        "е",
                                        "ю",
                                        "я",
                                        "ё",
                                    ]:
                                        # Заменяем последнюю фонему на вариант с отрицанием апострофа
                                        # Find the corresponding processed phoneme and modify it
                                        for j in range(
                                            len(processed_phonemes) - 1, -1, -1
                                        ):
                                            if processed_phonemes[j].startswith(
                                                last_phoneme
                                            ) and not processed_phonemes[j].endswith(
                                                "'"
                                            ):
                                                processed_phonemes[j] = (
                                                    f"{last_phoneme}(?!')"
                                                )
                                                break
                                        phoneme_sequence = r"\s+".join(
                                            processed_phonemes
                                        )

                            sequence_regex_parts_internal.append(phoneme_sequence)

                    # Для внутренних частей последовательности используем пробелы
                    regex_parts.append(r"\s+".join(sequence_regex_parts_internal))
            elif kind == "QUANTIFIER":
                raise ValueError(
                    f"Синтаксическая ошибка: квантификатор {value} не может находиться в этой позиции."
                )

        # Соединяем токены с возможным пробелом между ними, так как фонемы в транскрипции разделены пробелами
        return r"\s*".join(regex_parts)


# Для обратной совместимости и простоты использования
def parse_query(query: str) -> Dict[str, Any]:
    parser = DSLParser()
    return parser.parse(query)


if __name__ == "__main__":
    # Демонстрация работы
    parser = DSLParser()

    queries = [
        "дом",
        "д*м",
        "**лог",
        "(гл)(2)",
        "ста (согл)(3)",
        "к*т (зв)(1) (мягк)(0)",
        "уд2",
        "(л,р)(1+)",
        "м(0)",
        "(шип)",
    ]

    print("=== СТАРЫЕ ТЕСТЫ (должны работать как раньше) ===")
    for q in queries:
        try:
            result = parser.parse(q)
            print(f"Запрос: '{q}'")
            print(f"  -> Regex: '{result['sequence_regex']}'")
            print(f"  -> Globals: {result['global_conditions']}")
            print("-" * 20)
        except ValueError as e:
            print(f"Запрос: '{q}' -> ОШИБКА: {e}")
            print("-" * 20)

    # Тест ошибки
    error_query = "а(3-1)"
    try:
        parser.parse(error_query)
    except ValueError as e:
        print(f"Запрос: '{error_query}' -> ОШИБКА: {e}")
        print("-" * 20)

    print("\n=== НОВЫЕ ТЕСТЫ (маркер ! и !!) ===")
    new_queries = [
        "бра!",  # 'а' ударная
        "бро!!",  # 'о' безударная
        "бр(а,о)!",  # 'а' или 'о' ударные
        "бр(а,о)!!",  # 'а' или 'о' безударные
        "бр(гласн)!",  # гласная ударная
        "бр(гласн)!!",  # гласная безударная
        "бра!бо!!",
        "бра!!бо!",
    ]

    for q in new_queries:
        try:
            result = parser.parse(q)
            print(f"Запрос: '{q}'")
            print(f"  -> Regex: '{result['sequence_regex']}'")
            print(f"  -> Globals: {result['global_conditions']}")
            print("-" * 20)
        except ValueError as e:
            print(f"Запрос: '{q}' -> ОШИБКА: {e}")
            print("-" * 20)
