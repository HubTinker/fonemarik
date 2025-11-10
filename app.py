import streamlit as st
import re
from pathlib import Path
import pickle
import requests
import random

st.set_page_config(
    page_title="Фонемарик - Подбор слов по звукам", page_icon="🔠", layout="wide"
)

st.title("Подбор слов по звукам 🔠")


@st.cache_data
def get_words():
    """Загружает и кэширует список русских слов."""
    cache_file = Path("russian_words_cache.pkl")

    # Проверяем наличие кэша
    if cache_file.exists():
        try:
            with open(cache_file, "rb") as f:
                return pickle.load(f)
        except Exception:
            # Если с кэшем что-то не так, удаляем его
            cache_file.unlink(missing_ok=True)

    # Если кэша нет или он поврежден, загружаем словарь
    with st.spinner("Загружаем словарь..."):
        url = (
            "https://raw.githubusercontent.com/danakt/russian-words/master/russian.txt"
        )
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # Создаем множество слов, игнорируя пустые строки и преобразуя в нижний регистр
                words = {
                    word.strip().lower()
                    for word in response.text.splitlines()
                    if word.strip()
                }
                # Фильтруем слова, оставляя только те, что содержат только кириллицу
                words = {
                    word
                    for word in words
                    if word
                    and all(char.isalpha() and "а" <= char <= "я" for char in word)
                }
                words = sorted(list(words))

                # Сохраняем кэш
                try:
                    with open(cache_file, "wb") as f:
                        pickle.dump(words, f)
                except Exception as e:
                    st.warning(f"Не удалось сохранить кэш: {str(e)}")

                return words
            else:
                raise Exception(f"HTTP {response.status_code}")
        except Exception as e:
            st.error(f"Ошибка загрузки словаря: {str(e)}")
            return []


col1, col2 = st.columns([2, 1])

with col1:

    def count_syllables(word):
        # Считаем количество гласных как количество слогов
        return len(re.findall(r"[аеёиоуыэюя]", word, re.IGNORECASE))

    pattern = st.text_input(
        "Введите сочетание или шаблон", placeholder="Например: 'мн' или 'р[аеёиоуыэюя]'"
    )

    syllable_filter = st.selectbox(
        "Количество слогов (опционально)",
        options=["Любое", 1, 2, 3, 4, 5, 6],
        index=0,
        help="Фильтровать слова по количеству слогов",
    )

    position = st.radio(
        "Позиция сочетания:",
        ["в любом месте", "в начале слова", "в конце слова"],
        horizontal=True,
    )

    max_words = st.slider(
        "Максимальное количество слов для показа",
        min_value=10,
        max_value=100,
        value=50,
        step=10,
    )

    if pattern:
        # Модифицируем шаблон в зависимости от выбранной позиции
        if position == "в начале слова":
            search_pattern = f"^{pattern}"
        elif position == "в конце слова":
            search_pattern = f"{pattern}$"
        else:
            search_pattern = pattern

        try:
            with st.spinner("Идёт поиск по словарю..."):
                # Находим все подходящие слова
                words = [w for w in get_words() if re.search(search_pattern, w)]
                # Фильтрация по количеству слогов, если выбрано
                if syllable_filter != "Любое":
                    words = [w for w in words if count_syllables(w) == syllable_filter]
                total_found = len(words)

                # Перемешиваем список и берем нужное количество слов
                if words:
                    if len(words) > max_words:
                        words = random.sample(words, max_words)
                    else:
                        random.shuffle(words)

            if words:
                st.success(f"Найдено всего: {total_found} слов")
                st.write(words)
                if total_found > max_words:
                    st.info(f"⚡ Показаны случайные {len(words)} слов из {total_found}")
            else:
                st.warning("Слов не найдено. Попробуйте изменить шаблон.")
        except re.error:
            st.error("Ошибка в регулярном выражении. Проверьте синтаксис.")
    else:
        st.info("👆 Введите шаблон для поиска")

with col2:
    st.markdown(
        """
    ### 💡 Примеры шаблонов
    - `мн` - слова с сочетанием "мн"
    - `р[аеёиоуыэюя]` - "р" + гласная
    - `[бвгджзклмнпрстфхцчшщ]{2}` - два согласных подряд
    """
    )

# Добавляем footer
st.markdown("---")
st.markdown("🌟 Фонемарик - помогаем детям говорить правильно")
