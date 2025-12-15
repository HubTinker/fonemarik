import sqlite3
import json
from pathlib import Path
from data_loader import get_pos_tag_map
from transcribe_stress import count_syllables
from database import initialize_database  # Импортируем функцию инициализации
from phoneme_mapper import create_phoneme_letter_mapping
from typing import Dict, Optional, Tuple

DB_FILE = "dictionary.db"

IPA_TO_CYRILLIC: Dict[str, str] = {
    "a": "а",
    "e": "е",
    "i": "и",
    "o": "о",
    "u": "у",
    "ə": "а",
    "ɐ": "а",
    "ɛ": "э",
    "ɪ": "и",
    "ɔ": "о",
    "ʊ": "у",
    "ʉ": "у",
    "ɨ": "ы",
    "æ": "а",
    "ɵ": "о",
    "b": "б",
    "d": "д",
    "f": "ф",
    "g": "г",
    "k": "к",
    "l": "л",
    "m": "м",
    "n": "н",
    "p": "п",
    "r": "р",
    "s": "с",
    "t": "т",
    "v": "в",
    "z": "з",
    "ʃ": "ш",
    "ʒ": "ж",
    "x": "х",
    "j": "й",
    "ts": "ц",
    "tʃ": "ч",
    "ɕ": "щ",
    "ʂ": "ш",
    "ʐ": "ж",
    "c": "ц",
    "t͡s": "ц",
    "t͡ɕ": "ч",
    "d͡z": "дз",
    "ɡ": "г",
    "lʲ": "ль",
    "nʲ": "нь",
    "tʲ": "ть",
    "dʲ": "дь",
    "sʲ": "сь",
    "zʲ": "зь",
    "rʲ": "рь",
    "kʲ": "кь",
    "gʲ": "гь",
    "xʲ": "хь",
    "ɫ": "л",
    "ʲ": "ь",
    "ː": "",
    "ˈ": "",
    "ˌ": "",
    "(": "",
    ")": "",
    "[": "",
    "]": "",
}
VOWELS_CYRILLIC = "аеёиоуыэюя"


def get_stress_sound_cyrillic(ipa: str) -> Optional[str]:
    """
    Определяет ударный звук (гласный) из IPA транскрипции и конвертирует в кириллицу.
    """
    if not ipa or "ˈ" not in ipa:
        return None

    # Находим позицию ударения
    stress_pos = ipa.find("ˈ")

    # Ищем гласный звук сразу после знака ударения
    ipa_vowels = {k for k, v in IPA_TO_CYRILLIC.items() if v in VOWELS_CYRILLIC}

    # Итерируемся по символам после знака ударения
    # Учитываем, что символы IPA могут быть многобуквенными (например, 't͡s')
    i = stress_pos + 1
    while i < len(ipa):
        # Проверяем на многобуквенные символы
        for length in range(3, 0, -1):
            char = ipa[i : i + length]
            if char in ipa_vowels:
                return IPA_TO_CYRILLIC.get(char)
        i += 1

    return None


def transcribe_ipa_to_cyrillic(ipa: str) -> Tuple[Optional[str], Optional[int]]:
    if not ipa:
        return None, None
    stress_syllable = None
    stress_mark = "ˈ"
    ipa_vowels = {k for k, v in IPA_TO_CYRILLIC.items() if v in VOWELS_CYRILLIC}
    syllable_count_total = sum(1 for char in ipa if char in ipa_vowels)
    if stress_mark in ipa:
        stress_pos = ipa.find(stress_mark)
        syllables_before_stress = sum(
            1 for char in ipa[:stress_pos] if char in ipa_vowels
        )
        stress_syllable = syllables_before_stress + 1
    elif syllable_count_total == 1:
        stress_syllable = 1

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


# --- Новая функция для загрузки данных транскрипции ---


def load_transcription_data() -> Dict[str, Dict]:
    """
    Загружает данные из kaikki.org-dictionary-Russian-words.jsonl
    и возвращает словарь с данными для транскрипции.
    """
    transcription_map = {}
    jsonl_file = Path("kaikki.org-dictionary-Russian-words.jsonl")
    if not jsonl_file.exists():
        print(f"Файл {jsonl_file} не найден. Данные о транскрипции не будут загружены.")
        return {}

    with jsonl_file.open("r", encoding="utf-8") as f_in:
        for line in f_in:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            word = data.get("word")
            sounds = data.get("sounds", [])
            if not word or not sounds:
                continue

            if word.lower() in transcription_map:
                continue

            for sound_entry in sounds:
                ipa = sound_entry.get("ipa")
                if not ipa:
                    continue

                ipa_clean = ipa.strip("[]/").replace("..", "")
                cyrillic_trans, stress_syl = transcribe_ipa_to_cyrillic(ipa_clean)

                if cyrillic_trans:
                    transcription_map[word.lower()] = {
                        "ipa": ipa,
                        "cyrillic": cyrillic_trans,
                        "stress": stress_syl,
                    }
                    break
    return transcription_map


