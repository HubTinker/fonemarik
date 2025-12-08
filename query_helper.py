# -*- coding: utf-8 -*-
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGridLayout,
    QFrame,
)


class ClickableLabel(QLabel):
    """Кликабельная метка для добавления тегов в строку запроса."""

    clicked = pyqtSignal(str)

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QLabel {
                color: #007BFF;
                text-decoration: none;
                font-size: 13px;
                padding: 2px;
                border-radius: 3px;
            }
            QLabel:hover {
                background-color: #e6f2ff;
                
            }
        """
        )
        self.setToolTip(f"Нажмите, чтобы добавить '{self.text()}' в поле запроса")

    def mousePressEvent(self, event):
        self.clicked.emit(self.text())


class QueryHelperWidget(QWidget):
    """Виджет со справкой по языку запросов и кликабельными примерами."""

    tag_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 10, 0, 0)
        main_layout.setSpacing(8)

        title_label = QLabel("Справка по языку запросов")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        main_layout.addWidget(title_label)

        # --- Символы ---
        symbols_frame = self._create_section_frame("Символы")
        symbols_layout = QGridLayout(symbols_frame)
        symbols_data = [
            ("*", "Любое количество символов (включая ноль)"),
            ("**", "Один или несколько символов"),
            ("уд[N]", "Слово с ударением на N-м слоге (уд2)"),
            ("!", "Исключить слова с последующим звуком"),
            ("!!", "Исключить слова со всеми последующими звуками"),
        ]
        for i, (symbol, description) in enumerate(symbols_data):
            symbols_layout.addWidget(self._create_clickable_label(symbol), i, 0)
            symbols_layout.addWidget(QLabel(description), i, 1)

        main_layout.addWidget(symbols_frame)

        # --- Теги (группы звуков) ---
        tags_frame = self._create_section_frame("Теги (группы звуков)")
        tags_layout = QGridLayout(tags_frame)
        tags_data = [
            ("(гласн)", "Любой гласный звук"),
            ("(согл)", "Любой согласный звук"),
            ("(тверд)", "Любой твердый согласный"),
            ("(мягк)", "Любой мягкий согласный"),
            ("(м,н)", "Перечисление: м или н"),
        ]
        for i, (tag, description) in enumerate(tags_data):
            tags_layout.addWidget(self._create_clickable_label(tag), i, 0)
            tags_layout.addWidget(QLabel(description), i, 1)
        main_layout.addWidget(tags_frame)

        # --- Примеры комбинаций ---
        examples_frame = self._create_section_frame("Примеры комбинаций")
        examples_layout = QGridLayout(examples_frame)
        examples_data = [
            ("д*м", "Слова, начинающиеся на 'д' и заканчивающиеся на 'м'"),
            ("р(гласн)(согл)", "После 'р' идет гласный, затем согласный"),
            ("ра уд2", "Слова на 'ра' с ударением на 2-м слоге"),
            ("(с,з)р(гласн)", "Начинается на 'с' или 'з', затем 'р' и гласный"),
            (
                "(согл)(согл)(гласн)",
                "Слог со стечением согласных (например, в начале слова)",
            ),
            ("(гласн)(согл)(гласн)", "Согласный между двумя гласными"),
        ]
        for i, (example, description) in enumerate(examples_data):
            examples_layout.addWidget(self._create_clickable_label(example), i, 0)
            examples_layout.addWidget(QLabel(description), i, 1)

        main_layout.addWidget(examples_frame)

    def _create_section_frame(self, title):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.NoFrame)
        # frame.setStyleSheet(".QFrame { border-top: 1px solid #ddd; margin-top: 5px; padding-top: 5px; }")
        return frame

    def _create_clickable_label(self, text):
        label = ClickableLabel(text)
        label.clicked.connect(self.tag_clicked.emit)
        return label
