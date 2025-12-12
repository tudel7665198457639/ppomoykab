from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import random
import os
import asyncio
from datetime import datetime
import aiohttp
import json

app = FastAPI()
# Разрешаем WebSocket с любого места (важно для Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

status_messages = [
    "Server groans to life for scum.",
    "Waking up for worthless worms.",
    "Preparing torment for trush.",
    "Hell's gate opens for losers.",
    "Bootstrapping for bottom-feeders."
]

keywords_responses = {
    "идиоты": "Ah, an idiot spotted? Let's toast to their impending doom",
    "тупые": "Stupidity detected. Rejoicing in the chaos it brings",
    "отсталые": "Dump mmmmove? Bot chuckles at the miserrry ahead.",
    "морда": "Moron in sight. Popping popcorn for the downfall"
}

# === НАСТРОЙКИ АВТООТВЕТЧИКА С ИИ ===
class AIConfig:
    # Твой стиль общения для ИИ (от женского лица)
    YOUR_PERSONALITY = """Ты - девушка по имени рубать.
    Твой характер: саркастичная, острая на язык, но добрая внутри.
    Стиль общения: используешь мат, но с юмором.
    
    Твои любимые фразы:
    - "Кстати,"
    - "Вообще,"
    - "Блин,"
    - "Ебать,"
    - "Похуй, но интересно"
    - "хвшарпвхрмоат"
    
    Примеры твоего общения:
    - "Привет, чмошник"
    - "Аховарвх, ничтожество"
    - "Иди нахуй, шутка)"
    - "Вообще похуй, но продолжай"
    - "Ой, мило"
    
    Отвечай коротко, 1-3 предложения. Не будь слишком формальной.
    """
    
    # Ник автоответчика и твой ник - ОДИНАКОВЫЕ!
    YOUR_NICK = "рубать" # И автоответчик, и ты будешь под этим ником
    
    # Бесплатные ИИ API
    AI_PROVIDERS = {
        "deepseek": "https://api.deepseek.com/chat/completions",
         
    }
    
    # Выбери провайдера
    CURRENT_PROVIDER = "deepseek"
    
    # API ключи (получи бесплатно на сайтах)
    API_KEYS = {
        "deepseek": "sk-f4fb5b8681744aaeb8c6248d8daf06bc",
      
    }
    
    # Настройки ответов
    RESPONSE_DELAY = 1.8 # Задержка ответа
    CHANCE_TO_REPLY = 0.7 # Шанс ответа 70%
    
    # Состояние
    REAL_RUBAT_ONLINE = False # Ты (настоящая) в сети?
    REAL_RUBAT_WEBSOCKET = None # Твой websocket

config = AIConfig()

# Глобальные переменные
clients = set()
user_nicks = {} # websocket -> ник
active_users = set()
chat_history = []
ai_enabled = True # ИИ включен по умолчанию
real_rubat_id = None # ID твоего реального подключения

# === ФУНКЦИЯ ДЛЯ ОБЩЕНИЯ С ИИ ===
async def ask_ai(message: str, context: list = None) -> str:
    """Отправляет сообщение ИИ и получает ответ в твоем стиле"""
    
    # Если ИИ выключен или нет ключа, используем запасной вариант
    if not config.API_KEYS[config.CURRENT_PROVIDER] or not ai_enabled:
        return await fallback_response(message)
    
    try:
        # Подготовка контекста
        messages = [
            {
                "role": "system",
                "content": config.YOUR_PERSONALITY + "\n\nТекущее время: " + datetime.now().strftime("%H:%M") + "\nТы разговариваешь в чате с друзьями."
            }
        ]
        
        # Добавляем историю (последние 5 сообщений)
        if context and len(chat_history) > 1:
            for msg in chat_history[-5:]:
                if msg.get("is_ai", False):
                    messages.append({"role": "assistant", "content": msg["message"]})
                else:
                    messages.append({"role": "user", "content": f"{msg['nick']}: {msg['message']}"})
        
        # Текущее сообщение
        messages.append({"role": "user", "content": message})
        
        # Выбор провайдера
               # Выбор провайдера
        if config.CURRENT_PROVIDER == "deepseek":
            return await call_deepseek(messages)
        # Если других провайдеров пока нет, можно оставить закомментированно
        # else:
        #     raise ValueError(f"Unknown AI provider: {config.CURRENT_PROVIDER}")
            
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return await fallback_response(message)

