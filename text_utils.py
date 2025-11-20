# -*- coding: utf-8 -*-

"""
Модуль со вспомогательными утилитами для форматирования текста.
"""

VOWELS = "аеёиоуыэюя"
STRESS_MARK = "\u0301"  # Combining Acute Accent
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
# Это нужно для определения согласных букв.
# Чтобы избежать циклического импорта, мы не импортируем phonology_rules,
# а определяем согласные здесь по остаточному принципу.
ALL_CONSONANT_LETTERS = "бвгджзйклмнпрстфхцчшщ"


def text_to_phonemes(text_part: str) -> list[str]:
    """
    Интеллектуально обрабатывает текстовую часть запроса, преобразуя её
    в последовательность фонем.
    """
    phonemes = []
    i = 0
    n = len(text_part)

    consonant_letters = set(ALL_CONSONANT_LETTERS)

    while i < n:
        char = text_part[i]

        if char in consonant_letters:
            # Смотрим на следующий символ для определения мягкости
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

            phonemes.append(char)
            i += 1

        elif char in VOWEL_LETTER_TO_PHONEME:
            phonemes.append(VOWEL_LETTER_TO_PHONEME[char])
            i += 1

        elif char == "'":
            if phonemes:
                last_phoneme = phonemes[-1]
                if last_phoneme in consonant_letters and not last_phoneme.endswith("'"):
                    phonemes[-1] = f"{last_phoneme}'"
            i += 1

        else:
            i += 1

    return phonemes


def syllabify_word(word: str) -> list[str]:
    """
    Делит слово на слоги по простому правилу: каждый слог содержит одну гласную.
    Согласные примыкают к последующей гласной.
    """
    if not word:
        return []

    syllables = []
    current_syllable = ""
    vowels = "аеёиоуыэюя"

    for char in word:
        current_syllable += char
        if char.lower() in vowels:
            syllables.append(current_syllable)
            current_syllable = ""

    if current_syllable:
        if syllables:
            syllables[-1] += current_syllable
        else:
            syllables.append(current_syllable)

    # Объединяем слоги, которые оказались разделены, но не имеют гласных
    # Например, "взгляд" -> ["в", "згляд"] -> ["взгляд"]
    final_syllables = []
    buffer = ""
    for i, syllable in enumerate(syllables):
        # Если в слоге нет гласной (кроме последнего слога)
        if not any(c in vowels for c in syllable.lower()) and i < len(syllables) - 1:
            buffer += syllable
        else:
            final_syllables.append(buffer + syllable)
            buffer = ""

    if buffer:
        final_syllables.append(buffer)

    return final_syllables


def format_word_with_stress(word: str, stress_position: int) -> str:
    """
    Добавляет знак ударения в слово на основе номера ударной гласной.
    Версия 2.0: Игнорирует HTML-теги при подсчете гласных.

    Знак ударения ставится *после* ударной гласной.

    Args:
        word: Слово для форматирования (может содержать HTML-теги).
        stress_position: Номер ударной гласной (1-based).
                         Если 0 или None, ударение не ставится.

    Returns:
        Слово с расставленным ударением.
    """
    if not stress_position or stress_position == 0:
        return word

    vowel_count = 0
    in_tag = False
    for i, char in enumerate(word):
        if char == "<":
            in_tag = True
            continue
        elif char == ">":
            in_tag = False
            continue

        if not in_tag and char.lower() in VOWELS:
            vowel_count += 1
            if vowel_count == stress_position:
                # Вставляем знак ударения после найденной гласной
                return word[: i + 1] + STRESS_MARK + word[i + 1 :]

    return word


if __name__ == "__main__":
    # Тестирование
    print(f"'молоко' (ударение на 3) -> '{format_word_with_stress('молоко', 3)}'")
    print(f"'замок' (ударение на 2) -> '{format_word_with_stress('замок', 2)}'")
    print(f"'кошка' (ударение на 1) -> '{format_word_with_stress('кошка', 1)}'")
    print(f"'он' (ударение на 1) -> '{format_word_with_stress('он', 1)}'")
    print(f"'йогурт' (ударение на 1) -> '{format_word_with_stress('йогурт', 1)}'")
    print(f"'нет ударения' (0) -> '{format_word_with_stress('безударное', 0)}'")

    # Тестирование syllabify_word
    print("\n--- Тестирование syllabify_word ---")
    test_words = ["молоко", "кошка", "взгляд", "программа", "аорта"]
    for w in test_words:
        print(f"'{w}' -> {syllabify_word(w)}")
