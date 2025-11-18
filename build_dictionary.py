#!/usr/bin/env python3
"""Создать и заполнить `dictionary.db` из `lemma40_tables.json`.

Этот скрипт собирает леммы и информацию о частях речи из `lemma40_tables.json`, загружает
доступные транскрипции IPA/кириллицей из `kaikki.org-dictionary-Russian-words.jsonl`,
и записывает записи в `dictionary.db`.
"""
from pathlib import Path
import sqlite3
from typing import Dict, Optional, Tuple

from data_loader import get_pos_tag_map
from database import initialize_database, DB_FILE
from populate_db import load_transcription_data
from transcribe_stress import count_syllables


def build_and_populate():
    # Инициализировать (пересоздать) базу данных и схему таблицы
    initialize_database()

    pos_map = get_pos_tag_map()
    transcription_map = load_transcription_data()

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    words = sorted(set(pos_map.keys()))
    total = 0

    for word in words:
        total += 1
        part_of_speech = None
        frequency = None
        pos_data = pos_map.get(word)
        if pos_data:
            part_of_speech = pos_data[0]
            frequency = pos_data[1]

        trans = transcription_map.get(word)
        ipa = trans.get("ipa") if trans else None
        cyrillic = trans.get("cyrillic") if trans else None
        stress = trans.get("stress") if trans else None

        syllable_count = count_syllables(word)

        # Использовать INSERT OR REPLACE, чтобы повторные запуски сохраняли согласованность БД
        cur.execute(
            """
            INSERT OR REPLACE INTO dictionary
            (word, part_of_speech, syllable_count, frequency,
             transcription_ipa, transcription_cyrillic, stress_position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (word, part_of_speech, syllable_count, frequency, ipa, cyrillic, stress),
        )

    conn.commit()
    conn.close()
    print(f"Готово: добавлено/обновлено {total} слов в базу '{DB_FILE}'.")


if __name__ == "__main__":
    build_and_populate()
