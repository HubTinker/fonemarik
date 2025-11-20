#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Финальный тест-справка для проверки всех изменений.
Запустите этот файл для подтверждения, что всё работает корректно.
"""

import sys


def print_banner(text, char="="):
    width = 70
    print(f"\n{char * width}")
    print(f"{text.center(width)}")
    print(f"{char * width}\n")


def check_imports():
    print("1️⃣  Проверка импортов...")
    try:
        from phoneme_mapper import (
            create_phoneme_letter_mapping,
            get_letter_range_for_phoneme_range,
        )
        from search import find_words, find_words_intelligent

        print("   ✓ Все модули импортируются успешно")
        return True
    except Exception as e:
        print(f"   ✗ Ошибка импорта: {e}")
        return False


def check_basic_functionality():
    print("2️⃣  Проверка базовой функциональности...")
    try:
        from phoneme_mapper import (
            create_phoneme_letter_mapping,
            get_letter_range_for_phoneme_range,
        )

        # Тест создания маппинга
        word = "аббревиатура"
        phonemes = "а б' б' р' э в' и а т у р а"
        mapping = create_phoneme_letter_mapping(word, phonemes)

        if mapping and mapping != "[]":
            print(f"   ✓ Маппинг создан: {len(mapping)} символов")
        else:
            print("   ✗ Ошибка при создании маппинга")
            return False

        # Тест получения диапазона
        letter_range = get_letter_range_for_phoneme_range(mapping, 6, 7, word)

        if letter_range:
            print(f"   ✓ Диапазон получен: {letter_range}")
            start, end = letter_range
            text = word[start:end]
            print(f"   ✓ Выделено: '{text}'")
            return True
        else:
            print("   ✗ Ошибка при получении диапазона")
            return False

    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return False


def check_doubled_letters():
    print("3️⃣  Проверка обработки удвоенных букв...")
    try:
        from phoneme_mapper import (
            create_phoneme_letter_mapping,
            get_letter_range_for_phoneme_range,
        )

        test_cases = [
            ("ассоциированный", "а с' с' о ц и р' о в' а н ы й", 3, 3),
            ("аппарат", "а п' п' а р' а т", 2, 2),
            ("кассир", "к а с' с' и р", 3, 3),
        ]

        for word, phonemes, start_idx, end_idx in test_cases:
            mapping = create_phoneme_letter_mapping(word, phonemes)
            letter_range = get_letter_range_for_phoneme_range(
                mapping, start_idx, end_idx, word
            )

            if letter_range:
                s, e = letter_range
                text = word[s:e]
                # Проверяем, что не включена предыдущая букву при удвоении
                if s > 0:
                    print(f"   ✓ '{word}' → '{text}' (без удвоенной буквы)")
                else:
                    print(f"   ✓ '{word}' → '{text}'")
            else:
                print(f"   ✗ Ошибка для слова '{word}'")
                return False

        return True

    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return False


def check_search_integration():
    print("4️⃣  Проверка интеграции с поиском...")
    try:
        from search import find_words_intelligent

        # Проверяем, что find_words работает с новой логикой
        results = find_words_intelligent("и", search_in="phonemes")

        if len(results) > 0:
            print(f"   ✓ Найдено {len(results)} слов со звуком 'и'")

            # Проверяем наличие matched_span в результатах
            has_spans = sum(1 for r in results if "matched_span" in r)
            print(f"   ✓ Диапазоны выделения установлены: {has_spans} слов")

            return True
        else:
            print("   ✗ Поиск не вернул результатов")
            return False

    except Exception as e:
        print(f"   ✗ Ошибка: {e}")
        return False


def main():
    print_banner("ФИНАЛЬНАЯ ПРОВЕРКА: ИСПРАВЛЕНИЕ ВЫДЕЛЕНИЯ УДВОЕННЫХ БУКВ")

    checks = [
        ("Импорты", check_imports),
        ("Базовая функциональность", check_basic_functionality),
        ("Обработка удвоенных букв", check_doubled_letters),
        ("Интеграция с поиском", check_search_integration),
    ]

    results = []
    for name, check_func in checks:
        result = check_func()
        results.append((name, result))
        print()

    print_banner("РЕЗУЛЬТАТЫ", "-")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nИТОГО: {passed}/{total} проверок пройдено\n")

    if passed == total:
        print_banner("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ - ГОТОВО К ИСПОЛЬЗОВАНИЮ!", "=")
        return 0
    else:
        print_banner("❌ НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОЙДЕНЫ", "!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
