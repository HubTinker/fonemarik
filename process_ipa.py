#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Этот скрипт обрабатывает JSONL-файл словаря (например, от kaikki.org),
извлекает IPA-транскрипцию, определяет ударный слог и преобразует
транскрипцию в кириллицу.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any

# Сопоставление символов IPA и кириллицы.
# Это начальный вариант, который может потребовать дополнений.
IPA_TO_CYRILLIC: Dict[str, str] = {
    # Гласные
    'a': 'а', 'e': 'е', 'i': 'и', 'o': 'о', 'u': 'у', 'ə': 'а', 'ɐ': 'а',
    'ɛ': 'э', 'ɪ': 'и', 'ɔ': 'о', 'ʊ': 'у', 'ɨ': 'ы', 'æ': 'э', 'ɵ': 'о',

    # Согласные
    'b': 'б', 'd': 'д', 'f': 'ф', 'g': 'г', 'k': 'к', 'l': 'л', 'm': 'м',
    'n': 'н', 'p': 'п', 'r': 'р', 's': 'с', 't': 'т', 'v': 'в', 'z': 'з',
    'ʃ': 'ш', 'ʒ': 'ж', 'x': 'х', 'j': 'й', 'ts': 'ц', 'tʃ': 'ч', 'ɕ': 'щ',
    'ʂ': 'ш', 'ʐ': 'ж', 'c': 'ц', 't͡s': 'ц', 't͡ɕ': 'ч', 'd͡z': 'дз', 'ɡ': 'г',
    'lʲ': 'ль', 'nʲ': 'нь', 'tʲ': 'ть', 'dʲ': 'дь', 'sʲ': 'сь', 'zʲ': 'зь',
    'rʲ': 'рь', 'kʲ': 'кь', 'gʲ': 'гь', 'xʲ': 'хь',

    # Другие символы
    'ʲ': 'ь',  # Палатализация
    'ː': '',  # Долгота
    'ˈ': '',  # Главное ударение
    'ˌ': '',  # Второстепенное ударение
    '(': '', ')': '', '[': '', ']': ''  # Скобки
}

# Гласные в кириллице для подсчета слогов
VOWELS_CYRILLIC = "аеёиоуыэюя"

def transcribe_ipa_to_cyrillic(ipa: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Транскрибирует IPA-строку в кириллицу и определяет номер ударного слога.
    Args:
        ipa: Строка с IPA-транскрипцией.
    Returns:
        Кортеж (кириллическая транскрипция, номер ударного слога (1-based)).
    """
    if not ipa:
        return None, None

    # Определение ударного слога
    stress_syllable = None
    stress_mark = 'ˈ'
    
    # Сначала считаем общее количество слогов по гласным в IPA
    # (гласные из ключей словаря)
    ipa_vowels = {k for k, v in IPA_TO_CYRILLIC.items() if v in VOWELS_CYRILLIC}
    
    syllable_count_total = sum(1 for char in ipa if char in ipa_vowels)

    if stress_mark in ipa:
        stress_pos = ipa.find(stress_mark)
        # Считаем гласные до знака ударения
        syllables_before_stress = sum(1 for char in ipa[:stress_pos] if char in ipa_vowels)
        stress_syllable = syllables_before_stress + 1
    elif syllable_count_total == 1:
        # Если слог один, он и является ударным
        stress_syllable = 1

    # Транскрипция в кириллицу
    cyrillic_transcription = ""
    i = 0
    # Сортируем ключи по длине в обратном порядке для корректного поиска
    sorted_keys = sorted(IPA_TO_CYRILLIC.keys(), key=len, reverse=True)
    
    while i < len(ipa):
        match = None
        for key in sorted_keys:
            if ipa.startswith(key, i):
                match = key
                break
        
        if match:
            cyrillic_transcription += IPA_TO_CYRILLIC[match]
            i += len(match)
        else:
            # Если совпадения не найдено, просто пропускаем символ
            i += 1
            
    return cyrillic_transcription, stress_syllable


def process_dictionary_file(input_path: Path, output_path: Path):
    """
    Обрабатывает JSONL-файл, извлекает IPA и сохраняет результат.
    """
    results = []
    with input_path.open("r", encoding="utf-8") as f_in:
        for line in f_in:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            word = data.get("word")
            sounds = data.get("sounds", [])
            if not word or not sounds:
                continue

            for sound_entry in sounds:
                ipa = sound_entry.get("ipa")
                if not ipa:
                    continue

                # В файле могут быть разные варианты произношения, берем первый
                # IPA может быть в квадратных скобках
                ipa_clean = ipa.strip("[]/").replace('..', '') # Очистка
                
                cyrillic_trans, stress_syl = transcribe_ipa_to_cyrillic(ipa_clean)

                if cyrillic_trans:
                    results.append({
                        "word": word,
                        "ipa": ipa,
                        "cyrillic_transcription": cyrillic_trans,
                        "stress_syllable": stress_syl
                    })
                    # Обрабатываем только первое найденное произношение для слова
                    break 
    
    with output_path.open("w", encoding="utf-8") as f_out:
        json.dump(results, f_out, ensure_ascii=False, indent=2)

    print(f"Обработка завершена. Результаты сохранены в {output_path}")


if __name__ == "__main__":
    # Пример использования
    # Убедитесь, что файл 'kaikki.org-dictionary-Russian-words.jsonl' находится в том же каталоге
    jsonl_file = Path("kaikki.org-dictionary-Russian-words.jsonl")
    output_file = Path("ipa_processed_words.json")

    if not jsonl_file.exists():
        print(f"Ошибка: Файл '{jsonl_file}' не найден.")
        print("Пожалуйста, убедитесь, что файл словаря находится в правильном месте.")
    else:
        process_dictionary_file(jsonl_file, output_file)
