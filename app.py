# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from search import find_words
from pos_mapper import POS_NAME_TO_TAG, POS_NAMES_LIST

# --- Конфигурация страницы ---
st.set_page_config(
    page_title="Фонемарик - Поиск слов по звукам",
    page_icon="🔠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Боковая панель с фильтрами ---
with st.sidebar:
    st.header("Фильтры поиска")

    query = st.text_input(
        "Запрос",
        placeholder="[тверд]к[а] или просто 'книга'",
        help="Введите слово, его часть или фонемный шаблон.",
    )
    
    exclude_sounds = st.text_input(
        "Исключить звуки",
        placeholder="а, б', ...",
        help="Перечислите через запятую звуки, которых не должно быть в слове.",
    )

    search_in_options = {"в транскрипции": "phonemes", "в слове": "word"}
    search_in = st.radio(
        "Искать:",
        options=list(search_in_options.keys()),
        horizontal=True,
        help="`в транскрипции` для фонемного поиска, `в слове` для обычного."
    )

    position = st.selectbox(
        "Позиция в слове",
        options=["в любом месте", "в начале слова", "в конце слова"],
        index=0,
        help="Где должен находиться искомый фонемный шаблон.",
    )
    
    syllable_count = st.selectbox(
        "Количество слогов",
        options=["Любое", 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        index=0,
        help="Фильтр по точному количеству слогов в слове.",
    )

    part_of_speech = st.selectbox(
        "Часть речи",
        options=["Любая"] + POS_NAMES_LIST,
        index=0,
    )

    sort_by_freq = st.toggle(
        "Сортировать по частотности",
        value=False,
        help="Если включено, самые частотные слова будут показаны первыми.",
    )
    
    max_words = st.slider(
        "Максимум слов для показа",
        min_value=50,
        max_value=1000,
        value=100,
        step=50,
        help="Ограничить количество отображаемых результатов.",
    )

# --- Основная часть интерфейса ---
st.title("🔠 Фонемарик")
st.markdown("База для подбора слов по их фонемному составу.")


if query:
    # Преобразование параметров для функции поиска
    pos_map = {
        "в любом месте": "any",
        "в начале слова": "start",
        "в конце слова": "end",
    }
    search_pos = pos_map[position]

    syllables = syllable_count if syllable_count != "Любое" else None
    
    # Получаем тег части речи для БД
    pos_tag = None
    if part_of_speech != "Любая":
        pos_tag = POS_NAME_TO_TAG.get(part_of_speech)

    with st.spinner("Идет поиск по словарю..."):
        # Вызов основной функции поиска
        found_results = find_words(
            query=query,
            syllable_count=syllables,
            part_of_speech=pos_tag,
            position=search_pos,
            search_in=search_in_options[search_in],
            sort_by_frequency=sort_by_freq,
            exclude_sounds=exclude_sounds,
        )

    total_found = len(found_results)

    if total_found > 0:
        st.success(f"Найдено слов: {total_found}")

        # Ограничиваем вывод
        results_to_show = found_results[:max_words]

        # --- Подготовка данных для отображения ---
        display_data = []
        for item in results_to_show:
            display_data.append(
                {
                    "Слово": item.get("word", ""),
                    "Часть речи": item.get("part_of_speech", "-"),
                    "Слоги": item.get("syllable_count", "-"),
                    "Фонемы": item.get("phonemes_list", "-"),
                    "Транскрипция": item.get("transcription_cyrillic", "-"),
                }
            )
        
        df = pd.DataFrame(display_data)

        # Стилизация таблицы для лучшей читаемости
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Слово": st.column_config.TextColumn(width="medium"),
                "Часть речи": st.column_config.TextColumn(width="small"),
                "Слоги": st.column_config.NumberColumn(width="small"),
                "Фонемы": st.column_config.TextColumn(width="large"),
                "Транскрипция": st.column_config.TextColumn(width="large"),
            },
        )
        
        if total_found > max_words:
            st.info(f"Показано первых {max_words} из {total_found} найденных слов.")

    else:
        st.warning("Слов по вашему запросу не найдено. Попробуйте изменить фильтры.")

else:
    st.info("⬅️ Задайте параметры поиска в боковой панели, чтобы начать.")

# --- Информационный блок ---
with st.expander("Как пользоваться фонемным поиском?"):
    st.markdown(
        """
        **Фонемный поиск** позволяет находить слова по их звучанию, а не написанию. 
        Вы можете использовать специальные теги в квадратных скобках:

        - `[гласн]` — любая гласная (`а, о, у, ы, э, я, ё, ю, и, е`)
        - `[согл]` — любая согласная
        - `[тверд]` — любая твердая согласная (`б, в, г, ...`)
        - `[мягк]` — любая мягкая согласная (`б', в', г', ...`)
        - `[звонк]` — любая звонкая согласная
        - `[глух]` — любая глухая согласная
        - `[любой]` — любая гласная или согласная

        **Примеры запросов:**
        - `к[а,о]т` — найдет слова, где между 'к' и 'т' стоит 'а' или 'о'.
        - `[тверд][гласн]` — найдет слова, содержащие сочетание "твердый согласный + гласный".
        - `с[мягк]н` — найдет слова, где между 'с' и 'н' есть любой мягкий согласный.
        
        Пробелы между буквами и тегами игнорируются. `к о т` и `кот` — это один и тот же запрос.
        """
    )
