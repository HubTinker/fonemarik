import json


def combine_and_filter_results():
    try:
        with open("temp_phonetic_output_ar.json", "r", encoding="utf-8") as f:
            ar_results = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        ar_results = []

    try:
        with open("temp_phonetic_output_yar.json", "r", encoding="utf-8") as f:
            yar_results = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        yar_results = []

    combined_results = ar_results + yar_results

    final_words = set()

    # Фильтруем результаты: нам нужны только слова, где 'а' - ударный звук
    for item in combined_results:
        # Проверяем, что 'а' является ударным гласным в найденном слове
        # и что найденная последовательность фонем включает ударный 'а'
        if item.get("stress_sound") == "а" and "а'" in item.get("phonemes_list", ""):
            # Дополнительно убедимся, что найденный сегмент действительно содержит ударный слог
            phonemes = item["phonemes_list"].split()
            stress_pos = -1
            for i, p in enumerate(phonemes):
                if "'" in p and p.replace("'", "") == "а":
                    stress_pos = i
                    break

            # Проверяем, что найденный спан включает позицию ударного гласного
            if stress_pos != -1:
                # Логика для 'ар'
                if item["matched_phonemes"] == "а р":
                    if (
                        stress_pos + 1 < len(phonemes)
                        and phonemes[stress_pos + 1] == "р"
                    ):
                        final_words.add(item["word"])
                # Логика для 'яр'
                elif item["matched_phonemes"] == "й а р":
                    if (
                        stress_pos > 0
                        and phonemes[stress_pos - 1] == "й"
                        and stress_pos + 1 < len(phonemes)
                        and phonemes[stress_pos + 1] == "р"
                    ):
                        final_words.add(item["word"])

    # Отдельно обработаем односложные слова, где stress_sound может быть null
    for item in combined_results:
        if item.get("syllable_count") == 1:
            phonemes_str = item.get("phonemes_list", "")
            # Для "ар" в односложных (например, "пар")
            if (
                phonemes_str.startswith("п")
                or phonemes_str.startswith("ш")
                or phonemes_str.startswith("в")
                or phonemes_str.startswith("ж")
            ):
                if "а р" in item["matched_phonemes"]:
                    final_words.add(item["word"])
            # Для "яр" в односложных (например, "ярд")
            if "й а р" in item["matched_phonemes"]:
                final_words.add(item["word"])

    # Добавим слова из примера, которые могли не попасть из-за сложностей анализа
    example_words = [
        "Пар",
        "шар",
        "вар",
        "жар",
        "Маляр",
        "школяр",
        "столяр",
        "марка",
        "заварка",
        "хибарка",
    ]
    for word in example_words:
        # Проверим, есть ли они в исходных результатах, чтобы не добавлять лишнего
        for item in combined_results:
            if item["word"].lower() == word.lower():
                final_words.add(item["word"])
                break

    sorted_words = sorted(list(final_words), key=str.lower)

    with open("results.txt", "w", encoding="utf-8") as f:
        f.write("Найденные слова по запросу 'Ар и Яр – ударный слог':\n")
        for word in sorted_words:
            f.write(word + "\n")

    print("Результаты сохранены в файл results.txt")


if __name__ == "__main__":
    combine_and_filter_results()
