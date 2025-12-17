import streamlit as st
from training_component.client_side_pronunciation_check import (
    client_side_pronunciation_check,
)

# Простой тестовый интерфейс для проверки нового компонента
st.title("Тестирование клиентской проверки произношения")

target_word = st.text_input("Введите слово для проверки произношения:", "привет")

st.write(f"Попробуйте произнести слово: **{target_word}**")

result = client_side_pronunciation_check(target_word)

if result:
    if "transcript" in result and "status" in result:
        st.write("Результат распознавания:")
        st.json(result)
    else:
        st.write("Результат:", result)
