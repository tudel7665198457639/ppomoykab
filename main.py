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
    # Твой стиль общения для ИИ
    YOUR_PERSONALITY = """Ты - девушка по имени рубать.
    Твой характер: саркастичная, острая на язык, но добрая внутри.
    Стиль общения: используешь мат, но с юмором.
    
    Твои любимые фразы:
    - "Кстати,"
    - "Вообще,"
    - "Блин,"
    - "Ебать,"
    - "Похуй, но интересно"
    
    Примеры твоего общения:
    - "Привет, чмошник"
    - "Ахахах, ничтожество"
    - "Иди нахуй, шутка)"
    - "Вообще похуй, но продолжай"
    - "Ой, мило"
    
    Отвечай коротко, 1-3 предложения. Не будь слишком формальной.
    НИКОГДА не используй смайлики вроде 😂🤣😭😎🤔.
    """
    
    # Ник автоответчика и твой ник
    YOUR_NICK = "рубать"
    
    # DeepSeek API
    DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
    DEEPSEEK_KEY = "sk-94abb7f70900428782c23f19d01b0dde"  # ⚠️ ЗАМЕНИ ЭТО!
    
    # Настройки ответов
    RESPONSE_DELAY = 1.8
    CHANCE_TO_REPLY = 0.6
    
    # Состояние
    REAL_RUBAT_ONLINE = False
    REAL_RUBAT_WEBSOCKET = None
    AI_ENABLED = True

config = AIConfig()

# Глобальные переменные
clients = set()
user_nicks = {}
active_users = set()
chat_history = []

# === ФУНКЦИЯ ДЛЯ ОБЩЕНИЯ С ИИ ===
async def ask_ai(message: str, context: list = None) -> str:
    """Отправляет сообщение ИИ и получает ответ в твоем стиле"""
    
    # Сначала проверяем ключевые слова
    message_lower = message.lower()
    for keyword, response in keywords_responses.items():
        if keyword in message_lower:
            return response
    
    # Если нет ключевого слова, используем DeepSeek
    if not config.DEEPSEEK_KEY or config.DEEPSEEK_KEY == "sk-тут_твой_ключ":
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
        if chat_history:
            for msg in chat_history[-5:]:
                if msg.get("nick") == config.YOUR_NICK:
                    messages.append({"role": "assistant", "content": msg["message"]})
                else:
                    messages.append({"role": "user", "content": f"{msg['nick']}: {msg['message']}"})
        
        # Текущее сообщение
        messages.append({"role": "user", "content": message})
        
        # Вызов DeepSeek API
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_KEY}",
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
                config.DEEPSEEK_URL,
                headers=headers,
                json=data,
                timeout=10
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_response = result["choices"][0]["message"]["content"].strip()
                    
                    # Чистим ответ если нужно
                    if "рубать:" in ai_response.lower():
                        ai_response = ai_response.split(":", 1)[-1].strip()
                    
                    return ai_response if ai_response else await fallback_response(message)
                else:
                    print(f"DeepSeek error: {response.status}")
                    return await fallback_response(message)
                    
    except Exception as e:
        print(f"Ошибка ИИ: {e}")
        return await fallback_response(message)

async def fallback_response(message: str) -> str:
    """Запасные ответы в твоем стиле"""
    message_lower = message.lower()
    
    # Проверяем ключевые слова еще раз (на всякий случай)
    for keyword, response in keywords_responses.items():
        if keyword in message_lower:
            return response
    
    # Ответы в твоем стиле
    responses = {
        "привет": ["Здарова, чмошник", "Приветик, епта", "О, еще один мудак приполз", "Хай, кожанный мешок"],
        "как дела": ["Норм, пашу", "Похуй, как обычно", "Живая пока, спасибо", "Терпимо, ты как"],
        "что делаешь": ["Сосу хуй в углу", "Туплю тут", "Ничего, скучаю по тебе", "Отвечаю на твои тупые сообщения"],
        "пока": ["Иди нахуй", "Съебался наконец", "Бывай, ничтожество", "Пока, чмо"],
        "люблю": ["Иди нахуй, педик", "Я тоже... шутка", "Пошел в пизду, романтик", "Бля, ну и ладно"],
        "хочу": ["Хотеть не вредно", "Мечтать не запретишь", "И чё", "Ну и хуй с тобой"],
        "рубать": ["Чего зовешь", "Я тут, чё надо", "Рубать на связи", "Опять меня вспомнили"],
        "бот": ["Я не бот, я личность", "Сам ты бот", "Блять, опять про бота", "Я живая, епта"],
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
        "Блин, серьезно",
        "Ой все",
        "Ну и хуй с ним",
        "Чет скучно",
        "Продолжай, мне нра",
        "И чё дальше",
        "Мне похуй, но продолжай",
        "Интересно, расскажи еще",
        "Ты дебил или прикидываешься",
    ]
    
    return random.choice(general_responses)

# === ОСНОВНЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ ЧАТА ===
async def broadcast(message: str):
    """Отправить сообщение всем подключенным клиентам"""
    disconnected = []
    for client in clients:
        try:
            await client.send_text(message)
        except:
            disconnected.append(client)
    
    for client in disconnected:
        clients.discard(client)
        if client in user_nicks:
            del user_nicks[client]

async def handle_command(command: str, websocket, user_nick: str):
    """Обработка команд от пользователей"""
    global config
    
    if command.startswith("/ai "):
        # Команда управления ботом - ТОЛЬКО ДЛЯ НАСТОЯЩЕЙ РУБАТЬ
        if websocket == config.REAL_RUBAT_WEBSOCKET:
            if "on" in command:
                config.AI_ENABLED = True
                await broadcast("Автоответчик включен")
            elif "off" in command:
                config.AI_ENABLED = False
                await broadcast("Автоответчик выключен")
    
    elif command == "/clear" and websocket == config.REAL_RUBAT_WEBSOCKET:
        # Очистка чата - ТОЛЬКО ДЛЯ НАСТОЯЩЕЙ РУБАТЬ
        await broadcast("Чат очищен")
    
    elif command == "/stats" and websocket == config.REAL_RUBAT_WEBSOCKET:
        # Статистика - ТОЛЬКО ДЛЯ НАСТОЯЩЕЙ РУБАТЬ
        stats_msg = f"Онлайн: {len(active_users)} | Сообщений: {len(chat_history)}"
        await websocket.send_text(stats_msg)

async def send_ai_response(user_message: str, sender_nick: str):
    """Отправка ответа от автоответчика"""
    try:
        response = await ask_ai(user_message, chat_history)
        ai_message = f"{config.YOUR_NICK}: {response}"
        
        # Сохраняем в историю
        chat_history.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "nick": config.YOUR_NICK,
            "message": response,
            "is_ai": True
        })
        
        # Отправляем всем
        await broadcast(ai_message)
    except Exception as e:
        print(f"Ошибка при отправке ИИ: {e}")

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
            color: #ff66cc;
            font-style: italic;
        }
        
        .real-message {
            color: #00ff00;
            font-weight: bold;
        }
        
        .system-message {
            color: #666;
            font-size: 12px;
            font-style: italic;
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
            display: none;
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
        }
    </style>
