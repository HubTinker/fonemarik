# -*- coding: utf-8 -*-

"""
state_manager.py: Управляет состоянием приложения, поиском и результатами.

Этот модуль содержит класс StateManager, который выступает в качестве центрального
компонента для управления данными и бизнес-логикой приложения "Фонемарик".
Он инкапсулирует логику обработки поисковых запросов, фильтрации
и взаимодействия с базой данных, отделяя ее от UI (presentation_layer).

Основные обязанности:
- Хранение и обновление состояния фильтров поиска.
- Запуск асинхронного поиска при изменении фильтров.
- Хранение результатов поиска и данных сборника.
- Предоставление сигналов для обновления интерфейса.

Зависимости:
- PyQt6.QtCore (для сигналов и QObject)
- search (для функции find_words)
- pos_mapper

Пример использования:
    # В главном классе приложения
    self.state_manager = StateManager()
    self.state_manager.search_results_updated.connect(self.update_results_table)
    self.state_manager.status_updated.connect(self.update_status_bar)

    # При изменении фильтра в UI
    self.query_input.textChanged.connect(self.state_manager.set_query)
"""

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from typing import Optional, Set

from search import find_words
from pos_mapper import POS_NAME_TO_TAG
from dictionary_updater import update_dictionary_from_file
from database import DB_FILE
import sqlite3


