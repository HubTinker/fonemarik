import sqlite3
from pathlib import Path
from text_utils import format_word_with_stress
import re

EXPORT_FILE = "words_export.html"

# Список удвоенных согласных, которые могут вызывать смещение
DOUBLED_LETTERS = {"сс", "мм", "нн", "лл", "пп", "бб", "вв", "гг", "дд", "жж", "зз", "кк", "рр", "тт", "фф", "цц", "чч", "шш", "щщ"}


def _calculate_doubled_letters_offset(word: str, start_index: int) -> int:
    """
    Рассчитывает смещение для выделения, если в слове до start_index есть удвоенные буквы.
    Каждая пара удвоенных букв добавляет +1 к смещению.
    """
    offset = 0
    # Проверяем срезы по два символа до начала выделения
    for i in range(start_index - 1):
        if word[i:i+2].lower() in DOUBLED_LETTERS:
            offset += 1
    return offset


def export_words(found_words: list[dict], search_in: str, limit: int | None = None):
    """
    Экспортирует найденные слова в HTML-файл для печати.
    Слова разделяются запятой, а искомое сочетание выделяется жирным (тег <b>).
    Ударения добавляются к словам.

    Args:
        found_words (list[dict]): Список словарей с информацией о словах.
        search_in (str): В чем искали ('word' или 'phonemes').
        limit (int | None): Ограничение на количество экспортируемых слов.
    """
    if not found_words:
        print("Нет слов для экспорта.")
        return

    words_to_export = found_words[:limit] if limit else found_words

    formatted_words = []
    for row in words_to_export:
        original_word = row["word"]
        to_highlight = row.get("matched_part")
        matched_span = row.get("matched_span")

        highlighted_word = original_word
        if (
            matched_span
            and isinstance(matched_span, (list, tuple))
            and len(matched_span) == 2
        ):
            # Используем точные индексы из поиска, чтобы выделять именно найденный фрагмент.
            start_idx, end_idx = matched_span

            # --- НОВЫЙ БЛОК: Коррекция индексов из-за удвоенных букв ---
            offset = _calculate_doubled_letters_offset(original_word, start_idx)
            start_idx += offset
            end_idx += offset
            # --- КОНЕЦ НОВОГО БЛОКА ---

            # Защита от неверных индексов
            if 0 <= start_idx < end_idx <= len(original_word):
                highlighted_word = (
                    original_word[:start_idx]
                    + f"<b>{original_word[start_idx:end_idx]}</b>"
                    + original_word[end_idx:]
                )
        elif to_highlight:
            try:
                # Фолбек: ищем и выделяем первую встреченную подстроку (backward-compatibility)
                pattern = re.compile(re.escape(to_highlight), re.IGNORECASE)
                highlighted_word, count = pattern.subn(
                    f"<b>{to_highlight}</b>", original_word, 1
                )
                if count == 0:
                    highlighted_word = original_word
            except re.error:
                highlighted_word = original_word

        # Теперь, когда выделение сделано, ставим ударение
        final_word = format_word_with_stress(
            highlighted_word, row.get("stress_position")
        )
        formatted_words.append(final_word)

    output_string = ", ".join(formatted_words)

    # Обновленная HTML-структура с улучшенным форматированием для печати
    html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Экспорт слов</title>
    <style>
        @media print {{
            body {{
                margin: 1.5cm; /* Поля для печати */
            }}
        }}
        body {{
            font-family: 'Times New Roman', serif;
            font-size: 14pt;
            line-height: 1.618; /* Межстрочный интервал по золотому сечению */
            margin: 2cm;
        }}
        b {{
            background-color: #ffff99; /* Легкий желтый фон для выделения */
        }}
    </style>
</head>
<body>
    <p>{output_string}</p>
</body>
</html>
"""

    try:
        with open(EXPORT_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Экспорт успешно завершен. Файл '{EXPORT_FILE}' создан.")
    except IOError as e:
        print(f"Ошибка при записи в файл: {e}")


if __name__ == "__main__":
    # Пример использования для демонстрации
    # В реальном приложении эта функция будет вызываться из GUI
    mock_words = ["тестовоеслово", "словотест", "простослово"]
    mock_query = "тест"
    export_words(mock_words, mock_query)
    # Ожидаемый результат в файле: "ТЕКСТовоеслово, словоТЕКСТ, простослово"
