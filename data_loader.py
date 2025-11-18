import json
from pathlib import Path
from typing import Dict, Optional, Tuple

def get_pos_tag_map() -> Dict[str, Tuple[str, Optional[float]]]:
    """
    Загружает данные из lemma40_tables.json и создает отображение
    'лемма' -> ('часть речи', частота).

    Возвращает:
        Словарь, где ключи - леммы в нижнем регистре, а значения - кортежи
        (часть речи, частота).
    """
    pos_map = {}
    file_path = Path("lemma40_tables.json")

    if not file_path.exists():
        # Если файла нет, нужно сначала его сгенерировать.
        # Для простоты, предположим, что он уже существует.
        # В реальном приложении здесь был бы вызов parse_lemma40.py
        print(f"Файл {file_path} не найден. Пожалуйста, сгенерируйте его.")
        return {}

    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                # Пропускаем строки, которые не являются словарями с данными о словах
                if not isinstance(data, dict) or "rows" not in data:
                    continue

                for row in data.get("rows", []):
                    lemma = row.get("lemma")
                    pos = row.get("pos")
                    frequency_str = row.get("frequency")
                    
                    frequency = None
                    if frequency_str:
                        try:
                            frequency = float(frequency_str)
                        except (ValueError, TypeError):
                            frequency = None

                    if lemma and pos:
                        # Приводим к нижнему регистру для унификации
                        # Сохраняем первую встреченную форму слова
                        if lemma.lower() not in pos_map:
                            pos_map[lemma.lower()] = (pos, frequency)
            except json.JSONDecodeError:
                continue # Игнорируем некорректные строки JSON

    return pos_map

if __name__ == '__main__':
    # Пример использования и проверки
    mapping = get_pos_tag_map()
    print(f"Загружено {len(mapping)} сопоставлений 'слово -> (часть речи, частота)'.")
    # Выведем несколько примеров
    for i, (word, data) in enumerate(mapping.items()):
        if i >= 5:
            break
        print(f"'{word}': ('{data[0]}', {data[1]})")
