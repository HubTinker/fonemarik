# -*- coding: utf-8 -*-

"""
Модуль для подсветки синтаксиса DSL в PyQt6.
"""

from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QSyntaxHighlighter, QColor, QTextCharFormat, QFont

class DslHighlighter(QSyntaxHighlighter):
    def __init__(self, parent):
        super().__init__(parent)

        self.highlighting_rules = []

        # Формат для классов (например, (гласн))
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#d19a66")) # оранжевый
        class_format.setFontWeight(QFont.Bold)
        # Паттерн для поиска валидных классов в скобках
        class_names = [
            'гласн', 'гласная', 'согласн', 'согл', 'тверд', 'тв', 
            'мягк', 'звонк', 'звон', 'глух', 'гл', 'любой'
        ]
        class_pattern = r'\b(' + '|'.join(class_names) + r')\b'
        self.highlighting_rules.append((QRegExp(class_pattern), class_format))

        # Формат для OR-групп (например, (к,с,т))
        or_group_format = QTextCharFormat()
        or_group_format.setForeground(QColor("#98c379")) # зеленый
        # Паттерн для поиска содержимого в скобках, содержащего запятую
        self.highlighting_rules.append((QRegExp(r'\(([^)]*?,[^)]*?)\)'), or_group_format))
        
        # Формат для скобок
        bracket_format = QTextCharFormat()
        bracket_format.setForeground(QColor("#61afef")) # синий
        self.highlighting_rules.append((QRegExp(r'\(|\)'), bracket_format))


    def highlightBlock(self, text):
        """
        Применяет правила подсветки к блоку текста.
        """
        for pattern, format in self.highlighting_rules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)