# --- Обновленная функция populate_database ---


def populate_database():
    """
    Заполняет базу данных словами и всей связанной информацией.
    """
    # Сначала инициализируем (или пересоздаем) базу данных и таблицу
    initialize_database()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    pos_map = get_pos_tag_map()
    transcription_map = load_transcription_data()
    # Получаем слова напрямую из карты частей речи, которая читает lemma40_tables.json
    words = list(pos_map.keys())

    print(f"Найдено {len(words)} слов для добавления в базу данных...")

    for word in words:
        # Данные о части речи и частоте
        pos_data = pos_map.get(word.lower())
        part_of_speech = pos_data[0] if pos_data else None
        frequency = pos_data[1] if pos_data else None

        # Данные о транскрипции
        trans_data = transcription_map.get(word.lower())
        ipa = trans_data.get("ipa") if trans_data else None
        cyrillic = trans_data.get("cyrillic") if trans_data else None
        stress = trans_data.get("stress") if trans_data else None

        # Извлекаем ударный звук в кириллице
        stress_sound = get_stress_sound_cyrillic(ipa) if ipa else None

        # Заменяем 'None' на реальный NULL для базы данных
        if ipa == "None":
            ipa = None
        if cyrillic == "None":
            cyrillic = None

        # Количество слогов
        syllable_count = count_syllables(word)

        # --- Новая логика для создания списка фонем и mapping'а ---
        phonemes_list_str = None
        phoneme_to_letter_map_json = None

        if cyrillic:
            sounds = []
            i = 0
            while i < len(cyrillic):
                # Проверяем, является ли следующий символ апострофом (знак мягкости)
                if i + 1 < len(cyrillic) and cyrillic[i + 1] == "'":
                    sounds.append(cyrillic[i : i + 2])
                    i += 2
                # Обрабатываем сочетания согласной с мягким знаком как мягкую согласную
                elif (
                    i + 1 < len(cyrillic)
                    and cyrillic[i + 1] == "ь"
                    and cyrillic[i] in "бвгджзйклмнпрстфхцчшщ"
                ):
                    sounds.append(
                        cyrillic[i] + "'"
                    )  # Преобразуем в формат 'б', 'в'' и т.д.
                    i += 2
                # 'ь' и 'ъ' не являются самостоятельными фонемами в данном контексте (если не идут после согласной)
                elif cyrillic[i] not in "ьъ":
                    sounds.append(cyrillic[i])
                    i += 1
                else:
                    i += 1
            phonemes_list_str = " ".join(sounds)

            # Создаем mapping между фонемами и буквами
            phoneme_to_letter_map_json = create_phoneme_letter_mapping(
                word, phonemes_list_str
            )
        # --- Конец новой логики ---

        try:
            cursor.execute(
                """
                INSERT INTO dictionary (word, part_of_speech, syllable_count, frequency,
                                        transcription_ipa, transcription_cyrillic, stress_position, 
                                        stress_sound, phonemes_list, phoneme_to_letter_map)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    word,
                    part_of_speech,
                    syllable_count,
                    frequency,
                    ipa,
                    cyrillic,
                    stress,
                    stress_sound,
                    phonemes_list_str,
                    phoneme_to_letter_map_json,
                ),
            )
        except sqlite3.IntegrityError:
            print(f"Слово '{word}' уже есть в базе данных. Обновляем...")
            cursor.execute(
                """
                UPDATE dictionary
                SET part_of_speech = ?, syllable_count = ?, frequency = ?,
                    transcription_ipa = ?, transcription_cyrillic = ?, stress_position = ?, 
                    stress_sound = ?, phonemes_list = ?, phoneme_to_letter_map = ?
                WHERE word = ?
            """,
                (
                    part_of_speech,
                    syllable_count,
                    frequency,
                    ipa,
                    cyrillic,
                    stress,
                    stress_sound,
                    phonemes_list_str,
                    phoneme_to_letter_map_json,
                    word,
                ),
            )

    conn.commit()
    conn.close()
    print(f"База данных '{DB_FILE}' успешно заполнена/обновлена {len(words)} словами.")


def update_phonemes_with_stress():
    """
    Обновляет столбец phonemes_list в таблице dictionary, добавляя ударение к гласной после знака ˈ в IPA.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Получаем все записи из таблицы
    cursor.execute("SELECT id, word, transcription_ipa FROM dictionary")
    records = cursor.fetchall()

    print(f"Найдено {len(records)} записей для обновления phonemes_list...")

    for record_id, word, transcription_ipa in records:
        if transcription_ipa:
            # Извлекаем кириллическую транскрипцию
            cursor.execute("SELECT transcription_cyrillic FROM dictionary WHERE id = ?", (record_id,))
            cyrillic_result = cursor.fetchone()
            if cyrillic_result and cyrillic_result[0]:
                cyrillic_transcription = cyrillic_result[0]

                # Преобразуем IPA в новый список фонем с ударением
                new_phonemes_list = convert_ipa_to_phonemes_with_stress(
                    transcription_ipa, cyrillic_transcription
                )

                # Обновляем поле phonemes_list
                cursor.execute(
                    "UPDATE dictionary SET phonemes_list = ? WHERE id = ?",
                    (new_phonemes_list, record_id)
                )

    conn.commit()
    conn.close()
    print("Обновление phonemes_list завершено.")


def convert_ipa_to_phonemes_with_stress(ipa_transcription: str, cyrillic_transcription: str) -> str:
    """
    Преобразует IPA транскрипцию в список фонем, добавляя ударение к гласной после знака ˈ.
    Также обрабатывает мягкие согласные (например, lʲ -> л').
    """
    # Удаляем скобки и слэши из IPA
    clean_ipa = ipa_transcription.strip("[]/").replace("..", "")
    
    # Словарь для преобразования IPA в кирилические фонемы
    ipa_to_phoneme = {
        "a": "а",
        "e": "е",
        "i": "и",
        "o": "о",
        "u": "у",
        "ə": "а",
        "ɐ": "а",
        "ɛ": "э",
        "ɪ": "и",
        "ɔ": "о",
        "ʊ": "у",
        "ʉ": "у",
        "ɨ": "ы",
        "æ": "а",
        "ɵ": "о",
        "b": "б",
        "d": "д",
        "f": "ф",
        "g": "г",
        "k": "к",
        "l": "л",
        "m": "м",
        "n": "н",
        "p": "п",
        "r": "р",
        "s": "с",
        "t": "т",
        "v": "в",
        "z": "з",
        "ʃ": "ш",
        "ʒ": "ж",
        "x": "х",
        "j": "й",
        "ts": "ц",
        "tʃ": "ч",
        "ɕ": "щ",
        "ʂ": "ш",
        "ʐ": "ж",
        "c": "ц",
        "t͡s": "ц",
        "t͡ɕ": "ч",
        "d͡z": "дз",
        "ɡ": "г",
        "lʲ": "л'",
        "nʲ": "н'",
        "tʲ": "т'",
        "dʲ": "д'",
        "sʲ": "с'",
        "zʲ": "з'",
        "rʲ": "р'",
        "kʲ": "к'",
        "gʲ": "г'",
        "xʲ": "х'",
        "ɫ": "л",
        "ʲ": "ь",
        "ː": "",
        "ˈ": "ˈ",  # Оставляем знак ударения для определения позиции
        "ˌ": "",
        "(": "",
        ")": "",
        "[": "",
        "]": "",
    }

    # Сортируем ключи по длине в обратном порядке для корректного поиска
    sorted_keys = sorted(ipa_to_phoneme.keys(), key=len, reverse=True)

    # Ищем позицию ударения
    stress_pos = clean_ipa.find("ˈ")
    
    # Преобразуем IPA в фонемы
    phonemes = []
    i = 0
    while i < len(clean_ipa):
        # Пропускаем знак ударения, но отмечаем его позицию
        if clean_ipa[i] == "ˈ":
            i += 1
            continue
            
        match = None
        for key in sorted_keys:
            if clean_ipa.startswith(key, i):
                match = key
                break

        if match:
            phoneme = ipa_to_phoneme[match]
            # Если это гласный звук сразу после ударения, добавляем апостроф
            if stress_pos != -1 and i == stress_pos + 1 and phoneme in "аеёиоуыэюя":
                phoneme = phoneme + "'"
            phonemes.append(phoneme)
            i += len(match)
        else:
            # Если совпадения не найдено, просто пропускаем символ
            i += 1

    # Удаляем пустые строки из результата
    phonemes = [p for p in phonemes if p]

    return " ".join(phonemes)


if __name__ == "__main__":
    # populate_database()
    update_phonemes_with_stress()