</head>
<body>
    <div id="status-bar">
        <span id="status-text">Рубать-бот активен</span>
    </div>
    
    <h2>идиотский ник ничтожества:</h2>
    <input id="nick" placeholder="введи ник и Enter" autofocus>
    
    <div id="controls">
        <strong>Команды для Рубать:</strong><br>
        <button onclick="toggleAI()">Вкл/Выкл бота</button>
        <button onclick="clearChat()">Очистить помойку</button>
        <button onclick="showStats()">Статистика</button>
    </div>
    
    <div id="log"></div>
    <input id="msg" placeholder="пиши сюда, мразь..." disabled>
    
    <script>
        let nick = "чмо_" + Math.floor(Math.random() * 9999);
        let isRealRubat = false;
        const ws = new WebSocket("wss://" + location.host + "/ws");
        const log = document.getElementById("log");
        const controls = document.getElementById('controls');
        const statusText = document.getElementById('status-text');
        
        // Функции управления
        function toggleAI() {
            ws.send('/ai toggle');
        }
        
        function clearChat() {
            ws.send('/clear');
        }
        
        function showStats() {
            ws.send('/stats');
        }
        
        function updateStatus() {
            if (isRealRubat) {
                statusText.textContent = 'Настоящая Рубать в чате';
                statusText.style.color = '#ff0000';
                controls.style.display = 'block';
            } else {
                statusText.textContent = 'Рубать-бот активен';
                statusText.style.color = '#0f0';
                controls.style.display = 'none';
            }
        }
        
        // Обработка WebSocket
        ws.onopen = () => {
            addMessage('подключился, червь');
        };
        
        ws.onmessage = e => { 
            const data = e.data;
            
            // Системные сообщения о смене статуса
            if (data.includes('НАСТОЯЩАЯ РУБАТЬ ВОШЛА')) {
                isRealRubat = true;
                updateStatus();
                addMessage(data);
            } else if (data.includes('Рубать-бот активирован')) {
                isRealRubat = false;
                updateStatus();
                addMessage(data);
            } else {
                // Обычные сообщения
                addMessage(data);
            }
            
            log.scrollTop = log.scrollHeight;
        };
        
        function addMessage(text) {
            const div = document.createElement('div');
            
            if (text.includes('рубать:') && !text.includes('НАСТОЯЩАЯ')) {
                div.className = 'ai-message';
            } else if (text.includes('рубать:')) {
                div.className = 'real-message';
            } else if (text.includes('подключился') || text.includes('вышел') || text.includes('очищен') || text.includes('Автоответчик')) {
                div.className = 'system-message';
            }
            
            div.innerHTML = text;
            log.appendChild(div);
        }
        
        // Обработка ввода ника
        document.getElementById("nick").addEventListener("keydown", e => {
            if (e.key === "Enter") {
                if (e.target.value.trim()) nick = e.target.value.trim().toLowerCase();
                e.target.disabled = true;
                document.getElementById("msg").disabled = false;
                document.getElementById("msg").focus();
                
                // Отправляем информацию о подключении
                ws.send(`/nick ${nick}`);
                addMessage(`ты теперь — ${nick}`);
            }
        });
        
        // Обработка сообщений
        document.getElementById("msg").addEventListener("keydown", e => {
            if (e.key === "Enter" && e.target.value.trim()) {
                ws.send(`${nick}: ${e.target.value}`);
                e.target.value = "";
            }
        });
        
        // Инициализация
        updateStatus();
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
    
    user_nick = None
    is_real_rubat = False
    
    try:
        # Отправляем приветствие
        await websocket.send_text(random.choice(status_messages))
        
        while True:
            # Получаем сообщение
            data = await websocket.receive_text()
            
            # Обработка команды /nick
            if data.startswith("/nick "):
                new_nick = data[6:].strip().lower()
                old_nick = user_nick
                user_nick = new_nick
                user_nicks[websocket] = new_nick
                
                # Проверяем, это настоящая Рубать?
                if new_nick == config.YOUR_NICK and not config.REAL_RUBAT_ONLINE:
                    # Первый, кто зашел как "рубать" - становится настоящей
                    config.REAL_RUBAT_ONLINE = True
                    config.REAL_RUBAT_WEBSOCKET = websocket
                    is_real_rubat = True
                    
                    # Отправляем всем сообщение
                    await broadcast("НАСТОЯЩАЯ РУБАТЬ ВОШЛА В ЧАТ. АВТООТВЕТЧИК ОТКЛЮЧЕН.")
                    
                elif new_nick == config.YOUR_NICK and config.REAL_RUBAT_ONLINE:
                    # Кто-то пытается зайти как "рубать", но место занято
                    await websocket.send_text("Место Рубать уже занято. Выбери другой ник.")
                    user_nick = f"подделка_{random.randint(1000, 9999)}"
                    user_nicks[websocket] = user_nick
                
                active_users.add(user_nick)
                if old_nick:
                    active_users.discard(old_nick)
            
            # Обработка команд
            elif data.startswith("/"):
                await handle_command(data, websocket, user_nick)
            
            # Обработка обычных сообщений
            elif ": " in data:
                nick, message = data.split(": ", 1)
                
                # Сохраняем в историю
                chat_history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "nick": nick,
                    "message": message,
                    "is_ai": False
                })
                
                # Отправляем сообщение всем
                await broadcast(data)
                
                # Если это не настоящая Рубать и она не в сети - возможен ответ от бота
                if not config.REAL_RUBAT_ONLINE and config.AI_ENABLED and nick != config.YOUR_NICK:
                    if random.random() < config.CHANCE_TO_REPLY:
                        await asyncio.sleep(config.RESPONSE_DELAY)
                        await send_ai_response(message, nick)
            
            # Обработка сообщений без ника
            else:
                await broadcast(data)
                
    except Exception as e:
        print(f"Ошибка в WebSocket: {e}")
    finally:
        # Очистка при отключении
        if websocket in clients:
            clients.discard(websocket)
        
        if websocket in user_nicks:
            nick = user_nicks[websocket]
            active_users.discard(nick)
            
            # Если это была настоящая Рубать
            if websocket == config.REAL_RUBAT_WEBSOCKET:
                config.REAL_RUBAT_ONLINE = False
                config.REAL_RUBAT_WEBSOCKET = None
                
                await broadcast("НАСТОЯЩАЯ РУБАТЬ ПОКИНУЛА ЧАТ.")
                await broadcast("Рубать-бот активирован.")
            
            del user_nicks[websocket]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
