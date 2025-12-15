# collection_manager_ui.py

import streamlit as st
from database import (
    create_collection,
    get_all_collections,
    add_words_to_collection,
    get_words_in_collection,
    delete_word_from_collection,
    delete_collection,
)


def show_collection_manager():
    """
    Отображает интерфейс для управления коллекциями.
    """
    st.header("Управление коллекциями")

    # Отображение и создание коллекций
    st.subheader("Мои коллекции")

    new_collection_name = st.text_input(
        "Название новой коллекции:", key="new_collection_name"
    )
    if st.button("Создать коллекцию"):
        if new_collection_name:
            create_collection(new_collection_name)
            st.success(f"Коллекция '{new_collection_name}' успешно создана.")
            st.rerun()
        else:
            st.warning("Название коллекции не может быть пустым.")

    collections = get_all_collections()
    if not collections:
        st.info("У вас пока нет ни одной коллекции. Создайте первую!")
        return

    collection_names = [c[1] for c in collections]
    selected_collection_name = st.selectbox(
        "Выберите коллекцию для управления:", collection_names
    )

    if selected_collection_name:
        selected_collection = next(
            (c for c in collections if c[1] == selected_collection_name), None
        )
        if selected_collection:
            collection_id = selected_collection[0]

            # Добавление слов в коллекцию
            st.subheader(f"Добавление слов в '{selected_collection_name}'")
            words_to_add = st.text_area(
                "Введите слова через запятую или с новой строки:",
                key=f"words_for_{collection_id}",
            )

            if st.button("Добавить слова"):
                if words_to_add:
                    # Разделяем слова по запятым или переводам строк и убираем лишние пробелы
                    word_list = [
                        word.strip()
                        for word in words_to_add.replace(",", "\n").split("\n")
                        if word.strip()
                    ]
                    if word_list:
                        add_words_to_collection(collection_id, word_list)
                        st.success(
                            f"Слова добавлены в коллекцию '{selected_collection_name}'."
                        )
                        st.rerun()
                else:
                    st.warning("Поле для ввода слов пусто.")

            # Отображение и удаление слов из коллекции
            st.subheader(f"Слова в коллекции '{selected_collection_name}'")
            words_in_collection = get_words_in_collection(collection_id)

            if not words_in_collection:
                st.info("В этой коллекции пока нет слов.")
            else:
                for word_tuple in words_in_collection:
                    word_id, word_text = word_tuple[0], word_tuple[1]
                    col1, col2 = st.columns([0.8, 0.2])
                    with col1:
                        st.write(word_text)
                    with col2:
                        if st.button("Удалить", key=f"delete_word_{word_id}"):
                            delete_word_from_collection(word_id)
                            st.success(f"Слово '{word_text}' удалено.")
                            st.rerun()

            # Удаление всей коллекции
            st.subheader("Опасная зона")
            if st.button(
                f"Удалить коллекцию '{selected_collection_name}'", type="primary"
            ):
                delete_collection(collection_id)
                st.success(f"Коллекция '{selected_collection_name}' была удалена.")
                st.rerun()
