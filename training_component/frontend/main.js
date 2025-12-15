// main.js

function sendValue(value) {
    Streamlit.setComponentValue(value);
}

function onRender(event) {
    // Устанавливаем высоту фрейма
    Streamlit.setFrameHeight(80);
}

// Инициализация компонента
Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();

const listenBtn = document.getElementById('listenBtn');
const status = document.getElementById('status');

// Проверяем поддержку Web Speech API
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (!SpeechRecognition) {
    status.textContent = "Ошибка: Ваш браузер не поддерживает Web Speech API.";
    listenBtn.disabled = true;
    sendValue({ text: "", status: "error", error: "Unsupported Browser" });
} else {
    const recognition = new SpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.interimResults = false;

    listenBtn.addEventListener('click', () => {
        status.textContent = 'Слушаю...';
        listenBtn.disabled = true;
        recognition.start();
    });

    recognition.onresult = (event) => {
        const last = event.results.length - 1;
        const text = event.results[last][0].transcript;

        // Отправляем результат в Streamlit
        sendValue({ text: text, status: "ok" });

        status.textContent = `Распознано: "${text}"`;
    };

    recognition.onspeechend = () => {
        recognition.stop();
        listenBtn.disabled = false;
        status.textContent = 'Нажмите на кнопку, чтобы начать распознавание.';
    };

    recognition.onerror = (event) => {
        listenBtn.disabled = false;
        status.textContent = 'Ошибка распознавания: ' + event.error;
        sendValue({ text: "", status: "error", error: event.error });
    };

    recognition.onnomatch = () => {
        listenBtn.disabled = false;
        status.textContent = "Речь не распознана. Попробуйте снова.";
        sendValue({ text: "", status: "error", error: "No Match" });
    };
}