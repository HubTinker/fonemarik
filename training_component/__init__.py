# training_component/__init__.py
import streamlit as st
import streamlit.components.v1 as components


def web_speech_api_component():
    """
    Встраивает HTML/JS для Web Speech API и слушает события.
    """
    html_code = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>Speech Recognition</title>
      <meta charset="UTF-8">
      <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: transparent;
        }
        #micButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 15px 30px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            cursor: pointer;
            border-radius: 8px;
            transition: background-color 0.3s;
        }
        #micButton:hover {
            background-color: #45a049;
        }
        #micButton.recording {
            background-color: #f44336;
        }
        #micButton.recording:hover {
            background-color: #da190b;
        }
        #status {
            margin-top: 10px;
            font-style: italic;
            color: #555;
        }
      </style>
    </head>
    <body>

    <div style="text-align: center;">
        <button id="micButton">Нажмите и говорите</button>
        <div id="status">Статус: ожидание</div>
    </div>

    <script>
      const micButton = document.getElementById('micButton');
      const statusDiv = document.getElementById('status');
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

      if (!SpeechRecognition) {
          statusDiv.textContent = 'Ошибка: Speech Recognition API не поддерживается в этом браузере.';
          micButton.disabled = true;
      } else {
          const recognition = new SpeechRecognition();
          recognition.lang = 'ru-RU';
          recognition.interimResults = false;
          recognition.maxAlternatives = 1;

          recognition.onstart = () => {
              micButton.textContent = 'Идёт запись...';
              micButton.classList.add('recording');
              statusDiv.textContent = 'Статус: слушаю...';
          };

          recognition.onend = () => {
              micButton.textContent = 'Нажмите и говорите';
              micButton.classList.remove('recording');
              statusDiv.textContent = 'Статус: ожидание';
          };

          recognition.onresult = (event) => {
              const transcript = event.results[0][0].transcript;
              const confidence = event.results[0][0].confidence;
              
              console.log('Распознано:', transcript); // Для отладки в браузере
              
              // Отправляем результат в Streamlit как объект
              // Streamlit получит это значение как возвращаемое из `components.html`
              // Streamlit в iframe ожидает postMessage.
              // Для совместимости с режимом отладки, отправляем и туда, и в основной компонент.
              window.parent.postMessage({
                  type: 'streamlit:setComponentValue',
                  value: { transcript: transcript, confidence: confidence }
              }, '*');

              // Для основного приложения, если оно не в iframe
              if (window.Streamlit) {
                  window.Streamlit.setComponentValue({ transcript: transcript, confidence: confidence });
              }
          };

          recognition.onerror = (event) => {
              statusDiv.textContent = 'Ошибка распознавания: ' + event.error;
              console.error('Ошибка SpeechRecognition:', event.error); // Для отладки

              // Отправляем ошибку в Streamlit
              window.parent.postMessage({
                  'error': event.error
              }, '*');
          };

          micButton.addEventListener('click', () => {
              // --- РЕЖИМ ОТЛАДКИ ---
              // Чтобы его включить, откройте консоль разработчика в браузере (F12)
              // и выполните команду: sessionStorage.setItem('debug_mode', 'true');
              // Чтобы выключить: sessionStorage.removeItem('debug_mode');
              if (sessionStorage.getItem('debug_mode') === 'true') {
                  const testTranscript = 'тестовое слово';
                  console.log('РЕЖИМ ОТЛАДКИ: Отправка тестового результата:', testTranscript);
                  statusDiv.textContent = 'Статус: Отправка тестового результата...';
                  
                  // Безопасно отправляем тестовый результат в Streamlit через postMessage
                  window.parent.postMessage({
                      type: 'streamlit:setComponentValue',
                      value: {
                          'transcript': testTranscript,
                          'confidence': 1.0,
                          'debug': true // Флаг для отладки на стороне Python
                      }
                  }, '*');
                  
                  // Также имитируем стандартное поведение для прямого встраивания
                  if (window.Streamlit) {
                      window.Streamlit.setComponentValue({
                          'transcript': testTranscript,
                          'confidence': 1.0,
                          'debug': true
                      });
                  }
                  return;
              }
              // --- Конец режима отладки ---

              recognition.start();
          });
      }
    </script>
    </body>
    </html>
    """

    # Встраиваем компонент и указываем, что мы ожидаем возвращаемое значение
    component_value = components.html(html_code, height=120)
    return component_value
