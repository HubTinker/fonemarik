import streamlit as st
from logic.pronunciation_trainer import PronunciationTrainer
from training_component import web_speech_api_component
from database import get_all_collections

# --- Инициализация ---
trainer = PronunciationTrainer(db_path="dictionary.db")


def show_training_ui():
    """Отображает интерфейс тренировки произношения."""
    st.header("Режим тренировки произношения")

    # --- Выбор коллекции ---
    collections = get_all_collections()
    if not collections:
        st.warning("Сначала создайте коллекцию в разделе 'Коллекции'.")
        return

    collection_names = {c["id"]: c["title"] for c in collections}
    selected_collection_id = st.selectbox(
        "Выберите коллекцию для тренировки:",
        options=list(collection_names.keys()),
        format_func=lambda x: collection_names[x],
    )

    if not selected_collection_id:
        return

    # --- Запуск и управление сессией ---
    session_key = f"training_session_{selected_collection_id}"

    # Кнопка для сброса сессии
    if st.button("Начать заново"):
        st.session_state[session_key] = trainer.start_session(
            collection_id=selected_collection_id
        )
        st.rerun()

    if session_key not in st.session_state:
        st.session_state[session_key] = trainer.start_session(
            collection_id=selected_collection_id
        )

    session = st.session_state[session_key]
    word_ids = session.get("word_ids", [])

    if not word_ids:
        st.warning("В этой коллекции нет слов. Добавьте их в разделе 'Коллекции'.")
        return

    # --- Основной UI тренировки ---
    current_index = session["current_index"]
    current_word_id = word_ids[current_index]
    current_word_data = session["words_data"][current_word_id]
    current_word = current_word_data["word"]
    total_words = len(word_ids)
    result_data = session["results"][current_word_id]

    st.subheader(f"Слово для произношения:")
    st.title(current_word)

    # --- ASR Компонент ---
    st.markdown("---")
    st.write("Нажмите 'Говорите' и произнесите слово:")

    # Используем ASR клиент для получения аудио
    asr_result = web_speech_api_component()

    if isinstance(asr_result, dict):
        if asr_result.get("text"):
            recognized_text = asr_result.get("text", "").strip()

            # Проверяем произношение
            result = trainer.check_pronunciation(current_word, recognized_text)

            # Обновляем состояние сессии
            result_data["attempts"] += 1
            if result == "ok":
                result_data["success"] = True
                st.success(f"🎉 Верно! Вы сказали: **{recognized_text}**")
            else:
                st.error(
                    f"🤔 Ошибка. Вы сказали: **{recognized_text}**. Попробуйте еще раз."
                )

            # Просто перезапускаем, чтобы компонент сбросился и мы не обрабатывали результат повторно
            st.rerun()
        elif asr_result.get("error"):
            st.error(f"Ошибка распознавания речи: {asr_result.get('error')}")

    # --- Статус и прогресс ---
    st.markdown("---")
    if result_data["success"]:
        st.success("Слово произнесено верно!")
    elif result_data["attempts"] > 0:
        st.warning(f"Пока неверно. Попыток: {result_data['attempts']}")
    else:
        st.info("Ожидание произношения...")

    st.progress((current_index + 1) / total_words)
    st.write(f"Слово {current_index + 1} из {total_words}")

    # --- Кнопки навигации ---
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button(
            "⬅️ Предыдущее", use_container_width=True, disabled=(current_index == 0)
        ):
            session["current_index"] -= 1
            st.rerun()
    with col2:
        if st.button(
            "Следующее ➡️",
            use_container_width=True,
            disabled=(current_index >= total_words - 1),
        ):
            session["current_index"] += 1
            st.rerun()

    if current_index >= total_words - 1 and result_data["success"]:
        st.balloons()
        st.success("Поздравляем! Вы завершили тренировку этой коллекции!")
