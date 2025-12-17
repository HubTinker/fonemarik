import streamlit.components.v1 as components
import json


def client_side_pronunciation_check(target_word):
    """
    Встраивает HTML/JS компонент для проверки произношения на клиентской стороне.

    Args:
        target_word (str): Слово, которое нужно произнести пользователю

    Returns:
        dict: Результат проверки произношения
    """
    # Экранируем кавычки в целевом слове для использования в JavaScript
    escaped_target_word = target_word.replace('"', '"').replace("'", "&#x27;")

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <title>Pronunciation Checker</title>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background-color: transparent;
        }}
        #micButton {{
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
            width: 200px;
        }}
        #micButton:hover {{
            background-color: #45a049;
        }}
        #micButton.recording {{
            background-color: #f44336;
        }}
        #micButton.recording:hover {{
            background-color: #da190b;
        }}
        #status {{
            margin-top: 10px;
            font-style: italic;
            color: #555;
            min-height: 20px;
        }}
        #result {{
            margin-top: 15px;
            font-weight: bold;
            min-height: 25px;
        }}
        .correct {{
            color: green;
        }}
        .incorrect {{
            color: red;
        }}
        .target-word {{
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
            color: #333;
        }}
      </style>
    </head>
    <body>

    <div style="text-align: center;">
        <div class="target-word">Произнесите слово: <span id="targetWord">{escaped_target_word}</span></div>
        <button id="micButton">Нажмите и говорите</button>
        <div id="status">Статус: ожидание</div>
        <div id="result"></div>
    </div>

    <script>
      const targetWord = "{escaped_target_word}";
      const micButton = document.getElementById('micButton');
      const statusDiv = document.getElementById('status');
      const resultDiv = document.getElementById('result');
      const targetWordElement = document.getElementById('targetWord');
      
      // Функция нормализации текста (сопоставимая с Python реализацией)
      function normalizeText(text) {{
        return text.toLowerCase().trim().replace(/[ё]/g, 'е');
      }}
      
      // Функция вычисления расстояния Левенштейна
      function levenshteinDistance(str1, str2) {{
        const matrix = Array(str2.length + 1).fill().map(() => Array(str1.length + 1).fill(0));
        
        for (let i = 0; i <= str1.length; i++) {{
          matrix[0][i] = i;
        }}
        
        for (let j = 0; j <= str2.length; j++) {{
          matrix[j][0] = j;
        }}
        
        for (let j = 1; j <= str2.length; j++) {{
          for (let i = 1; i <= str1.length; i++) {{
            const indicator = str1[i - 1] === str2[j - 1] ? 0 : 1;
            matrix[j][i] = Math.min(
              matrix[j][i - 1] + 1, // deletion
              matrix[j - 1][i] + 1, // insertion
              matrix[j - 1][i - 1] + indicator // substitution
            );
          }}
        }}
        
        return matrix[str2.length][str1.length];
      }}

      // Функция вычисления схожести в процентах, более близкая к fuzz.ratio
      function similarityPercentage(str1, str2) {{
        if (str1 === str2) {{
          return 100;
        }}
        
        if (str1.length === 0 || str2.length === 0) {{
          return 0;
        }}
        
        // Используем общую длину для нормализации, как в fuzz.ratio
        const distance = levenshteinDistance(str1, str2);
        const len_sum = str1.length + str2.length;
        
        return Math.round((len_sum - distance) / len_sum * 100);
      }}
      
      // Функция проверки произношения
      function checkPronunciation(original, spoken) {{
        const normOriginal = normalizeText(original);
        const normSpoken = normalizeText(spoken);
        
        if (normOriginal === normSpoken) {{
          return {{ status: "ok", similarity: 100 }};
        }}
        
        const similarityRatio = similarityPercentage(normOriginal, normSpoken);
        
        if (similarityRatio > 85) {{
          return {{ status: "ok", similarity: Math.round(similarityRatio) }};
        }}
        
        return {{ status: "error", similarity: Math.round(similarityRatio) }};
      }}
      
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      
      if (!SpeechRecognition) {{
          statusDiv.textContent = 'Ошибка: Speech Recognition API не поддерживается в этом браузере.';
          micButton.disabled = true;
      }} else {{
          const recognition = new SpeechRecognition();
          recognition.lang = 'ru-RU';
          recognition.interimResults = false;
          recognition.maxAlternatives = 1;
          
          recognition.onstart = () => {{
              micButton.textContent = 'Идёт запись...';
              micButton.classList.add('recording');
              statusDiv.textContent = 'Статус: слушаю...';
              resultDiv.textContent = '';
              resultDiv.className = '';
          }};
          
          recognition.onend = () => {{
              micButton.textContent = 'Нажмите и говорите';
              micButton.classList.remove('recording');
              statusDiv.textContent = 'Статус: ожидание';
          }};
          
          recognition.onresult = (event) => {{
              const transcript = event.results[0][0].transcript;
              const confidence = event.results[0][0].confidence;
              
              console.log('Распознано:', transcript);
              
              // Проверяем произношение на клиенте
              const checkResult = checkPronunciation(targetWord, transcript);
              
              // Показываем результат пользователю
              if (checkResult.status === "ok") {{
                  resultDiv.textContent = `Правильно! Вы сказали: "${{transcript}}" (схожесть: ${{checkResult.similarity}}%)`;
                  resultDiv.className = 'correct';
              }} else {{
                  resultDiv.textContent = `Неверно. Вы сказали: "${{transcript}}" (схожесть: ${{checkResult.similarity}}%)`;
                  resultDiv.className = 'incorrect';
              }}
              
              // Отправляем результат в Streamlit
              const value = {{ 
                transcript: transcript, 
                confidence: confidence, 
                status: checkResult.status,
                similarity: checkResult.similarity
              }};
              
              const message = {{
                  isStreamlitMessage: true,
                  type: "streamlit:setComponentValue",
                  value: value
              }};
              
              window.parent.postMessage(message, "*");
          }};
          
          recognition.onerror = (event) => {{
              statusDiv.textContent = 'Ошибка распознавания: ' + event.error;
              console.error('Ошибка SpeechRecognition:', event.error);
              
              // Отправляем ошибку в Streamlit
              window.parent.postMessage({{
                  'error': event.error
              }}, '*');
          }};
          
          micButton.addEventListener('click', () => {{
              recognition.start();
          }});
      }}
    </script>
    </body>
    </html>
    """

    # Встраиваем компонент и указываем, что мы ожидаем возвращаемое значение
    component_value = components.html(html_code, height=250)
    return component_value