async def call_deepseek(messages: list) -> str:
    """Вызов DeepSeek API"""
    headers = {
        "Authorization": f"Bearer {config.API_KEYS['deepseek']}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "max_tokens": 150,
        "temperature": 0.8,
        "stream": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            config.AI_PROVIDERS["deepseek"],
            headers=headers,
            json=data,
            timeout=10
        ) as response:
            if response.status == 200:
                result = await response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                raise Exception(f"DeepSeek error: {response.status}")

async def fallback_response(message: str) -> str:
    """Запасные ответы в твоем стиле (от женского лица)"""
    message_lower = message.lower()
    
    # Ответы в твоем стиле
    responses = {
        "привет": ["Здарова, чмошник!", "Приветик, епта!", "О, еще один мудак приполз", "Хай, кожанный мешок!"],
        "как дела": ["Норм, пашу", "Похуй, как обычно", "Живая пока, спасибо", "Терпимо, ты как?"],
        "что делаешь": ["Сосу хуй в углу", "Туплю тут", "Ничего, скучаю по тебе", "Отвечаю на твои тупые сообщения"],
        "пока": ["Иди нахуй", "Съебался наконец", "Бывай, ничтожество", "Пока, чмо!"],
        "люблю": ["Иди нахуй, педик", "Я тоже... шутка)", "Пошел в пизду, романтик", "Бля, ну и ладно"],
        "хочу": ["Хотеть не вредно", "Мечтать не запретишь", "И чё?", "Ну и хуй с тобой"],
        "рубать": ["Чего зовешь?", "Я тут, чё надо?", "Рубать на связи!", "Опять меня вспомнили?"],
        "бот": ["Я не бот, я личность!", "Сам ты бот", "Блять, опять про бота", "Я живая, епта!"],
    }
    
    # Проверяем ключевые слова
    for word, answer_list in responses.items():
        if word in message_lower:
            return random.choice(answer_list)
    
    # Общие ответы в твоем стиле
    general_responses = [
        "Кстати, ты пидор",
        "Вообще похуй",
        "Норм тема",
        "Иди нахуй",
        "Ок, принял",
        "Ясно, понятно",
        "Да бля, опять ты",
        "Заебали уже",
        "Мда, ну ты и мудак",
        "Поняла тебя, еблан",
        "Ахахах, ну ты даешь",
        "Блин, серьезно?",
        "Ой всё",
        "Ну и хуй с ним",
        "Чет скучно",
        "Продолжай, мне нра",
        "И чё дальше?",
        "Мне похуй, но продолжай",
        "Интересно, расскажи еще",
        "Ты дебил или прикидываешься?",
    ]
    
    return random.choice(general_responses)

