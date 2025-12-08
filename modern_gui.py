import sys
import sqlite3
from pathlib import Path
from functools import partial
from PyQt6.QtCore import Qt, QAbstractTableModel, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QTableView,
    QHeaderView,
    QLabel,
    QToolButton,
    QSplitter,
    QFrame,
    QStyledItemDelegate,
    QButtonGroup,
    QFileDialog,
)
from PyQt6.QtGui import QAction
from text_utils import format_word_with_stress
from pos_mapper import POS_NAMES_LIST
from state_manager import StateManager
from query_helper import QueryHelperWidget


class WordCollectionModel(QAbstractTableModel):
    """Model for the word collection table"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Используем две структуры: список для порядка, словарь для быстрого доступа
        self.collection_list = []  # Для сохранения порядка и отображения
        self.collection_map = {}  # Для быстрого поиска по word_id
        self.headers = ["", "Запрос", "Слово"]

    def rowCount(self, parent=None):
        return len(self.collection_list)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if not (0 <= row < len(self.collection_list) and 0 <= col < len(self.headers)):
            return None

        word_data = self.collection_list[row]
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return "🗑️"
            elif col == 1:
                return word_data[0]
            elif col == 2:
                return format_word_with_stress(
                    word_data[1]["word"], word_data[1].get("stress_position")
                )
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.headers[section]
        return None

    def add_word(self, query, word_data):
        word_id = word_data.get("id")
        if word_id is None or word_id in self.collection_map:
            return

        row_to_insert = len(self.collection_list)
        self.beginInsertRows(self.index(0, 0).parent(), row_to_insert, row_to_insert)

        data_tuple = (query, word_data)
        self.collection_list.append(data_tuple)
        self.collection_map[word_id] = data_tuple

        self.endInsertRows()

    def remove_word_by_id(self, word_id: int):
        """Удаляет слово по ID, используя быстрый поиск по словарю."""
        if word_id not in self.collection_map:
            return

        # Находим индекс элемента для удаления
        row_to_remove = -1
        for i, (_, data) in enumerate(self.collection_list):
            if data.get("id") == word_id:
                row_to_remove = i
                break

        if row_to_remove != -1:
            self.beginRemoveRows(self.index(0, 0), row_to_remove, row_to_remove)
            del self.collection_list[row_to_remove]
            del self.collection_map[word_id]
            self.endRemoveRows()

    def clear_collection(self):
        self.beginResetModel()
        self.collection_list = []
        self.collection_map = {}
        self.endResetModel()

    def export_to_text(self):
        result = []
        current_query = None
        for query, word_data in self.collection_list:
            if query != current_query:
                if current_query is not None:
                    result.append("-" * 20)
                result.append(f"Запрос: {query}")
                current_query = query
            word = format_word_with_stress(
                word_data["word"], word_data.get("stress_position")
            )
            result.append(word)
        return "\n".join(result)


class WordTableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self.headers = ["+", "Слово", "Транскрипция", "Часть речи", "Слоги", "Частота"]

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if not (0 <= row < len(self._data) and 0 <= col < len(self.headers)):
            return None

        word_data = self._data[row]
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return None
            elif col == 1:
                return format_word_with_stress(
                    word_data["word"], word_data.get("stress_position")
                )
            elif col == 2:
                return word_data.get("transcription_cyrillic", "-")
            elif col == 3:
                return word_data.get("part_of_speech", "-")
            elif col == 4:
                return str(word_data.get("syllable_count", "-"))
            elif col == 5:
                return str(word_data.get("frequency", "-"))
        elif role == Qt.ItemDataRole.UserRole:
            return word_data
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.headers[section]
        return None


class SyllableCountWidget(QWidget):
    selectionChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.buttons = []
        for i in range(1, 6):
            btn = self._create_button(str(i))
            self.buttons.append(btn)
            layout.addWidget(btn)
        btn_6plus = self._create_button("6+")
        self.buttons.append(btn_6plus)
        layout.addWidget(btn_6plus)
        layout.addStretch()

    def _create_button(self, text):
        btn = QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        btn.setMaximumWidth(40)
        btn.setStyleSheet(
            "QToolButton { border: 1px solid #ccc; border-radius: 15px; padding: 5px; font-size: 14px; }"
            "QToolButton:checked { background-color: #007BFF; color: white; border: 1px solid #007BFF; }"
            "QToolButton:hover { background-color: #e6f2ff; border: 1px solid #0056b3; }"
        )
        btn.clicked.connect(self.selectionChanged.emit)
        return btn

    def get_checked_values(self):
        selected_counts = []
        for i, btn in enumerate(self.buttons):
            if btn.isChecked():
                if i < 5:
                    selected_counts.append(i + 1)
                else:
                    selected_counts.extend(range(6, 11))
        return selected_counts if selected_counts else None


class PositionWidget(QWidget):
    """Виджет для выбора позиции звука в слове."""

    selectionChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.buttons = []
        positions = ["Начало", "Середина", "Конец"]
        self.position_values = ["start", "middle", "end"]

        for pos in positions:
            btn = self._create_button(pos)
            self.buttons.append(btn)
            layout.addWidget(btn)
        layout.addStretch()

    def _create_button(self, text):
        btn = QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        btn.setStyleSheet(
            "QToolButton { border: 1px solid #ccc; border-radius: 5px; padding: 5px; min-width: 60px; }"
            "QToolButton:checked { background-color: #007BFF; color: white; border: 1px solid #007BFF; }"
            "QToolButton:hover { background-color: #e6f2ff; }"
        )
        btn.clicked.connect(self.selectionChanged.emit)
        return btn

    def get_checked_values(self):
        """Возвращает список выбранных позиций ('start', 'middle', 'end')."""
        selected_positions = []
        for i, btn in enumerate(self.buttons):
            if btn.isChecked():
                selected_positions.append(self.position_values[i])
        return selected_positions if selected_positions else None


class ModernFonemarikApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.word_collection_model = WordCollectionModel()
        self.state_manager = StateManager()
        # Карта для быстрого доступа к строкам в таблице результатов по word_id
        self.results_word_id_map = {}
        self.initUI()
        self.connect_signals()
        self.update_status_bar()
        self.query_helper.tag_clicked.connect(self.on_tag_clicked)

    def connect_signals(self):
        self.query_input.textChanged.connect(self.state_manager.set_query)
        self.query_input.returnPressed.connect(self.state_manager.execute_search)
        self.position_widget.selectionChanged.connect(
            lambda: self.state_manager.set_position(
                self.position_widget.get_checked_values()
            )
        )
        self.search_in_combo.currentTextChanged.connect(
            self.state_manager.set_search_in
        )
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        self.pos_combo.currentTextChanged.connect(self.state_manager.set_part_of_speech)
        self.stress_sound_combo.currentTextChanged.connect(
            self.state_manager.set_stress_sound
        )
        self.syllable_count_widget.selectionChanged.connect(
            lambda: self.state_manager.set_syllable_count(
                self.syllable_count_widget.get_checked_values()
            )
        )
        self.hardness_group.buttonClicked.connect(self.on_hardness_changed)
        self.voicing_group.buttonClicked.connect(self.on_voicing_changed)
        self.state_manager.search_results_updated.connect(self.update_results_table)
        self.state_manager.pagination_updated.connect(self.update_pagination_controls)
        self.state_manager.status_updated.connect(self.update_status_bar)
        self.results_per_page_combo.currentTextChanged.connect(
            lambda text: self.state_manager.set_page_size(int(text))
        )
        self.word_collection_model.modelReset.connect(self.update_status_bar)
        self.word_collection_model.rowsInserted.connect(self.update_status_bar)
        self.word_collection_model.rowsRemoved.connect(self.update_status_bar)
        self.state_manager.search_results_updated.connect(
            lambda: self.update_status_bar()
        )
        # self.state_manager.collection_updated.connect(self.on_collection_updated)
        self.state_manager.word_added_to_collection.connect(self.on_word_added)
        self.state_manager.word_removed_from_collection.connect(self.on_word_removed)
        self.state_manager.collection_cleared.connect(
            self.word_collection_model.clear_collection
        )
        # self.word_collection_model.rowsRemoved.connect(
        #     lambda: self.on_collection_updated(force_rebuild=False)
        # )

    def initUI(self):
        self.setWindowTitle("Фонемарик - Современный интерфейс")
        self.setGeometry(100, 100, 1400, 800)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        sidebar = self.create_sidebar()
        main_layout.addWidget(sidebar)

        # Создаем разделитель
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # Создаем основное содержимое (таблица результатов)
        main_content = self.create_main_content()
        self.splitter.addWidget(main_content)

        # Создаем панель сборника
        self.collection_panel = self.create_collection_panel()
        self.splitter.addWidget(self.collection_panel)

        # Начальные размеры: 2/3 для результатов, 1/3 для сборника
        self.splitter.setSizes([self.width() * 2 // 3, self.width() * 1 // 3])
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)

        self.create_menu_bar()

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setFrameShape(QFrame.Shape.StyledPanel)
        sidebar.setMaximumWidth(350)
        layout = QVBoxLayout(sidebar)
        layout.setSpacing(10)

        main_filters_layout = QVBoxLayout()
        query_label = QLabel("Запрос")
        query_label.setStyleSheet("font-weight: bold;")
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Введите DSL-запрос...")
        main_filters_layout.addWidget(query_label)
        main_filters_layout.addWidget(self.query_input)

        common_filters_layout = QGridLayout()
        position_label = QLabel("Позиция в слове")
        self.position_widget = PositionWidget()
        # Позиция занимает всю первую строку (0), растягиваясь на 2 колонки
        common_filters_layout.addWidget(position_label, 0, 0, 1, 2)
        common_filters_layout.addWidget(self.position_widget, 1, 0, 1, 2)

        search_in_label = QLabel("Искать в")
        self.search_in_combo = QComboBox()
        self.search_in_combo.addItems(["В транскрипции", "В слове"])
        # "Искать в" начинается со второй строки (2)
        common_filters_layout.addWidget(search_in_label, 2, 0)
        common_filters_layout.addWidget(self.search_in_combo, 3, 0)

        sort_label = QLabel("Сортировка")
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["По алфавиту", "По частоте"])
        # "Сортировка" также на второй строке (2), но во второй колонке (1)
        common_filters_layout.addWidget(sort_label, 2, 1)
        common_filters_layout.addWidget(self.sort_combo, 3, 1)

        main_filters_layout.addLayout(common_filters_layout)
        layout.addLayout(main_filters_layout)

        # --- Справка по языку запросов ---
        self.query_helper = QueryHelperWidget()
        layout.addWidget(self.query_helper)

        self.advanced_filters_toggle_button = QToolButton()
        self.advanced_filters_toggle_button.setText("Расширенные фильтры ▼")
        self.advanced_filters_toggle_button.setCheckable(True)
        self.advanced_filters_toggle_button.setChecked(False)
        self.advanced_filters_toggle_button.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; color: #007BFF; }"
            "QToolButton:hover { color: #0056b3; }"
        )
        self.advanced_filters_toggle_button.clicked.connect(
            self.toggle_advanced_filters
        )
        layout.addWidget(self.advanced_filters_toggle_button)

        self.advanced_filters_panel = QFrame()
        advanced_layout = QVBoxLayout(self.advanced_filters_panel)
        advanced_layout.setContentsMargins(0, 5, 0, 5)
        advanced_layout.setSpacing(10)

        pos_label = QLabel("Часть речи")
        self.pos_combo = QComboBox()
        self.pos_combo.addItems(["Все части речи"] + POS_NAMES_LIST)
        advanced_layout.addWidget(pos_label)
        advanced_layout.addWidget(self.pos_combo)

        stress_label = QLabel("Ударный звук")
        self.stress_sound_combo = QComboBox()
        self.stress_sound_combo.addItem("Все ударения")
        self.update_stress_sounds()
        advanced_layout.addWidget(stress_label)
        advanced_layout.addWidget(self.stress_sound_combo)

        exclude_label = QLabel("Исключить")
        self.exclude_input = QLineEdit()
        self.exclude_input.setPlaceholderText("Исключить звуки (а, б', ...)")
        advanced_layout.addWidget(exclude_label)
        advanced_layout.addWidget(self.exclude_input)

        phonology_layout = QGridLayout()
        phonology_label = QLabel("Свойства искомого согласного")
        phonology_label.setStyleSheet("font-weight: bold;")
        advanced_layout.addWidget(phonology_label)

        # --- Группа Твердость/Мягкость ---
        self.hardness_group = QButtonGroup(self)
        self.hardness_group.setExclusive(
            False
        )  # Отключаем эксклюзивность для ручного управления

        self.hard_button = self._create_toggle_button("Только твёрдые")
        self.hard_button.setToolTip(
            "Искать слова, в которых найденный по запросу согласный звук является твёрдым."
        )
        self.soft_button = self._create_toggle_button("Только мягкие")
        self.soft_button.setToolTip(
            "Искать слова, в которых найденный по запросу согласный звук является мягким."
        )
        self.hardness_group.addButton(self.hard_button, 1)
        self.hardness_group.addButton(self.soft_button, 2)

        phonology_layout.addWidget(self.hard_button, 0, 0)
        phonology_layout.addWidget(self.soft_button, 0, 1)

        # --- Группа Звонкость/Глухость ---
        self.voicing_group = QButtonGroup(self)
        self.voicing_group.setExclusive(
            False
        )  # Отключаем эксклюзивность для ручного управления

        self.voiced_button = self._create_toggle_button("Только звонкие")
        self.voiced_button.setToolTip(
            "Искать слова, в которых найденный по запросу согласный звук является звонким."
        )
        self.voiceless_button = self._create_toggle_button("Только глухие")
        self.voiceless_button.setToolTip(
            "Искать слова, в которых найденный по запросу согласный звук является глухим."
        )
        self.voicing_group.addButton(self.voiced_button, 1)
        self.voicing_group.addButton(self.voiceless_button, 2)

        phonology_layout.addWidget(self.voiced_button, 1, 0)
        phonology_layout.addWidget(self.voiceless_button, 1, 1)

        advanced_layout.addLayout(phonology_layout)

        syllable_label = QLabel("Количество слогов")
        advanced_layout.addWidget(syllable_label)
        self.syllable_count_widget = SyllableCountWidget()
        advanced_layout.addWidget(self.syllable_count_widget)

        self.advanced_filters_panel.setVisible(False)
        layout.addWidget(self.advanced_filters_panel)
        layout.addStretch()
        return sidebar

    def create_main_content(self):
        main_content = QFrame()
        main_content.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(main_content)
        self.results_table = QTableView()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.results_table)

        # --- Панель пагинации ---
        pagination_layout = QHBoxLayout()
        self.prev_page_button = QPushButton("◀ Назад")
        self.prev_page_button.clicked.connect(self.state_manager.go_to_previous_page)
        self.page_label = QLabel("Страница 1 из 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_page_button = QPushButton("Вперед ▶")
        self.next_page_button.clicked.connect(self.state_manager.go_to_next_page)

        self.results_per_page_combo = QComboBox()
        self.results_per_page_combo.addItems(["10", "25", "50", "100"])
        self.results_per_page_combo.setCurrentText("25")
        self.results_per_page_combo.setFixedWidth(80)

        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_page_button)
        pagination_layout.addSpacing(20)
        pagination_layout.addWidget(QLabel("Результатов на странице:"))
        pagination_layout.addWidget(self.results_per_page_combo)
        pagination_layout.addStretch()
        layout.addLayout(pagination_layout)

        status_layout = QHBoxLayout()
        self.status_bar = QLabel("Готово")
        self.status_bar.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_bar)
        status_layout.addStretch()

        self.reset_filters_button = QPushButton("Сбросить фильтры")
        self.reset_filters_button.clicked.connect(self.reset_all_filters)
        status_layout.addWidget(self.reset_filters_button)

        self.toggle_collection_button = QPushButton("Скрыть сборник")
        self.toggle_collection_button.setCheckable(True)
        self.toggle_collection_button.setChecked(True)
        self.toggle_collection_button.clicked.connect(self.toggle_collection_panel)
        status_layout.addWidget(self.toggle_collection_button)

        layout.addLayout(status_layout)

        return main_content

    def create_collection_panel(self):
        collection_panel = QWidget()
        layout = QVBoxLayout(collection_panel)
        self.collection_table = QTableView()
        self.collection_table.setModel(self.word_collection_model)
        self.collection_table.setAlternatingRowColors(True)
        self.collection_table.setSortingEnabled(True)
        self.collection_table.clicked.connect(self.on_collection_table_clicked)
        header = self.collection_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.collection_table)
        return collection_panel

    def create_menu_bar(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл")
        export_action = QAction("Экспортировать сборник", self)
        export_action.triggered.connect(self.export_collection)
        file_menu.addAction(export_action)
        clear_action = QAction("Очистить сборник", self)
        clear_action.triggered.connect(self.clear_collection)
        file_menu.addAction(clear_action)

        file_menu.addSeparator()

        update_action = QAction("Обновить словарь из файла...", self)
        update_action.triggered.connect(self.open_update_dialog)
        file_menu.addAction(update_action)

    def open_update_dialog(self):
        """Открывает диалог выбора файла для обновления словаря."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать файл для обновления",
            "",
            "JSON файлы (*.json);;CSV файлы (*.csv);;Все файлы (*)",
        )
        if filename:
            # Запускаем обновление через state_manager
            self.state_manager.run_dictionary_update(filename)

    def update_results_table(self, results):
        model = WordTableModel(results)
        self.results_table.setModel(model)

        # Очищаем и заново строим карту для быстрого доступа
        self.results_word_id_map.clear()

        for i, word_data in enumerate(results):
            word_id = word_data.get("id")
            if word_id is not None:
                self.results_word_id_map[word_id] = i

            add_button = QPushButton()
            add_button.setFixedSize(28, 28)

            if self.state_manager.is_word_in_collection(word_data):
                add_button.setText("✓")
                add_button.setEnabled(False)
            else:
                add_button.setText("+")
                add_button.setEnabled(True)
                add_button.clicked.connect(partial(self.on_add_button_clicked, i))

            self.results_table.setIndexWidget(model.index(i, 0), add_button)

    def update_status_bar(self, status_text=None):
        if isinstance(status_text, str):
            self.status_bar.setText(status_text)
        else:
            search_count = len(self.state_manager.search_results)
            self.status_bar.setText(f"Найдено слов: {search_count}")

    def update_pagination_controls(self, current_page, total_pages):
        """Обновляет элементы управления пагинацией."""
        self.page_label.setText(f"Страница {current_page} из {total_pages}")
        self.prev_page_button.setEnabled(current_page > 1)
        self.next_page_button.setEnabled(current_page < total_pages)

    def reset_all_filters(self):
        """Сбрасывает все фильтры и очищает поля ввода."""
        # 1. Вызываем метод менеджера состояний для сброса логики
        self.state_manager.reset_filters()

        # 2. Очищаем все виджеты в UI
        self.query_input.clear()
        self.pos_combo.setCurrentIndex(0)
        self.stress_sound_combo.setCurrentIndex(0)
        self.exclude_input.clear()
        self.search_in_combo.setCurrentIndex(0)
        self.sort_combo.setCurrentIndex(0)

        # Сброс кнопок-переключателей
        for btn in self.position_widget.buttons:
            btn.setChecked(False)

        for btn in self.syllable_count_widget.buttons:
            btn.setChecked(False)

        # Сброс групп фонологических признаков
        self.hardness_group.setExclusive(False)
        for button in self.hardness_group.buttons():
            button.setChecked(False)
        self.hardness_group.setExclusive(True)

        self.voicing_group.setExclusive(False)
        for button in self.voicing_group.buttons():
            button.setChecked(False)
        self.voicing_group.setExclusive(True)

    def toggle_advanced_filters(self, checked):
        self.advanced_filters_panel.setVisible(checked)
        self.advanced_filters_toggle_button.setText(
            "Расширенные фильтры ▲" if checked else "Расширенные фильтры ▼"
        )

    def toggle_collection_panel(self, checked):
        if checked:
            self.toggle_collection_button.setText("Скрыть сборник")
            # Восстанавливаем размеры
            self.splitter.setSizes([self.width() * 2 // 3, self.width() * 1 // 3])
        else:
            self.toggle_collection_button.setText("Показать сборник")
            # Сворачиваем панель сборника, устанавливая ее размер в 0
            self.splitter.setSizes([self.width(), 0])

    def on_add_button_clicked(self, row):
        model = self.results_table.model()
        index = model.index(row, 1)
        word_data = model.data(index, Qt.ItemDataRole.UserRole)
        if word_data:
            # query = self.state_manager.query
            # self.add_word_to_collection(query, word_data) # Упрощаем
            self.state_manager.add_word_to_collection(word_data)

    def on_collection_table_clicked(self, index):
        if index.column() == 0:
            # Получаем данные слова, чтобы передать их в state_manager
            if index.row() < len(self.word_collection_model.collection_list):
                word_data_with_query = self.word_collection_model.collection_list[
                    index.row()
                ]
                word_data = word_data_with_query[1]
                self.state_manager.remove_word_from_collection(word_data)

    def update_stress_sounds(self):
        try:
            if not Path("dictionary.db").exists():
                return
            conn = sqlite3.connect("dictionary.db")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT stress_sound FROM dictionary WHERE stress_sound IS NOT NULL ORDER BY stress_sound"
            )
            sounds = [row[0] for row in cursor.fetchall() if row[0]]
            conn.close()
            for sound in sounds:
                if self.stress_sound_combo.findText(sound) == -1:
                    self.stress_sound_combo.addItem(sound)
        except Exception:
            pass

    def on_sort_changed(self, index):
        is_by_frequency = self.sort_combo.currentText() == "По частоте"
        self.state_manager.set_sort_by_frequency(is_by_frequency)

    def on_hardness_changed(self, clicked_button):
        """Обрабатывает изменение выбора в группе твердости/мягкости с возможностью сброса."""
        for button in self.hardness_group.buttons():
            if button is not clicked_button:
                button.setChecked(False)

        if self.hard_button.isChecked():
            self.state_manager.set_phonological_hardness("hard")
        elif self.soft_button.isChecked():
            self.state_manager.set_phonological_hardness("soft")
        else:
            # Если ни одна кнопка не выбрана (пользователь снял выбор)
            self.state_manager.set_phonological_hardness(None)

    def on_voicing_changed(self, clicked_button):
        """Обрабатывает изменение выбора в группе звонкости/глухости с возможностью сброса."""
        for button in self.voicing_group.buttons():
            if button is not clicked_button:
                button.setChecked(False)

        if self.voiced_button.isChecked():
            self.state_manager.set_phonological_voicing("voiced")
        elif self.voiceless_button.isChecked():
            self.state_manager.set_phonological_voicing("voiceless")
        else:
            self.state_manager.set_phonological_voicing(None)

    def _create_toggle_button(self, text):
        """Создает стилизованную кнопку-переключатель."""
        btn = QToolButton()
        btn.setText(text)
        btn.setCheckable(True)
        btn.setStyleSheet(
            """
            QToolButton {
                border: 1px solid #c0c0c0;
                border-radius: 5px;
                padding: 5px 10px;
                background-color: #f0f0f0; /* Более темный фон для неактивного состояния */
                font-weight: bold;
                color: #555;
            }
            QToolButton:checked {
                background-color: #007BFF;
                color: white;
                border-color: #0056b3;
            }
            QToolButton:hover:!checked {
                background-color: #e0e0e0; /* Затемнение при наведении */
                border-color: #007BFF;
            }
        """
        )
        return btn

    def add_word_to_collection(self, query, word_data):
        # Этот метод больше не будет вызываться напрямую, но оставляем на всякий случай
        if not self.state_manager.is_word_in_collection(word_data):
            self.state_manager.add_word_to_collection(word_data)

    def clear_collection(self):
        self.state_manager.clear_collection()

    def export_collection(self):
        try:
            export_text = self.word_collection_model.export_to_text()
            if not export_text.strip():
                self.status_bar.setText("Сборник пуст")
                return

            # Вызываем диалоговое окно для выбора пути сохранения
            from datetime import datetime

            default_filename = (
                f"collection_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Экспортировать сборник",
                default_filename,
                "Текстовые файлы (*.txt);;Все файлы (*)",
            )

            # Если пользователь отменил диалог, filename будет пустой строкой
            if not filename:
                self.status_bar.setText("Экспорт отменен")
                return

            with open(filename, "w", encoding="utf-8") as f:
                f.write(export_text)
            self.status_bar.setText(f"Сборник экспортирован в {Path(filename).name}")
        except Exception as e:
            self.status_bar.setText(f"Ошибка экспорта: {str(e)}")

    def on_word_added(self, word_id: int):
        """Слот, вызываемый при добавлении слова в сборник."""
        # 1. Добавляем слово в модель сборника
        # Находим данные слова в текущих результатах поиска
        word_data = self._find_word_data_in_results(word_id)
        if word_data:
            query = self.state_manager.query
            self.word_collection_model.add_word(query, word_data)

        # 2. Обновляем кнопку в таблице результатов
        self._update_result_button_state(word_id, is_in_collection=True)

    def on_word_removed(self, word_id: int):
        """Слот, вызываемый при удалении слова из сборника."""
        # 1. Удаляем слово из модели сборника, используя новый быстрый метод
        self.word_collection_model.remove_word_by_id(word_id)

        # 2. Обновляем кнопку в таблице результатов
        self._update_result_button_state(word_id, is_in_collection=False)

    def _find_word_data_in_results(self, word_id: int):
        """Находит данные слова по ID в текущих результатах поиска, используя карту."""
        model = self.results_table.model()
        if not model or word_id not in self.results_word_id_map:
            return None

        row_index = self.results_word_id_map[word_id]
        if 0 <= row_index < model.rowCount():
            return model.data(model.index(row_index, 0), Qt.ItemDataRole.UserRole)

        return None

    def _update_result_button_state(self, word_id: int, is_in_collection: bool):
        """Обновляет состояние кнопки добавления для слова, используя карту."""
        model = self.results_table.model()
        if not model or word_id not in self.results_word_id_map:
            return

        row_index = self.results_word_id_map.get(word_id)
        if row_index is None:
            return

        add_button = self.results_table.indexWidget(model.index(row_index, 0))
        if isinstance(add_button, QPushButton):
            if is_in_collection:
                add_button.setText("✓")
                add_button.setEnabled(False)
                # Отключаем обработчик, чтобы избежать повторного добавления
                # Это более надежно, чем просто вызов disconnect(), который может вызвать ошибку
                try:
                    add_button.clicked.disconnect()
                except TypeError:
                    pass  # Соединение уже было отключено
            else:
                add_button.setText("+")
                add_button.setEnabled(True)
                # Восстанавливаем соединение, если его не было
                try:
                    add_button.clicked.disconnect()
                except TypeError:
                    pass  # На случай, если соединений не было
                add_button.clicked.connect(
                    partial(self.on_add_button_clicked, row_index)
                )

    def on_tag_clicked(self, tag):
        """Добавляет тег из справки в поле ввода."""
        current_text = self.query_input.text()
        # Добавляем пробел, если поле не пустое и не заканчивается пробелом
        if current_text and not current_text.endswith(" "):
            self.query_input.setText(current_text + " " + tag)
        else:
            self.query_input.setText(current_text + tag)
        self.query_input.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = ModernFonemarikApp()
    ex.show()
    sys.exit(app.exec())
