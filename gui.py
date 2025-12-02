import sys
import sqlite3
import re
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QTextEdit,
    QListView,
    QStylePainter,
    QStyleOptionComboBox,
    QStyle,
)
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWidgets import QCompleter
from search import find_words
from pos_mapper import POS_NAME_TO_TAG, POS_NAMES_LIST
from text_utils import format_word_with_stress
from export_words import export_words  # Импортируем функцию экспорта
from dsl_parser import DSLParser
from dsl_highlighter import DslHighlighter

DB_FILE = "dictionary.db"


# --- Custom Widget for Multi-select ---
class CheckableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view().pressed.connect(self.handle_item_pressed)
        self.setModel(QStandardItemModel(self))
        self._changed = False

    def handle_item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        if item.checkState() == 2:  # Qt.Checked
            item.setCheckState(0)  # Qt.Unchecked
        else:
            item.setCheckState(2)  # Qt.Checked
        self._changed = True

    def hidePopup(self):
        if not self._changed:
            super().hidePopup()
        self._changed = False

    def add_items(self, items):
        for i, text in enumerate(items):
            item = QStandardItem(text)
            item.setFlags(
                Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled
            )
            item.setCheckState(0)  # Qt.Unchecked
            self.model().appendRow(item)

    def checked_items(self):
        checked = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == 2:  # Qt.Checked
                checked.append(item.text())
        return checked

    def paintEvent(self, event):
        # Переопределяем, чтобы показывать выбранные элементы
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)

        checked = self.checked_items()
        if checked:
            opt.currentText = ", ".join(checked)
        else:
            opt.currentText = "Кол-во слогов"

        painter.drawComplexControl(QStyle.CC_ComboBox, opt)
        painter.drawControl(QStyle.CE_ComboBoxLabel, opt)


