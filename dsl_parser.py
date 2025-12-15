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

# Константы для интеллектуальной обработки текста
SOFTENING_VOWELS = {"я", "ё", "ю", "и", "е"}
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
YOTATED_VOWELS = {"я": "а", "ё": "о", "ю": "у", "е": "э"}

TAG_MAP = {
    "гласн": VOWELS,
    "согл": ALL_CONSONANTS,
    "тверд": HARD_CONSONANTS,
    "мягк": SOFT_CONSONANTS,
    "звонк": VOICED_CONSONANTS,
    "глух": VOICELESS_CONSONANTS,
    "шип": "жчшщ",
    "сон": "йлмнр",
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
    consonant_letters = {p.replace("'", "") for p in ALL_CONSONANTS}

    while i < n:
        char = text_part[i]
        if char in consonant_letters:
            if i + 1 < n:
                next_char = text_part[i + 1]
                if next_char == "ь":
                    phonemes.append(f"{char}'")
                    i += 2
                    continue
                elif next_char in SOFTENING_VOWELS:
                    phonemes.append(f"{char}'")
                    phonemes.append(VOWEL_LETTER_TO_PHONEME[next_char])
                    i += 2
                    continue
                elif next_char == "ъ":
                    phonemes.append(char)
                    i += 2
                    continue
            if f"{char}'" in SOFT_CONSONANTS:
                phonemes.append(f"({char}'|{char})")
            else:
                phonemes.append(char)
            i += 1
        elif char in VOWEL_LETTER_TO_PHONEME:
            is_yotated_position = not phonemes or phonemes[-1] in VOWELS
            if char in YOTATED_VOWELS and is_yotated_position:
                phonemes.append("й")
                phonemes.append(YOTATED_VOWELS[char])
            else:
                phonemes.append(VOWEL_LETTER_TO_PHONEME[char])
            i += 1
        elif char == "'":
            if (
                phonemes
                and not phonemes[-1].endswith("'")
                and not phonemes[-1].startswith("(")
            ):
                phonemes[-1] = f"{phonemes[-1]}'"
            i += 1
        else:
            i += 1

    processed_phonemes = []
    for phoneme in phonemes:
        if phoneme.startswith("("):
            parts = phoneme.strip("()").split("|")
            processed_parts = [
                p[:-1] + r"\s*'" if p.endswith("'") else p for p in parts
            ]
            processed_phonemes.append(f"({'|'.join(processed_parts)})")
        elif phoneme.endswith("'"):
            processed_phonemes.append(phoneme[:-1] + r"\s*'")
        else:
            processed_phonemes.append(phoneme)
    return r"\s+".join(processed_phonemes)


# Унифицированный токенизатор
TOKEN_SPECIFICATION = [
    ("DSL_CONSTRUCT", r"(\([^\)]+\))|(\*\*?)|(\.)|(!{1,2})|(уд\d+)"),
    ("TEXT", r"([а-яёыА-ЯЁЫ']+)"),
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
        """
        query = query.lower().replace("ё", "е")
        tokens = self._tokenize(query)
        sequence_tokens, global_conditions = self._distribute_tokens(tokens)
        sequence_regex = self._build_sequence_regex(sequence_tokens)
        return {
            "sequence_regex": sequence_regex,
            "global_conditions": global_conditions,
        }

    def _tokenize(self, query: str) -> List[Tuple[str, str]]:
        """Разбивает строку на токены."""
        return [
            (mo.lastgroup, mo.group())
            for mo in TOKEN_REGEX.finditer(query)
            if mo.lastgroup not in ["SPACE", "ERROR"]
        ]

    def _distribute_tokens(
        self, tokens: List[Tuple[str, str]]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Распределяет токены на 'sequence' и 'global'.
        """
        sequence_tokens = []
        global_conditions = []
        i = 0
        while i < len(tokens):
            kind, value = tokens[i]
            if kind == "DSL_CONSTRUCT":
                if value.startswith("уд"):
                    pos = int(value[2:])
                    if pos <= 0:
                        raise ValueError("Номер слога должен быть > 0.")
                    global_conditions.append(
                        {"type": "STRESS", "value": str(pos), "quantifier": (1, 1)}
                    )
                elif value in ["!", "!!"]:
                    if sequence_tokens:
                        sequence_tokens[-1]["stress"] = (
                            "stressed" if value == "!" else "unstressed"
                        )
                elif value in ["*", "**"]:
                    sequence_tokens.append({"type": "WILDCARD", "value": value})
                elif value == ".":
                    sequence_tokens.append({"type": "WILDCARD", "value": "*"})
                elif value.startswith("(") and value.endswith(")"):
                    content = value[1:-1]
                    # Проверка на квантификатор для глобального условия
                    if i + 1 < len(tokens) and re.fullmatch(
                        r"\(\d+(-(\d+)?)?\+?\)", tokens[i + 1][1]
                    ):
                        quant_value = tokens[i + 1][1]
                        quantifier = self._parse_quantifier(quant_value)
                        global_conditions.append(
                            {"type": "TAG", "value": content, "quantifier": quantifier}
                        )
                        i += 1  # Пропускаем токен квантификатора
                    else:
                        sequence_tokens.append({"type": "TAG", "value": content})
            elif kind == "TEXT":
                sequence_tokens.append({"type": "TEXT", "value": value})
            i += 1
        return sequence_tokens, global_conditions

    def _parse_quantifier(self, value: str) -> Tuple[int, Optional[int]]:
        """Парсит строковое представление квантификатора в кортеж (min, max)."""
        value = value[1:-1]
        if value.endswith("+"):
            min_val = int(value[:-1])
            return (min_val, None)
        if "-" in value:
            min_val, max_val = map(int, value.split("-"))
            if max_val < min_val:
                raise ValueError("Верхняя граница < нижней.")
            return (min_val, max_val)
        val = int(value)
        return (val, val)

    def _build_sequence_regex(self, tokens: List[Dict]) -> str:
        """Строит регулярное выражение из токенов последовательности."""
        regex_parts = []
        for token in tokens:
            kind, value = token["type"], token["value"]
            stress_info = token.get("stress")

            if kind == "TEXT":
                regex_parts.append(_process_text_part(value))
            elif kind == "WILDCARD":
                if value == "*":
                    regex_parts.append(r"[^\s']+")
                elif value == "**":
                    regex_parts.append(r"(?:[^\s']+\s*)*?")
            elif kind == "TAG":
                tag_names = value.split(",")
                phonemes = set()
                for name in tag_names:
                    name = name.strip()
                    if not name:
                        continue
                    if len(name) == 1 and name in "абвгдеёжзийклмнопрстуфхцчшщъыьэюя'":
                        phonemes.add(
                            name[:-1] + r"\s*'" if name.endswith("'") else name
                        )
                    elif name in TAG_MAP:
                        raw_phonemes = TAG_MAP[name]
                        for p in raw_phonemes:
                            phonemes.add(p[:-1] + r"\s*'" if p.endswith("'") else p)
                        if name == "гласн":
                            phonemes.update(
                                {
                                    f"{v[:-1]}\\s*'"
                                    for v in raw_phonemes
                                    if v.endswith("'")
                                }
                            )
                    else:
                        raise ValueError(f"Неизвестный тег: {name}")

                if not phonemes:
                    continue
                group_content = "|".join(sorted(list(phonemes)))

                if stress_info:
                    vowel_phonemes = {
                        p for p in phonemes if p.replace(r"\s*'", "") in "аоуыэиеюя"
                    }
                    other_phonemes = phonemes - vowel_phonemes
                    if stress_info == "stressed":
                        stressed = {
                            p.replace(r"\s*'", "") + r"\s*'" for p in vowel_phonemes
                        }
                        all_alternatives = stressed | other_phonemes
                    else:  # unstressed
                        unstressed = {
                            p.replace(r"\s*'", "") + r"(?!\s*')" for p in vowel_phonemes
                        }
                        all_alternatives = unstressed | other_phonemes
                    if all_alternatives:
                        regex_parts.append(
                            f"({'|'.join(sorted(list(all_alternatives)))})"
                        )
                else:
                    regex_parts.append(f"({group_content})")

        final_regex = r"\s+".join(filter(None, regex_parts))
        return re.sub(r"\s+", " ", final_regex).strip()


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
