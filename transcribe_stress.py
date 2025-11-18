#!/usr/bin/env python3
"""Транскрибирует русские слова и определяет ударный слог с использованием RusPhonetic.

Принимает файл с одним русским словом в строке (UTF-8) и записывает JSON/NDJSON с
полями: `word`, `transcription` (кириллица, из RusPhonetic), и
`stress_syllable` (индекс слога с основным ударением, начиная с 1, или null).

Скрипт пытается импортировать реализацию RusPhonetic. Если она не
установлена, скрипт объяснит, как установить её.

Использование:
   python transcribe_stress.py -i words.txt -o out.json
   python transcribe_stress.py -i words.txt --ndjson -o out.ndjson

Примечание: измените имя импорта в скрипте, если ваш пакет RusPhonetic предоставляет
другой API. Скрипт пытается использовать общие шаблоны, но настраивается.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import unicodedata
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Any

VOWELS = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"


def count_syllables(word: str) -> int:
    """Считает количество слогов в слове по количеству гласных."""
    return len([char for char in word if char.lower() in VOWELS])


def normalize_text(s: str) -> str:
    """Возвращает нормализованную строку в нижнем регистре, подходящую для поиска.

    Сохраняет символы типа 'й' (который 'и' + бреве), но удаляет метки
    ударения (сочетание акута U+0301 и основная метка ударения U+02C8).
    Функция нормализует к NFD, чтобы удалить только определённые комбинирующие метки,
    затем объединяет в NFC.
    """
    if not s:
        return ""
    # Decompose so we can selectively remove only stress-related marks
    nfd = unicodedata.normalize("NFD", s)
    # Remove combining acute (U+0301) which marks stress, and U+02C8 stress mark
    nfd = nfd.replace("\u0301", "")
    nfd = nfd.replace("\u02c8", "")
    # Recompose to canonical form and lowercase
    recomposed = unicodedata.normalize("NFC", nfd)
    return recomposed.lower()


def stress_from_form(form: str) -> Optional[int]:
    """Возвращает индекс слога (начиная с 1) с комбинированным акутом в `form`, или None.

    Использует разложение NFD для нахождения комбинированного акута U+0301, размещенного после гласной.
    """
    if not form:
        return None
    nfd = unicodedata.normalize("NFD", form)
    comb = "\u0301"
    # indices of base vowels in the decomposed string
    vowel_positions = [i for i, ch in enumerate(nfd) if ch in VOWELS]
    if comb in nfd:
        # find combining acute position
        idx = nfd.find(comb)
        # find previous vowel position before combining
        prev = None
        j = idx - 1
        while j >= 0:
            if nfd[j] in VOWELS:
                prev = j
                break
            j -= 1
        if prev is not None:
            # count which vowel (1-based)
            count = sum(1 for p in vowel_positions if p <= prev)
            return count
    # fallback: if no combining, try to find preceeding stress mark U+02C8 before vowel
    stress_mark = "\u02c8"
    if stress_mark in nfd:
        pos = nfd.index(stress_mark)
        next_v = None
        for p in vowel_positions:
            if p > pos:
                next_v = p
                break
        if next_v is not None:
            count = sum(1 for p in vowel_positions if p <= next_v)
            return count
    return None


def build_mapping_from_jsonl(jsonl_path: Path) -> Dict[str, Dict[str, Any]]:
    """Создаёт отображение в памяти из base_form -> {accented, stress}.

    Для каждого поля `form` в каждой записи JSONL, содержащей кириллический текст,
    мы нормализуем (удаляем комбинирующие метки), чтобы сделать ключ поиска. Первый
    найденный акцентованный вариант сохраняется.
    """
    mapping: Dict[str, Dict[str, Any]] = {}
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            forms = obj.get("forms") or []
            # also consider top-level 'word' field
            maybe_word = obj.get("word")
            if maybe_word:
                forms = [{"form": maybe_word}] + forms

            for f in forms:
                form = f.get("form") if isinstance(f, dict) else f
                if not form or not any(
                    ch >= "а" and ch <= "я" or ch >= "А" and ch <= "Я" for ch in form
                ):
                    continue
                key = normalize_text(form)
                if not key:
                    continue
                if key in mapping:
                    continue
                stress = stress_from_form(form)
                mapping[key] = {"accented": form, "stress": stress}
    return mapping


def create_sqlite_index(jsonl_path: Path, db_path: Path) -> None:
    """Создаёт простой индекс sqlite (key, accented, stress) из файла JSONL."""
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS words(key TEXT PRIMARY KEY, accented TEXT, stress INTEGER)"
    )
    conn.commit()
    inserted = 0
    with jsonl_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            forms = obj.get("forms") or []
            maybe_word = obj.get("word")
            if maybe_word:
                forms = [{"form": maybe_word}] + forms
            for f in forms:
                form = f.get("form") if isinstance(f, dict) else f
                if not form or not any(
                    ch >= "а" and ch <= "я" or ch >= "А" and ch <= "Я" for ch in form
                ):
                    continue
                key = normalize_text(form)
                if not key:
                    continue
                # if exists skip
                try:
                    cur.execute(
                        "INSERT OR IGNORE INTO words(key, accented, stress) VALUES (?, ?, ?)",
                        (key, form, stress_from_form(form)),
                    )
                    inserted += 1
                except Exception:
                    continue
    conn.commit()
    conn.close()
    return


def sqlite_lookup(
    conn: sqlite3.Connection, word: str
) -> Optional[Tuple[str, Optional[int]]]:
    key = normalize_text(word)
    cur = conn.cursor()
    cur.execute("SELECT accented, stress FROM words WHERE key = ?", (key,))
    row = cur.fetchone()
    if not row:
        return None
    return (row[0], row[1])


def load_rusphonetic() -> Callable[[str, Optional[int]], str]:
    """
    Импортирует транскрибатор RusPhonetic и возвращает вызываемый объект.

    Вызываемый объект принимает слово и позицию ударения и возвращает
    фонетическую транскрипцию.
    """
    try:
        from RusPhonetic.phonetic_module import Phonetic

        def transcriber_wrapper(word: str, stress_pos: Optional[int]) -> str:
            # Phonetic требует позицию ударения, если она есть
            return Phonetic(word, stress_pos).get_phonetic()

        return transcriber_wrapper
    except ImportError:
        raise ImportError(
            "Библиотека RusPhonetic не найдена или имеет несовместимую структуру.\n"
            "Установите ее: python -m pip install RusPhonetic"
        )


def detect_stress_syllable(transcription: str) -> Optional[int]:
    """Определяет индекс ударного слога (начиная с 1) из строки транскрипции.

    Используемые эвристики (в порядке):
    - Комбинированный акут U+0301 непосредственно после гласной (например, 'а\u0301')
    - Основная метка ударения U+02C8 (ˈ), размещенная перед ударным слогом
    - Апостроф ASCII (') размещен перед ударным слогом
    - Заглавная гласная по сравнению с другими гласными (редко)

    Возвращает индекс слога (начиная с 1) или None, если не найден.
    """
    if not transcription:
        return None

    # find indices of vowels in the transcription
    vowel_indices = [i for i, ch in enumerate(transcription) if ch in VOWELS]
    if not vowel_indices:
        return None

    # 1) combining acute (placed after the base char)
    comb = "\u0301"
    for i, ch in enumerate(transcription):
        if ch == comb:
            # find previous vowel index
            prev = None
            j = i - 1
            while j >= 0:
                if transcription[j] in VOWELS:
                    prev = j
                    break
                j -= 1
            if prev is not None:
                # count which vowel number this is
                count = sum(1 for idx in vowel_indices if idx <= prev)
                return count

    # 2) primary stress mark U+02C8 (ˈ) before stressed syllable
    stress_char = "\u02c8"
    for mark in (stress_char, "'"):
        if mark in transcription:
            pos = transcription.index(mark)
            # find first vowel after pos
            next_vowel = None
            for vi in vowel_indices:
                if vi > pos:
                    next_vowel = vi
                    break
            if next_vowel is not None:
                count = sum(1 for idx in vowel_indices if idx <= next_vowel)
                return count

    # 3) uppercase vowel heuristic: if one vowel is uppercase while others are lower
    lower_vowels = [ch for ch in transcription if ch in VOWELS and ch.islower()]
    upper_vowels = [ch for ch in transcription if ch in VOWELS and ch.isupper()]
    if upper_vowels and not lower_vowels:
        # all vowels uppercase — can't decide
        return None
    if upper_vowels and len(upper_vowels) == 1:
        # find that vowel index
        for vi in vowel_indices:
            if transcription[vi].isupper():
                count = sum(1 for idx in vowel_indices if idx <= vi)
                return count

    return None


def read_words(path: Path) -> List[str]:
    txt = path.read_text(encoding="utf-8")
    words = [w.strip() for w in txt.splitlines() if w.strip()]
    return words


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Транскрибирует слова и определяет ударный слог"
    )
    parser.add_argument(
            "--input",
            "-i",
            default="words.txt",
            help="Входной файл с одним словом в строке (UTF-8)",
        )
    parser.add_argument(
        "--output",
        "-o",
        default="words_transcribed.json",
        help="Выходной файл (JSON или NDJSON)",
    )
    parser.add_argument(
        "--ndjson",
        action="store_true",
        help="Записать JSON, разделённый символами новой строки (один объект в строке)",
    )
    parser.add_argument(
        "--dict-jsonl",
        default="kaikki.org-dictionary-Russian-words.jsonl",
        help="(опционально) JSONL-словарь с формами, помеченными ударением",
    )
    parser.add_argument(
        "--create-index",
        action="store_true",
        help="Создать индекс sqlite из --dict-jsonl и выйти",
    )
    parser.add_argument(
        "--index-db",
        default="kaikki_index.db",
        help="Путь к БД SQLite для созданного/используемого индекса",
    )
    parser.add_argument(
        "--use-index",
        action="store_true",
        help="Использовать индекс sqlite для поиска (создать, если отсутствует)",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"Входной файл не найден: {in_path}")
        return 2

    try:
        transcriber = load_rusphonetic()
    except ImportError as e:
        print(str(e))
        return 3

    # Prepare dictionary lookup (prefer dictionary stress info if available)
    dict_path = Path(args.dict_jsonl)
    mapping: Optional[Dict[str, Dict[str, Any]]] = None
    sqlite_conn: Optional[sqlite3.Connection] = None
    if dict_path.exists():
        if args.create_index:
            create_sqlite_index(dict_path, Path(args.index_db))
            print(f"Created sqlite index at {args.index_db}")
            return 0
        if args.use_index:
            # ensure index exists, create if missing
            dbp = Path(args.index_db)
            if not dbp.exists():
                print(f"Index DB not found, creating {dbp} from {dict_path} ...")
                create_sqlite_index(dict_path, dbp)
            sqlite_conn = sqlite3.connect(str(dbp))
        else:
            # load into memory (fine for moderate test DBs)
            mapping = build_mapping_from_jsonl(dict_path)

    words = read_words(in_path)
    results = []
    for w in words:
        cleaned_word = w.strip()
        if not cleaned_word:
            continue

        # Сначала определяем ударение
        dict_stress: Optional[int] = None
        dict_accented: Optional[str] = None
        if sqlite_conn:
            row = sqlite_lookup(sqlite_conn, cleaned_word)
            if row:
                dict_accented, dict_stress = row
        elif mapping:
            info = mapping.get(normalize_text(cleaned_word))
            if info:
                dict_accented = info.get("accented")
                dict_stress = info.get("stress")

        if dict_stress is None and dict_accented:
            dict_stress = stress_from_form(dict_accented)

        # Теперь, когда есть ударение, делаем транскрипцию
        trans = None
        try:
            # Передаем слово и позицию ударения
            trans = transcriber(cleaned_word, dict_stress)
        except Exception as e:
            print(f"Ошибка транскрибации для '{cleaned_word}': {e}")

        results.append(
            {
                "word": w,
                "transcription": trans,
                "stress_syllable": dict_stress,
                "syllable_count": count_syllables(w),
                "dict_accented": dict_accented,
            }
        )

    out_path = Path(args.output)
    if args.ndjson:
        with out_path.open("w", encoding="utf-8") as f:
            for obj in results:
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    else:
        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print(f"Записано {out_path} ({len(results)} слов)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
