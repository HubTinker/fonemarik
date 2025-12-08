# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
from search import find_words
from pos_mapper import POS_NAME_TO_TAG, POS_NAMES_LIST
from text_utils import format_word_with_stress
from export_words import export_words, EXPORT_FILE

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
        placeholder="Введите DSL-запрос...",
        help="Используйте DSL-синтаксис: (гласн), (согл), (тверд), (мягк), (звонк), (глух), уд1, уд2 и т.д.",
    )

    exclude_sounds_input = st.text_input(
        "Исключить конкретные звуки",
        placeholder="а, б', ...",
        help="Перечислите через запятую звуки, которых не должно быть в слове.",
    )

    st.markdown("Исключить категории звуков:")
    col1, col2 = st.columns(2)
    with col1:
        exclude_hard = st.checkbox("Твердые согл.", key="exclude_hard")
        exclude_voiced = st.checkbox("Звонкие согл.", key="exclude_voiced")
    with col2:
        exclude_soft = st.checkbox("Мягкие согл.", key="exclude_soft")
        exclude_voiceless = st.checkbox("Глухие согл.", key="exclude_voiceless")

    search_in_options = {"в транскрипции": "phonemes", "в слове": "word"}
    search_in = st.radio(
        "Искать:",
        options=list(search_in_options.keys()),
        horizontal=True,
        help="`в транскрипции` для фонемного поиска, `в слове` для обычного.",
    )

    position = st.selectbox(
        "Позиция в слове",
        options=["в любом месте", "в начале слова", "в конце слова"],
        index=0,
        help="Где должен находиться искомый фонемный шаблон.",
    )

    syllable_count = st.multiselect(
        "Количество слогов",
        options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        help="Фильтр по точному количеству слогов в слове. Можно выбрать несколько.",
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

    syllables = syllable_count if syllable_count else None

    # Получаем тег части речи для БД
    pos_tag = None
    if part_of_speech != "Любая":
        pos_tag = POS_NAME_TO_TAG.get(part_of_speech)

    # --- Сбор всех исключений ---
    exclude_list = []
    if exclude_sounds_input:
        exclude_list.append(exclude_sounds_input)
    if exclude_hard:
        exclude_list.append("тверд")
    if exclude_soft:
        exclude_list.append("мягк")
    if exclude_voiced:
        exclude_list.append("звонк")
    if exclude_voiceless:
        exclude_list.append("глух")

    exclude_str = ",".join(exclude_list)

    with st.spinner("Идет поиск по словарю..."):
        # Вызов основной функции поиска
        found_results = find_words(
            query=query,
            syllable_count=syllables,
            part_of_speech=pos_tag,
            position=search_pos,
            search_in=search_in_options[search_in],
            sort_by_frequency=sort_by_freq,
            exclude_sounds=exclude_str,
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
                    "Слово": format_word_with_stress(
                        item.get("word", ""), item.get("stress_position")
                    ),
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

        # --- Блок экспорта ---
        st.subheader("Экспорт результатов")
        export_limit = st.number_input(
            "Количество слов для экспорта (0 = все)",
            min_value=0,
            max_value=total_found,
            value=min(100, total_found),
            step=50,
        )

        if st.button("Экспортировать в HTML"):
            limit = export_limit if export_limit > 0 else None
            export_words(
                found_words=found_results,
                search_in=search_in_options[search_in],
                limit=limit,
            )
            st.success(f"Экспорт завершен. Скачайте и распечатайте файл")
            # Предоставляем ссылку для скачивания
            with open(EXPORT_FILE, "rb") as file:
                st.download_button(
                    label="Скачать HTML",
                    data=file,
                    file_name=EXPORT_FILE,
                    mime="text/html",
                )

    else:
        st.warning("Слов по вашему запросу не найдено. Попробуйте изменить фильтры.")

else:
    st.info("⬅️ Задайте параметры поиска в боковой панели, чтобы начать.")

# --- Информационный блок ---
with st.expander("Как пользоваться фонемным поиском?"):
    st.markdown(
        """
        **Фонемный поиск** позволяет находить слова по их звучанию, а не написанию.
        Используйте специальные теги и символы для составления запроса:

        **Основные теги (в скобках):**
        - `(гласн)` — любая гласная (`а, о, у, ы, э, я, ё, ю, и, е`)
        - `(согл)` — любая согласная
        - `(тверд)` — любая твердая согласная
        - `(мягк)` — любая мягкая согласная
        - `(звонк)` — любая звонкая согласная
        - `(глух)` — любая глухая согласная
        - `(любой)` — любая гласная или согласная

        **Группы и условия:**
        - `в**в` — буква в слове должна встречаться 2 раза, г**г**г — г встречаться 3 раза и т.д.
        - `(а,о,у)` — любая из фонем в группе (работает как "ИЛИ").
        - `(к,с,т)а` — найдет "ка", "са", "та".
        - `!` — указывает, что предыдущая фонема или группа **должна быть ударной**.
        - `!!` — указывает, что предыдущая фонема или группа **должна быть безударной**.

        **Примеры запросов:**
        - `бр(а,о,ы)!` — найдет слова, где после "бр" идет ударная "а", "о" или "ы".
        - `бр(а,о,ы)!!` — найдет слова, где после "бр" идет безударная "а", "о" или "ы".
        - `(согл)(согл)(гласн)` — найдет слог со стечением двух согласных (например, в слове "трава").
        - `(гласн)(согл)` — найдет закрытый слог (гласный, за которым следует согласный).
        - `(гласн)(согл)(гласн)` — найдет согласный в интервокальной позиции (между двух гласных).
        - `уд2` — найдет слова, где ударение падает на второй слог.
        
        Пробелы между буквами и тегами игнорируются. `к о т` и `кот` — это один и тот же запрос.
        """
    )
