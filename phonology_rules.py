# -*- coding: utf-8 -*-

"""
Модуль для определения фонологических правил русского языка.

Здесь содержатся словари, классифицирующие звуки (в кириллической транскрипции)
по их основным характеристикам: звонкость/глухость и твёрдость/мягкость.
"""

# Классификация согласных по звонкости/глухости
VOICED_CONSONANTS = {
    "б", "б'", "в", "в'", "г", "г'", "д", "д'", "ж", "з", "з'", 
    "й", "л", "л'", "м", "м'", "н", "н'", "р", "р'"
}

VOICELESS_CONSONANTS = {
    "п", "п'", "ф", "ф'", "к", "к'", "т", "т'", "ш", "с", "с'", "х", "х'", "ц", "ч'"
}

# Классификация согласных по твёрдости/мягкости
# Звуки, которые всегда твёрдые или всегда мягкие, включены для полноты.
HARD_CONSONANTS = {
    "б", "в", "г", "д", "ж", "з", "к", "л", "м", "н", "п", "р", "с", "т", "ф", "х", "ц", "ш"
}

SOFT_CONSONANTS = {
    "б'", "в'", "г'", "д'", "з'", "й", "к'", "л'", "м'", "н'", "п'", "р'", "с'", "т'", "ф'", "х'", "ч'"
}


# --- Полные наборы фонем ---

# Все согласные
ALL_CONSONANTS = VOICED_CONSONANTS | VOICELESS_CONSONANTS

# Все гласные (включая ударные и безударные варианты, если они есть в транскрипции)
# Для простоты здесь только базовые гласные
VOWELS = {"а", "о", "у", "ы", "э", "и"}


def get_phoneme_properties(phoneme: str) -> dict:
    """
    Возвращает словарь со свойствами фонемы.

    Args:
        phoneme: Фонема (звук) в кириллической транскрипции.

    Returns:
        Словарь со свойствами 'voicing' (звонкость) и 'softness' (мягкость).
    """
    properties = {
        "voicing": None,
        "softness": None
    }

    # Определяем звонкость/глухость
    if phoneme in VOICED_CONSONANTS:
        properties["voicing"] = "voiced"
    elif phoneme in VOICELESS_CONSONANTS:
        properties["voicing"] = "voiceless"

    # Определяем твёрдость/мягкость
    if phoneme in HARD_CONSONANTS:
        properties["softness"] = "hard"
    elif phoneme in SOFT_CONSONANTS:
        properties["softness"] = "soft"
        
    return properties

if __name__ == '__main__':
    # Примеры использования
    test_phonemes = ["д", "т", "д'", "т'", "ж", "ш", "й", "а"]
    for p in test_phonemes:
        props = get_phoneme_properties(p)
        print(f"Фонема '{p}': Звонкость - {props['voicing']}, Мягкость - {props['softness']}")