class StateManager(QObject):
    """
    Управляет состоянием приложения, включая фильтры, поиск и результаты.
    """

    # --- Сигналы для обновления UI ---
    search_results_updated = pyqtSignal(list)
    pagination_updated = pyqtSignal(int, int)  # current_page, total_pages
    collection_changed = pyqtSignal(set)  # Передает полный набор ID
    word_added_to_collection = pyqtSignal(int)  # Передает word_id
    word_removed_from_collection = pyqtSignal(int)  # Передает word_id
    collection_cleared = pyqtSignal()
    status_updated = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        Инициализирует StateManager.
        """
        super().__init__(parent)

        # --- Состояние фильтров ---
        self.query = ""
        self.position = "any"
        self.search_in = "phonemes"
        self.part_of_speech = None
        self.syllable_count = None
        self.stress_sound = None
        self.sort_by_frequency = False
        self.phonological_hardness = None  # 'hard' or 'soft'
        self.phonological_voicing = None  # 'voiced' or 'voiceless'
        self.exclude_sounds = None

        # --- Состояние пагинации ---
        self.current_page = 1
        self.page_size = 25  # Изменено значение по умолчанию
        self.total_pages = 1

        # --- Данные ---
        self.search_results = []  # Полный список результатов
        self.collection_word_ids: Set[int] = set()

        # --- Таймер для отложенного поиска (debouncing) ---
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.execute_search)

    def set_query(self, query: str):
        """Обновляет поисковый запрос и запускает таймер поиска."""
        self.query = query
        self.start_search_timer()

    def set_position(self, positions: list[str] | None):
        """Обновляет фильтр позиции в слове на основе списка выбранных кнопок."""
        if positions:
            # Преобразуем список ['start', 'end'] в строку "start,end"
            self.position = ",".join(positions)
        else:
            # Если ничего не выбрано, ищем в любом месте
            self.position = "any"
        self.start_search_timer()

    def set_search_in(self, search_in_text: str):
        """Обновляет область поиска (транскрипция или слово)."""
        search_in_map = {"В транскрипции": "phonemes", "В слове": "word"}
        self.search_in = search_in_map.get(search_in_text, "phonemes")
        self.start_search_timer()

    def set_part_of_speech(self, pos_text: str):
        """Обновляет фильтр по части речи."""
        if pos_text == "Все части речи":
            self.part_of_speech = None
        else:
            self.part_of_speech = POS_NAME_TO_TAG.get(pos_text)
        self.start_search_timer()

    def set_syllable_count(self, counts: list | None):
        """Обновляет фильтр по количеству слогов."""
        self.syllable_count = counts
        self.start_search_timer()

    def set_sort_by_frequency(self, is_sorted: bool):
        """Устанавливает флаг сортировки по частоте."""
        self.sort_by_frequency = is_sorted
        self.start_search_timer()

    def set_stress_sound(self, stress_sound: str):
        """Устанавливает фильтр по ударному звуку."""
        if stress_sound == "Все ударения":
            self.stress_sound = None
        else:
            self.stress_sound = stress_sound
        self.start_search_timer()

    def set_phonological_hardness(self, hardness: Optional[str]):
        """Устанавливает фильтр по твердости/мягкости ('hard', 'soft', None)."""
        self.phonological_hardness = hardness
        self.start_search_timer()

    def set_phonological_voicing(self, voicing: Optional[str]):
        """Устанавливает фильтр по звонкости/глухости ('voiced', 'voiceless', None)."""
        self.phonological_voicing = voicing
        self.start_search_timer()

    def set_exclude_sounds(self, sounds: str):
        """Обновляет фильтр исключаемых звуков."""
        self.exclude_sounds = sounds.strip() if sounds else None
        self.start_search_timer()

    def set_page_size(self, size: int):
        """Устанавливает новый размер страницы и пересчитывает пагинацию."""
        if size > 0:
            self.page_size = size
            self.current_page = 1  # Сбрасываем на первую страницу
            self.total_pages = max(
                1, (len(self.search_results) - 1) // self.page_size + 1
            )
            self._emit_paginated_results()

    def reset_filters(self):
        """Сбрасывает все фильтры в состояние по умолчанию и очищает результаты."""
        self.query = ""
        self.position = "any"
        self.search_in = "phonemes"
        self.part_of_speech = None
        self.syllable_count = None
        self.stress_sound = None
        self.sort_by_frequency = False
        self.phonological_hardness = None
        self.phonological_voicing = None
        self.exclude_sounds = None
        self.current_page = 1
        self.total_pages = 1

        self.search_results = []
        self.search_results_updated.emit([])
        self.pagination_updated.emit(1, 1)
        self.status_updated.emit("Фильтры сброшены. Введите новый запрос.")

    def start_search_timer(self):
        """Перезапускает таймер поиска с задержкой в 300 мс."""
        self.search_timer.start(300)

    def execute_search(self):
        """
        Выполняет поиск на основе текущих фильтров и отправляет сигнал
        с результатами.
        """
        if not self.query.strip():
            self.status_updated.emit("Пожалуйста, введите запрос.")
            self.search_results = []
            self.search_results_updated.emit(self.search_results)
            self.pagination_updated.emit(1, 1)
            return

        self.status_updated.emit("Поиск...")
        try:
            self.search_results = find_words(
                query=self.query.strip(),
                position=self.position,
                search_in=self.search_in,
                part_of_speech=self.part_of_speech,
                syllable_count=self.syllable_count,
                sort_by_frequency=self.sort_by_frequency,
                stress_sound=self.stress_sound,
                phonological_hardness=self.phonological_hardness,
                phonological_voicing=self.phonological_voicing,
                exclude_sounds=self.exclude_sounds,
            )
            self.current_page = 1
            self.total_pages = max(
                1, (len(self.search_results) - 1) // self.page_size + 1
            )
            self._emit_paginated_results()
            self.status_updated.emit(f"Найдено: {len(self.search_results)}")

        except Exception as e:
            self.search_results = []
            self.search_results_updated.emit(self.search_results)
            self.pagination_updated.emit(1, 1)
            self.status_updated.emit(f"Ошибка: {str(e)}")

    def add_word_to_collection(self, word_data: dict):
        """Добавляет ID слова в сборник и испускает сигнал."""
        word_id = word_data.get("id")
        if word_id is not None and word_id not in self.collection_word_ids:
            self.collection_word_ids.add(word_id)
            self.word_added_to_collection.emit(word_id)
            self.collection_changed.emit(self.collection_word_ids)

    def remove_word_from_collection(self, word_data: dict):
        """Удаляет ID слова из сборника и испускает сигнал."""
        word_id = word_data.get("id")
        if word_id in self.collection_word_ids:
            self.collection_word_ids.remove(word_id)
            self.word_removed_from_collection.emit(word_id)
            self.collection_changed.emit(self.collection_word_ids)

    def clear_collection(self):
        """Очищает сборник."""
        self.collection_word_ids.clear()
        self.collection_cleared.emit()
        self.collection_changed.emit(self.collection_word_ids)

    def is_word_in_collection(self, word_data: dict) -> bool:
        """Проверяет, находится ли слово в сборнике."""
        return word_data.get("id") in self.collection_word_ids

    def _emit_paginated_results(self):
        """Отправляет срез результатов для текущей страницы."""
        start_index = (self.current_page - 1) * self.page_size
        end_index = start_index + self.page_size
        paginated_results = self.search_results[start_index:end_index]
        self.search_results_updated.emit(paginated_results)
        self.pagination_updated.emit(self.current_page, self.total_pages)

    def go_to_page(self, page_number: int):
        """Переходит на указанную страницу, если она существует."""
        if 1 <= page_number <= self.total_pages:
            self.current_page = page_number
            self._emit_paginated_results()

    def go_to_next_page(self):
        """Переходит на следующую страницу."""
        self.go_to_page(self.current_page + 1)

    def go_to_previous_page(self):
        """Переходит на предыдущую страницу."""
        self.go_to_page(self.current_page - 1)

    def run_dictionary_update(self, file_path: str):
        """
        Запускает процесс обновления словаря из файла.
        """
        self.status_updated.emit(f"Обновление словаря из {Path(file_path).name}...")

        conn = None
        try:
            # Создаем новое соединение для этой операции
            conn = sqlite3.connect(DB_FILE)
            update_dictionary_from_file(file_path, conn)
            self.status_updated.emit(
                "Словарь успешно обновлен. Перезапустите поиск для учета изменений."
            )
        except Exception as e:
            self.status_updated.emit(f"Ошибка обновления: {e}")
        finally:
            if conn:
                conn.close()
