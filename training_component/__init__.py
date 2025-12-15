# training_component/__init__.py
import streamlit.components.v1 as components
from pathlib import Path

# Объявляем компонент. Streamlit будет искать 'index.html' в директории 'frontend'.
_build_dir = Path(__file__).parent / "frontend"
_component_func = components.declare_component("web_speech_api", path=str(_build_dir))


def web_speech_api_listen(key=None):
    """
    Создает и вызывает фронтенд-компонент для распознавания речи.

    Args:
        key (str, optional): Уникальный ключ для экземпляра компонента.

    Returns:
        dict: Значение, возвращаемое из фронтенда.
    """
    component_value = _component_func(key=key, default={"text": "", "status": "idle"})
    return component_value