class FonemarikApp(QWidget):
    def __init__(self):
        super().__init__()
        self.search_results = []  # Хранение результатов поиска
        self.search_in_value = "phonemes"  # Хранение типа поиска для экспорта
        self.dsl_parser = DSLParser()  # Инициализация DSL-парсера
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Поиск по слогам")
        self.setGeometry(100, 100, 400, 300)

        # Layouts
        main_layout = QVBoxLayout()
        input_layout = QHBoxLayout()
        filter_layout = QHBoxLayout()
        action_layout = QHBoxLayout()
        exclude_cat_layout = QHBoxLayout()

        # Widgets
        self.query_input = QLineEdit(self)
        self.query_input.setPlaceholderText(
            "Введите DSL-запрос (например: (гласн)б(согл), дом, уд2)"
        )

        # Настройка автодополнения
        completer_list = [
            "(гласн)",
            "(согл)",
            "(тверд)",
            "(мягк)",
            "(звонк)",
            "(глух)",
            "уд1",
            "уд2",
            "уд3",
            "уд4",
            "уд5",
            "уд6",
            "уд7",
            "уд8",
            "уд9",
            "уд10",
            "а",
            "б",
            "в",
            "г",
            "д",
            "е",
            "ё",
            "ж",
            "з",
            "и",
            "й",
            "к",
            "л",
            "м",
            "н",
            "о",
            "п",
            "р",
            "с",
            "т",
            "у",
            "ф",
            "х",
            "ц",
            "ч",
            "ш",
            "щ",
            "ъ",
            "ы",
            "ь",
            "э",
            "ю",
            "я",
            "б'",
            "в'",
            "г'",
            "д'",
            "з'",
            "к'",
            "л'",
            "м'",
            "н'",
            "п'",
            "р'",
            "с'",
            "т'",
            "ф'",
            "х'",
            "ц'",
            "ч'",
            "ш'",
            "щ'",
        ]
        completer = QCompleter(completer_list, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.query_input.setCompleter(completer)

        # Настройка подсветки синтаксиса
        # self.dsl_highlighter = DslHighlighter(self.query_input.document())

        self.position_combo = QComboBox(self)
        self.position_combo.addItems(
            ["В любом месте", "В начале", "В середине", "В конце"]
        )

        self.search_in_combo = QComboBox(self)
        self.search_in_combo.addItems(["В транскрипции", "В слове"])

        self.pos_combo = QComboBox(self)
        self.pos_combo.addItems(["Все части речи", "Существительное (им.п.)"])

        self.exclude_input = QLineEdit(self)
        self.exclude_input.setPlaceholderText("Исключить конкретные звуки (а, б', ...)")

        self.exclude_hard_cb = QCheckBox("Твердые", self)
        self.exclude_soft_cb = QCheckBox("Мягкие", self)
        self.exclude_voiced_cb = QCheckBox("Звонкие", self)
        self.exclude_voiceless_cb = QCheckBox("Глухие", self)

        self.syllable_count_combo = CheckableComboBox(self)
        self.syllable_count_combo.add_items([str(i) for i in range(1, 11)])

        self.stress_sound_combo = QComboBox(self)
        self.stress_sound_combo.addItem("Все ударения")
        self.update_stress_sounds()

        self.search_button = QPushButton("Найти", self)
        self.search_button.clicked.connect(self.search_syllable)

        self.frequency_sort_checkbox = QCheckBox("Приоритет частотных слов", self)
        self.frequency_sort_checkbox.setToolTip(
            "Сортировать результаты по убыванию частоты встречаемости слова"
        )

        self.export_button = QPushButton(
            "Экспорт в HTML", self
        )  # Обновленный текст кнопки
        self.export_button.clicked.connect(self.export_results)  # Подключаем функцию

        self.export_limit_input = QLineEdit(self)  # Поле для лимита N
        self.export_limit_input.setPlaceholderText("N слов")
        self.export_limit_input.setFixedWidth(60)

        self.output_window = QTextEdit(self)
        self.output_window.setReadOnly(True)

        # Assemble layout
        input_layout.addWidget(self.query_input)
        input_layout.addWidget(self.position_combo)
        input_layout.addWidget(self.search_in_combo)

        filter_layout.addWidget(self.pos_combo)
        filter_layout.addWidget(self.exclude_input)
        filter_layout.addWidget(self.syllable_count_combo)
        filter_layout.addWidget(self.stress_sound_combo)

        exclude_cat_layout.addWidget(self.exclude_hard_cb)
        exclude_cat_layout.addWidget(self.exclude_soft_cb)
        exclude_cat_layout.addWidget(self.exclude_voiced_cb)
        exclude_cat_layout.addWidget(self.exclude_voiceless_cb)

        action_layout.addWidget(self.search_button)
        action_layout.addWidget(self.frequency_sort_checkbox)
        action_layout.addWidget(self.export_button)  # Добавляем кнопку в layout
        action_layout.addWidget(self.export_limit_input)  # Добавляем поле для лимита

        main_layout.addLayout(input_layout)
        main_layout.addLayout(filter_layout)
        main_layout.addLayout(exclude_cat_layout)
        main_layout.addLayout(action_layout)
        main_layout.addWidget(self.output_window)

        self.setLayout(main_layout)

    def update_stress_sounds(self):
        """
        Заполняет выпадающий список уникальными ударными звуками из БД.
        """
        try:
            if not Path(DB_FILE).exists():
                return

            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT stress_sound FROM dictionary WHERE stress_sound IS NOT NULL ORDER BY stress_sound"
            )
            sounds = [row[0] for row in cursor.fetchall()]
            conn.close()

            # Добавляем звуки в комбобокс (начиная со второй позиции)
            current_items = {
                self.stress_sound_combo.itemText(i)
                for i in range(self.stress_sound_combo.count())
            }
            for sound in sounds:
                if sound not in current_items:
                    self.stress_sound_combo.addItem(sound)
        except Exception:
            pass

    def search_syllable(self):
        query = self.query_input.text().strip()
        position = self.position_combo.currentText()
        search_in = self.search_in_combo.currentText()
        part_of_speech = self.pos_combo.currentText()

        # --- Сбор всех исключений ---
        exclude_list = []
        if self.exclude_input.text().strip():
            exclude_list.append(self.exclude_input.text().strip())
        if self.exclude_hard_cb.isChecked():
            exclude_list.append("тверд")
        if self.exclude_soft_cb.isChecked():
            exclude_list.append("мягк")
        if self.exclude_voiced_cb.isChecked():
            exclude_list.append("звонк")
        if self.exclude_voiceless_cb.isChecked():
            exclude_list.append("глух")

        exclude_sounds = ",".join(exclude_list)

        syllable_count = self.syllable_count_combo.checked_items()
        stress_sound = self.stress_sound_combo.currentText()
        if stress_sound == "Все ударения":
            stress_sound = ""

        sort_by_frequency = self.frequency_sort_checkbox.isChecked()

        if not query:
            self.output_window.setText("Пожалуйста, введите запрос.")
            return

        try:
            # Вся логика парсинга теперь инкапсулирована в search.py.
            # GUI просто передает сырой запрос и параметры.
            search_in_map = {"В транскрипции": "phonemes", "В слове": "word"}
            search_in_val = search_in_map.get(search_in, "phonemes")
            query_for_search = query

            # --- Преобразование параметров для `find_words` ---
            pos_map = {
                "В любом месте": "any",
                "В начале": "start",
                "В конце": "end",
                "В середине": "any",  # search.py не поддерживает "середину" как отдельную опцию
            }
            search_pos = pos_map.get(position, "any")

            pos_tag = None
            if part_of_speech != "Все части речи":
                pos_tag = POS_NAME_TO_TAG.get(part_of_speech)

            # Конвертация количества слогов в int, если возможно
            syllables = [int(s) for s in syllable_count if s.isdigit()]
            if not syllables:
                syllables = None

            # Сохраняем тип поиска для экспорта
            self.search_in_value = search_in_val

            # Вызываем функцию поиска
            # `find_words` теперь сама обрабатывает DSL и все условия.
            # `gui.py` больше не должен заниматься парсингом или дополнительной фильтрацией.
            self.search_results = find_words(
                query=query_for_search,
                position=search_pos,
                search_in=search_in_val,
                part_of_speech=pos_tag,
                exclude_sounds=exclude_sounds,
                syllable_count=syllables,
                sort_by_frequency=sort_by_frequency,
            )

            if self.search_results:
                output_text = []
                for row in self.search_results:
                    # Форматируем вывод, чтобы показать всю информацию
                    stress_info = (
                        f" (ударный звук: {row.get('stress_sound', 'N/A')})"
                        if row.get("stress_sound")
                        else ""
                    )
                    frequency_info = f" (частота: {row.get('frequency', 'N/A')})"
                    stressed_word = format_word_with_stress(
                        row["word"], row.get("stress_position")
                    )
                    phoneme_info = (
                        f"\nФонема: {row.get('matched_phonemes', 'N/A')}"
                        if row.get("matched_phonemes")
                        else ""
                    )
                    row_info = f"Слово: {stressed_word}{frequency_info}\nТранскрипция: {row['transcription_cyrillic']}{stress_info}{phoneme_info}\nЧасть речи: {row.get('part_of_speech', 'N/A')}\n\n"
                    output_text.append(row_info)
                self.output_window.setText("".join(output_text))
            else:
                self.output_window.setText(
                    f"Слова не найдены для запроса '{query}' в '{search_in}' в позиции '{position}'."
                )
        except Exception as e:
            self.output_window.setText(f"Произошла ошибка при поиске: {e}")

    def _check_global_conditions(
        self, word_data, global_conditions, exclude_sounds=None
    ):
        """
        Проверяет, удовлетворяет ли слово глобальным условиям DSL-запроса.
        Эта функция должна быть синхронизирована с `_check_global_conditions` в `search.py`.
        """
        phonemes = word_data.get("phonemes_list", "").split()
        if not phonemes:
            return False  # Если нет фонем, нечего проверять

        # 1. Проверка исключенных звуков
        if exclude_sounds:
            from phonology_rules import (
                HARD_CONSONANTS,
                SOFT_CONSONANTS,
                VOICED_CONSONANTS,
                VOICELESS_CONSONANTS,
            )

            EXCLUDE_TAG_MAP = {
                "тверд": HARD_CONSONANTS,
                "мягк": SOFT_CONSONANTS,
                "звонк": VOICED_CONSONANTS,
                "глух": VOICELESS_CONSONANTS,
            }
            sounds_to_exclude = set()
            excluded_items = [
                item.strip() for item in exclude_sounds.lower().split(",")
            ]
            for item in excluded_items:
                sounds_to_exclude.update(EXCLUDE_TAG_MAP.get(item, {item}))

            if not sounds_to_exclude.isdisjoint(phonemes):
                return False

        # 2. Проверка глобальных условий из DSL
        for condition in global_conditions:
            cond_type = condition["type"]
            cond_value = condition["value"]
            min_q, max_q = condition["quantifier"]

            if cond_type == "STRESS":
                stress_pos = int(cond_value)
                if word_data.get("stress_position") != stress_pos:
                    return False
                continue  # Условие по ударению проверено

            # Обработка условий по количеству фонем (LITERAL и TAG)
            target_phonemes = set()
            if cond_type == "LITERAL":
                target_phonemes = {cond_value}
            elif (
                cond_type == "TAG" or cond_type == "SEQUENCE"
            ):  # Добавлена проверка SEQUENCE
                from dsl_parser import TAG_MAP

                # Разбираем значение, которое может быть "согл" или "б,р,(гласн)"
                sub_parts = re.findall(r"[а-яё]+|\([а-яё,]+\)", cond_value)
                for part in sub_parts:
                    if part.startswith("("):
                        content = part[1:-1]
                        # Это может быть как тег, так и перечисление букв
                        items = content.split(",")
                        for item in items:
                            if item in TAG_MAP:
                                target_phonemes.update(TAG_MAP[item])
                            else:
                                target_phonemes.add(item)
                    else:  # Это либо тег, либо литералы
                        if part in TAG_MAP:
                            target_phonemes.update(TAG_MAP[part])
                        else:  # предполагаем, что это просто набор букв
                            target_phonemes.update(list(part))

            if not target_phonemes:
                continue

            count = sum(1 for p in phonemes if p in target_phonemes)

            if not (min_q <= count and (max_q is None or count <= max_q)):
                return False

        return True

    def export_results(self):
        """
        Экспортирует текущие результаты поиска в HTML-файл.
        """
        if not self.search_results:
            print("Нет результатов для экспорта.")
            return

        limit_text = self.export_limit_input.text().strip()
        limit = None
        if limit_text.isdigit():
            limit = int(limit_text)

        # Передаем тип поиска в функцию экспорта
        export_words(self.search_results, self.search_in_value, limit)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = FonemarikApp()
    ex.show()
    sys.exit(app.exec_())