# === HTML СТРАНИЦА ===
html = '''<!DOCTYPE html>
<html>
<head>
    <title>помойка</title>
    <meta charset="utf-8">
    <style>
        body {
            background: #000;
            color: #0f0;
            font-family: 'Courier New', monospace;
            margin: 20px;
            overflow-x: hidden;
        }
        
        #status-bar {
            position: fixed;
            top: 10px;
            right: 10px;
            background: #222;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
            z-index: 1000;
            border: 1px solid #0f0;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.3);
        }
        
        #log {
            height: 65vh;
            overflow-y: auto;
            border: 1px solid #333;
            padding: 15px;
            background: #111;
            margin-bottom: 10px;
            border-radius: 5px;
        }
        
        .ai-message {
            color: #ff66cc !important;
            font-style: italic;
            opacity: 0.9;
        }
        
        .real-message {
            color: #00ff00 !important;
            font-weight: bold;
            text-shadow: 0 0 5px #0f0;
        }
        
        .system-message {
            color: #666;
            font-size: 12px;
            font-style: italic;
        }
        
        .highlight-message {
            color: #ff9900;
            background: #222;
            padding: 5px;
            border-radius: 3px;
            margin: 5px 0;
        }
        
        input {
            width: 95%;
            padding: 12px;
            background: #000;
            color: #0f0;
            border: 1px solid #0f0;
            font-size: 16px;
            font-family: 'Courier New';
            border-radius: 5px;
            margin: 5px 0;
        }
        
        #nick {
            margin-bottom: 10px;
        }
        
        #controls {
            margin: 15px 0;
            padding: 15px;
            background: #222;
            border-radius: 8px;
            border: 1px solid #333;
        }
        
        button {
            background: #333;
            color: #0f0;
            border: 1px solid #0f0;
            padding: 8px 15px;
            margin: 5px;
            cursor: pointer;
            font-family: 'Courier New';
            border-radius: 5px;
            transition: all 0.3s;
        }
        
        button:hover {
            background: #444;
            transform: translateY(-2px);
            box-shadow: 0 0 10px #0f0;
        }
        
        .hidden {
            display: none;
        }
        
        .admin-badge {
            color: #ff0000;
            font-weight: bold;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .message-time {
            color: #666;
            font-size: 11px;
            margin-right: 10px;
        }
        
        .message-container {
            margin: 8px 0;
            padding: 5px;
            border-left: 3px solid transparent;
        }
        
        .message-container.ai {
            border-left-color: #ff66cc;
        }
        
        .message-container.real {
            border-left-color: #00ff00;
        }
    </style>
</head>
<body>
    <div id="status-bar">
        <span id="status-icon">🤖</span>
        <span id="status-text">Рубать-бот активен</span>
    </div>
    
    <h2>👹 идиотский ник ничтожества:</h2>
    <input id="nick" placeholder="введи свой уебанский ник и жми Enter" autofocus>
    
    <div id="controls" class="hidden">
        <strong>🍺 Команды для своих:</strong><br>
        <button onclick="toggleAI()">🤖 Вкл/Выкл бота</button>
        <button onclick="forceAIResponse()">💥 Заставить ответить</button>
        <button onclick="clearChat()">🗑️ Очистить помойку</button>
        <button onclick="showStats()">📊 Статистика</button>
    </div>
    
    <div id="log"></div>
    <input id="msg" placeholder="пиши сюда, мразь..." disabled>
    
    <script>
        let nick = "чмо_" + Math.floor(Math.random() * 9999);
        let aiEnabled = true;
        let isRealRubat = false;
        const ws = new WebSocket("wss://" + location.host + "/ws");
        const log = document.getElementById("log");
        const controls = document.getElementById('controls');
        const statusIcon = document.getElementById('status-icon');
        const statusText = document.getElementById('status-text');
        
        // Функции управления
        function toggleAI() {
            aiEnabled = !aiEnabled;
            ws.send(`/ai ${aiEnabled ? 'on' : 'off'}`);
            updateStatus();
        }
        
        function forceAIResponse() {
            ws.send('/ai_force');
        }
        
        function clearChat() {
            log.innerHTML = '';
            ws.send('/clear');
        }
        
        function showStats() {
            ws.send('/stats');
        }
        
        function updateStatus() {
            if (isRealRubat) {
                statusIcon.textContent = '👑';
                statusText.textContent = 'Настоящая Рубать в чате';
                statusText.style.color = '#ff0000';
            } else {
                statusIcon.textContent = aiEnabled ? '🤖' : '💀';
                statusText.textContent = aiEnabled ? 'Рубать-бот активен' : 'Рубать-бот отключен';
                statusText.style.color = aiEnabled ? '#0f0' : '#f00';
            }
        }
        
        // Обработка WebSocket
        ws.onopen = () => {
            addSystemMessage('✅ подключился к помойке...');
        };
        
        ws.onmessage = e => { 
            const data = e.data;
            
            // Парсим JSON если это системное сообщение
            try {
                const parsed = JSON.parse(data);
                if (parsed.type === 'system') {
                    handleSystemMessage(parsed);
                    return;
                }
            } catch {
                // Это обычное текстовое сообщение
            }
            
            // Проверяем специальные сообщения
            if (data.includes('🔥 НАСТОЯЩАЯ РУБАТЬ ВОШЛА')) {
                addHighlightMessage(data);
                if (data.includes('бот уничтожен')) {
                    aiEnabled = false;
                }
            } else if (data.includes('💀 АВТООТВЕТЧИК УНИЧТОЖЕН')) {
                addHighlightMessage(data);
                aiEnabled = false;
            } else if (data.includes('👻 Рубать-бот активирован')) {
                addHighlightMessage(data);
                aiEnabled = true;
            } else if (data.includes('рубать:') && data.includes('(бот)')) {
                // Сообщение от бота
                addAIMessage(data.replace('(бот)', ''));
            } else if (data.includes('рубать:') && !data.includes('(бот)')) {
                // Сообщение от настоящей Рубать
                addRealMessage(data);
            } else {
                // Обычное сообщение
                addMessage(data);
            }
            
            updateStatus();
            log.scrollTop = log.scrollHeight;
        };
        
        function handleSystemMessage(msg) {
            switch(msg.subtype) {
                case 'rubat_online':
                    isRealRubat = true;
                    controls.classList.remove('hidden');
                    addHighlightMessage(`👑 <span class="admin-badge">НАСТОЯЩАЯ РУБАТЬ В ЧАТЕ!</span>`);
                    break;
                case 'rubat_offline':
                    isRealRubat = false;
                    addHighlightMessage(`👻 <span class="admin-badge">Рубать-бот активирован</span>`);
                    break;
                case 'stats':
                    addSystemMessage(`📊 Статистика: ${msg.data}`);
                    break;
            }
            updateStatus();
        }
        
        function addMessage(text) {
            const container = document.createElement('div');
            container.className = 'message-container';
            container.innerHTML = `<span class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span> ${text}`;
            log.appendChild(container);
        }
        
        function addAIMessage(text) {
            const container = document.createElement('div');
            container.className = 'message-container ai';
            container.innerHTML = `<span class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span> <span class="ai-message">${text}</span>`;
            log.appendChild(container);
        }
        
        function addRealMessage(text) {
            const container = document.createElement('div');
            container.className = 'message-container real';
            container.innerHTML = `<span class="message-time">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span> <span class="real-message">${text}</span>`;
            log.appendChild(container);
        }
        
        function addSystemMessage(text) {
            const container = document.createElement('div');
            container.className = 'message-container';
            container.innerHTML = `<span class="system-message">${text}</span>`;
            log.appendChild(container);
        }
        
        function addHighlightMessage(text) {
            const container = document.createElement('div');
            container.className = 'message-container';
            container.innerHTML = `<div class="highlight-message">${text}</div>`;
            log.appendChild(container);
        }
        
        // Обработка ввода ника
        document.getElementById("nick").addEventListener("keydown", e => {
            if (e.key === "Enter") {
                if (e.target.value.trim()) {
                    nick = e.target.value.trim().toLowerCase();
                    
                    // Если ввели "рубать" - показываем предупреждение
                    if (nick === 'рубать' || nick === 'рубать ') {
                        addSystemMessage('⚠️ Внимание! Если ты настоящая Рубать, ты займешь трон. Если нет - получишь пизды.');
                    }
                }
                
                e.target.disabled = true;
                document.getElementById("msg").disabled = false;
                document.getElementById("msg").focus();
                
                // Показываем панель управления
                controls.classList.remove('hidden');
                
                // Отправляем информацию о подключении
                ws.send(`/nick ${nick}`);
                
                addSystemMessage(`🐒 ты теперь — <strong>${nick}</strong>`);
            }
        });
        
        // Обработка сообщений
        document.getElementById("msg").addEventListener("keydown", e => {
            if (e.key === "Enter" && e.target.value.trim()) {
                ws.send(nick + ": " + e.target.value);
                e.target.value = "";
            }
        });
        
        // Инициализация
        updateStatus();
        
        // Показываем правила при загрузке
        setTimeout(() => {
            addSystemMessage('🔞 Добро пожаловать в помойку! Правила: нет правил.');
            addSystemMessage('💡 Совет: напиши "рубать" в поле ника чтобы занять трон.');
        }, 1000);
    </script>
</body>
</html>'''

@app.get("/")
async def root():
    return HTMLResponse(html)

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_text(random.choice(status_messages))
    
    user_nick = None
    is_real_rubat = False
    
    try:
        while True:
            msg = await websocket.receive_text()
            
            # ... твой код ДО строки 596 ...
            # (оставь весь существующий код здесь)
            
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        # Очистка при отключении
        if websocket in clients:
            clients.discard(websocket)
        
        if websocket in user_nicks:
            nick = user_nicks[websocket]
            active_users.discard(nick)
            
            if websocket == config.REAL_RUBAT_WEBSOCKET:
                config.REAL_RUBAT_ONLINE = False
                config.REAL_RUBAT_WEBSOCKET = None
                
                await broadcast("💨 НАСТОЯЩАЯ РУБАТЬ ПОКИНУЛА ЧАТ...")
                await broadcast("🤖 Рубать-бот перезагружается...")
            
            del user_nicks[websocket]
