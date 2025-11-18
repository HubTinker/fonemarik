import sqlite3
import csv
from pathlib import Path

DB_FILE = "dictionary.db"
CSV_FILE = "words_export.csv"
LIMIT = None  # Убираем лимит, чтобы экспортировать все записи

def export_words_to_csv():
    """
    Экспортирует все слова из базы данных в CSV-файл.
    """
    db_path = Path(DB_FILE)
    if not db_path.exists():
        print(f"Ошибка: Файл базы данных '{DB_FILE}' не найден.")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        if LIMIT:
            print(f"Получение первых {LIMIT} записей из базы данных...")
            # Выбираем все столбцы с лимитом
            cursor.execute("SELECT * FROM dictionary ORDER BY id LIMIT ?", (LIMIT,))
        else:
            print("Получение всех записей из базы данных...")
            # Выбираем все столбцы без лимита
            cursor.execute("SELECT * FROM dictionary ORDER BY id")
        rows = cursor.fetchall()

        # Получаем названия столбцов из курсора
        column_names = [description[0] for description in cursor.description]

        print(f"Экспорт {len(rows)} записей в '{CSV_FILE}'...")
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(column_names)  # Записываем заголовки
            writer.writerows(rows)

        print(f"Экспорт успешно завершен. Файл '{CSV_FILE}' создан.")

    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    export_words_to_csv()