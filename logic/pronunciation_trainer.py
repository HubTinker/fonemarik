# -*- coding: utf-8 -*-
"""
Модуль для управления логикой тренировки произношения.
"""

import sqlite3
from thefuzz import fuzz


class PronunciationTrainer:
    """
    Класс для управления состоянием тренировочной сессии: загрузка слов,
    перемещение по ним и отслеживание прогресса.
    """

    def __init__(self, db_path: str):
        """
        Конструктор, принимающий путь к файлу базы данных.

        Args:
            db_path (str): Путь к файлу SQLite.
        """
        self.db_path = db_path

    def _normalize_text(self, text: str) -> str:
        """
        Приводит текст к "нормальной" форме для сравнения.

        - Переводит в нижний регистр.
        - Удаляет начальные и конечные пробелы.
        - Заменяет букву "ё" на "е".

        Args:
            text (str): Входная строка.

        Returns:
            str: Нормализованная строка.
        """
        return text.lower().strip().replace("ё", "е")

    def start_session(self, collection_id: int) -> dict:
        """
        Запускает новую тренировочную сессию.

        Загружает из базы данных все id слов и их тексты для данной коллекции,
        а затем формирует начальное состояние сессии.

        Args:
            collection_id (int): ID коллекции для тренировки.

        Returns:
            dict: Словарь с начальным состоянием сессии.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Загружаем слова из коллекции
        cursor.execute(
            """
            SELECT item.id, item.word, item.normalized_word
            FROM training_collection_items item
            WHERE item.collection_id = ?
            ORDER BY item.id
            """,
            (collection_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        word_ids = [row[0] for row in rows]
        words_data = {row[0]: {"word": row[1], "normalized": row[2]} for row in rows}
        results = {word_id: {"attempts": 0, "success": False} for word_id in word_ids}

        session_state = {
            "collection_id": collection_id,
            "word_ids": word_ids,
            "words_data": words_data,
            "current_index": 0,
            "results": results,
        }

        return session_state

    def check_pronunciation(self, original_word: str, spoken_text: str) -> str:
        """
        Проверяет правильность произнесенного текста с использованием нечеткого сравнения.

        1. Нормализует обе строки (нижний регистр, тримминг, ё -> е).
        2. Вычисляет схожесть с помощью `fuzz.ratio` (расстояние Левенштейна).
        3. Считает результат успешным, если строки идентичны или их схожесть
           превышает заданный порог (85%).

        Args:
            original_word (str): Оригинальное слово.
            spoken_text (str): Текст, произнесенный пользователем.

        Returns:
            str: "ok", если произношение верное, иначе "error".
        """
        norm_original = self._normalize_text(original_word)
        norm_spoken = self._normalize_text(spoken_text)

        if norm_original == norm_spoken:
            return "ok"

        # Используем fuzz.ratio, который возвращает схожесть в процентах
        similarity_ratio = fuzz.ratio(norm_original, norm_spoken)

        # Порог в 85% позволяет игнорировать незначительные ошибки распознавания
        if similarity_ratio > 85:
            return "ok"

        return "error"

    def get_summary(self, session_data: dict) -> dict:
        """
        Возвращает статистику по текущей сессии.

        Args:
            session_data (dict): Данные текущей сессии.

        Returns:
            dict: Словарь со статистикой (total, success_count, total_attempts).
        """
        total_words = len(session_data.get("word_ids", []))
        results = session_data.get("results", {})

        success_count = sum(1 for res in results.values() if res.get("success"))
        total_attempts = sum(res.get("attempts", 0) for res in results.values())

        return {
            "total_words": total_words,
            "success_count": success_count,
            "total_attempts": total_attempts,
        }
