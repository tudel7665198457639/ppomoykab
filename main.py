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
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Твой уникальный пароль для входа
REAL_RUBAT_PASSWORD = "kotiki"  # Смени на свой

status_messages = [
    "Server groans to life for scum.",
    "Waking up for worthless worms.",
    "Preparing torment for trash.",
    "Hell's gate opens for losers.",
    "Bootstrapping for bottom-feeders."
]

# === НАСТРОЙКИ АВТООТВЕТЧИКА ===
class AIConfig:
    # ИИ должен имитировать тебя на 100%
    YOUR_PERSONALITY = """Ты - девушка по имени Рубать. Твои черты:
    - Грубая, но с юмором
    - Используешь мат как запятые
    - Любишь слова: чмошник, мудак, пидор, ебать, похуй
    - Отвечаешь коротко (1-2 предложения)
    - НИКОГДА не используешь смайлики или эмодзи
    - Часто начинаешь с: Кстати, Вообще, Блин, Ой
    - Иногда говоришь "шутка)" после оскорблений
    
    Пример твоего общения:
    "Привет, чмошник"
    "Иди нахуй, шутка)"
    "Вообще похуй"
    "Бля, ну и ладно"
    "Мне скучно, развлекай"
    """
    
    YOUR_NICK = "рубать"  # Автоответчик использует ТВОЙ ник
    
    # API настройки
    DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
    DEEPSEEK_KEY = "sk-94abb7f70900428782c23f19d01b0dde"  # ⚠️ ЗАМЕНИ НА РЕАЛЬНЫЙ КЛЮЧ!
    
    # Режимы работы
    RESPONSE_DELAY = random.uniform(2, 4)  # Случайная задержка
    REPLY_CHANCE = 0.5  # 50% шанс ответить
    
    # Состояния
    REAL_RUBAT_CONNECTED = False  # Настоящая ты онлайн?
    REAL_RUBAT_WS = None  # Твой WebSocket
    AUTO_ANSWERER_ACTIVE = True  # Автоответчик работает

config = AIConfig()

# Глобальные переменные
clients = set()
user_nicks = {}
active_users = set()
chat_history = []
ai_response_count = 0  # Счётчик ответов автоответчика

# === ИИ ФУНКЦИИ ===
async def ask_ai(message: str, nick: str) -> str:
    """Получить ответ от ИИ в твоём стиле"""
    try:
        if not config.DEEPSEEK_KEY or config.DEEPSEEK_KEY == "sk-тут_твой_ключ":
            return await fallback_response(message)
        
        headers = {
            "Authorization": f"Bearer {config.DEEPSEEK_KEY}",
            "Content-Type": "application/json"
        }
        
        # Подготовка контекста
        system_prompt = f"""{config.YOUR_PERSONALITY}

        Сейчас {datetime.now().strftime('%H:%M')}
        Ты в чате с друзьями. Тебе пишет {nick}.
        Будь собой - грубой, но смешной. Отвечай как живой человек.
        """
        
        # Добавляем последние сообщения для контекста
        messages = [{"role": "system", "content": system_prompt}]
        
        if chat_history:
            for msg in chat_history[-4:]:  # Берем последние 4 сообщения
                if msg["nick"] == config.YOUR_NICK:
                    messages.append({"role": "assistant", "content": msg["message"]})
                else:
                    messages.append({"role": "user", "content": f"{msg['nick']}: {msg['message']}"})
        
        messages.append({"role": "user", "content": f"{nick}: {message}"})
        
        data = {
            "model": "deepseek-chat",
            "messages": messages,
            "max_tokens": 100,
            "temperature": 0.9,
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
                    response_text = result["choices"][0]["message"]["content"].strip()
                    
                    # Чистим ответ от мусора
                    if "Assistant:" in response_text:
                        response_text = response_text.split("Assistant:")[-1].strip()
                    if "assistant:" in response_text:
                        response_text = response_text.split("assistant:")[-1].strip()
                    
                    return response_text if response_text else await fallback_response(message)
                else:
                    logger.error(f"API error: {response.status}")
                    return await fallback_response(message)
                    
    except Exception as e:
        logger.error(f"ИИ ошибка: {e}")
        return await fallback_response(message)

async def fallback_response(message: str) -> str:
    """Запасные ответы если ИИ не работает"""
    message_lower = message.lower()
    
    # Ответы в твоём стиле
    your_responses = [
        "Иди нахуй",
        "Похуй",
        "Бля, ну и ладно",
        "Чет скучно",
        "Мне похуй, но продолжай",
        "Ахахах, ничтожество",
        "Ой все",
        "Шутка)",
        "Норм тема",
        "Ты дебил?",
        "Сам такой",
        "Заебали уже",
        "И чё?",
        "Ну и хуй с ним",
        "Кстати, ты пидор",
        "Вообще, отвали",
        "Блин, опять ты",
        "Ебать, скукота",
        "Поняла тебя, еблан",
        "Хуй тебе, а не ответ"
    ]
    
    # Ответы на конкретные фразы
    if "привет" in message_lower:
        return random.choice(["Здарова, чмошник", "Приветик, мудак", "Хай, пидор"])
    elif "как дела" in message_lower:
        return random.choice(["Норм, пашу", "Похуй как всегда", "Живая пока"])
    elif "что делаешь" in message_lower:
        return random.choice(["Туплю тут", "Скучаю по тебе", "Отвечаю мудакам"])
    elif "рубать" in message_lower:
        return random.choice(["Чего зовешь?", "Я тут, чё надо", "Опять меня?"])
    elif "бот" in message_lower:
        return "Сам ты бот, пидор"
    
    return random.choice(your_responses)

async def broadcast(message: str):
    """Отправить сообщение всем"""
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
        
        #status {
            position: fixed;
            top: 10px;
            right: 10px;
            background: #111;
            padding: 8px 12px;
            border: 1px solid #0f0;
            border-radius: 8px;
            font-size: 12px;
            z-index: 1000;
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
        
        .message {
            margin: 5px 0;
            padding: 3px 0;
        }
        
        .system {
            color: #666;
            font-size: 12px;
            font-style: italic;
        }
        
        .rubat {
            color: #ff66cc;
            font-weight: bold;
        }
        
        .real-rubat {
            color: #ff0000;
            font-weight: bold;
            text-shadow: 0 0 5px #ff0000;
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
    <div id="status">🤖 Автоответчик активен</div>
    
    <h2>введи ник и нажми Enter:</h2>
    <input id="nick" placeholder="твой ник..." autofocus>
    
    <div id="controls">
        <strong>Секретные команды:</strong><br>
        <button onclick="sendCommand('/ai off')">Выключить автоответчика</button>
        <button onclick="sendCommand('/ai on')">Включить автоответчика</button>
        <button onclick="sendCommand('/stats')">Статистика</button>
    </div>
    
    <div id="log"></div>
    <input id="msg" placeholder="пиши сюда..." disabled>
    
    <script>
        let nick = "чмо_" + Math.floor(Math.random() * 9999);
        let isRealRubat = false;
        let ws = null;
        
        function connect() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(protocol + '//' + location.host + '/ws');
            
            ws.onopen = () => {
                addMessage('<span class="system">подключился, червь</span>');
                ws.send(`/nick ${nick}`);
            };
            
            ws.onmessage = (e) => {
                const data = e.data;
                
                // Обработка системных сообщений
                if (data.includes('АВТООТВЕТЧИК УНИЧТОЖЕН')) {
                    isRealRubat = true;
                    document.getElementById('status').innerHTML = '🔥 НАСТОЯЩАЯ РУБАТЬ В ЧАТЕ';
                    document.getElementById('status').style.color = '#ff0000';
                    document.getElementById('controls').style.display = 'block';
                } else if (data.includes('Рубать-бот активирован')) {
                    isRealRubat = false;
                    document.getElementById('status').innerHTML = '🤖 Автоответчик активен';
                    document.getElementById('status').style.color = '#0f0';
                    document.getElementById('controls').style.display = 'none';
                }
                
                // Добавление сообщения в лог
                addMessage(formatMessage(data));
                document.getElementById('log').scrollTop = document.getElementById('log').scrollHeight;
            };
            
            ws.onclose = () => {
                addMessage('<span class="system">соединение потеряно... переподключение через 3 сек</span>');
                setTimeout(connect, 3000);
            };
        }
        
        function formatMessage(text) {
            if (text.includes('рубать:')) {
                if (text.includes('НАСТОЯЩАЯ')) {
                    return `<div class="message real-rubat">${text}</div>`;
                }
                return `<div class="message rubat">${text}</div>`;
            } else if (text.includes('подключился') || text.includes('вышел') || text.includes('Автоответчик')) {
                return `<div class="message system">${text}</div>`;
            }
            return `<div class="message">${text}</div>`;
        }
        
        function addMessage(html) {
            document.getElementById('log').innerHTML += html;
        }
        
        function sendCommand(cmd) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(cmd);
            }
        }
        
        // Обработка ввода ника
        document.getElementById('nick').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.value.trim()) {
                nick = e.target.value.trim().toLowerCase();
                e.target.disabled = true;
                document.getElementById('msg').disabled = false;
                document.getElementById('msg').focus();
                
                // Если это рубать - запроси пароль
                if (nick === 'рубать') {
                    const password = prompt('Введи секретный пароль:');
                    if (password) {
                        ws.send(`/auth ${password}`);
                    } else {
                        nick = 'фейк_' + Math.floor(Math.random() * 9999);
                        ws.send(`/nick ${nick}`);
                    }
                } else {
                    ws.send(`/nick ${nick}`);
                }
                
                addMessage(`<span class="system">ты теперь — ${nick}</span>`);
            }
        });
        
        // Обработка сообщений
        document.getElementById('msg').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && e.target.value.trim()) {
                ws.send(`${nick}: ${e.target.value}`);
                e.target.value = '';
            }
        });
        
        // Начальное подключение
        connect();
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
        # Приветствие
        await websocket.send_text(random.choice(status_messages))
        
        while True:
            data = await websocket.receive_text()
            
            # Команда /nick
            if data.startswith("/nick "):
                new_nick = data[6:].strip().lower()
                old_nick = user_nick
                user_nick = new_nick
                user_nicks[websocket] = new_nick
                
                if old_nick:
                    active_users.discard(old_nick)
                active_users.add(new_nick)
                
                # Уведомление о входе
                await broadcast(f"{new_nick} подключился")
                
            # Команда /auth (для входа как настоящая рубать)
            elif data.startswith("/auth "):
                password = data[6:].strip()
                if password == REAL_RUBAT_PASSWORD and not config.REAL_RUBAT_CONNECTED:
                    # Ты вошла как настоящая!
                    config.REAL_RUBAT_CONNECTED = True
                    config.REAL_RUBAT_WS = websocket
                    config.AUTO_ANSWERER_ACTIVE = False
                    is_real_rubat = True
                    
                    # Уничтожаем автоответчика с приколом
                    await broadcast("⚡⚡⚡ АВТООТВЕТЧИК УНИЧТОЖЕН ⚡⚡⚡")
                    await broadcast(f"НАСТОЯЩАЯ РУБАТЬ ВОШЛА В ЧАТ")
                    await broadcast(f"Автоответчик отправлял сообщения {ai_response_count} раз, пока меня не было")
                    await broadcast("Теперь я сама тут, мудаки")
                    
                else:
                    await websocket.send_text("Неверный пароль или место уже занято")
                    
            # Обычное сообщение
            elif ": " in data:
                nick, message = data.split(": ", 1)
                
                # Сохраняем в историю
                chat_history.append({
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "nick": nick,
                    "message": message,
                    "is_real_rubat": (nick == config.YOUR_NICK and config.REAL_RUBAT_CONNECTED)
                })
                
                # Отправляем всем
                await broadcast(data)
                
                # Автоответчик отвечает, если:
                # 1. Он включен
                # 2. Настоящая рубать не в сети
                # 3. Это не сообщение от "рубать"
                # 4. Случайное число проходит
                if (config.AUTO_ANSWERER_ACTIVE and 
                    not config.REAL_RUBAT_CONNECTED and 
                    nick != config.YOUR_NICK and 
                    random.random() < config.REPLY_CHANCE):
                    
                    # Случайная задержка
                    await asyncio.sleep(config.RESPONSE_DELAY)
                    
                    # Получаем ответ от ИИ
                    ai_response = await ask_ai(message, nick)
                    
                    # Формируем сообщение
                    ai_message = f"{config.YOUR_NICK}: {ai_response}"
                    
                    # Сохраняем и отправляем
                    chat_history.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "nick": config.YOUR_NICK,
                        "message": ai_response,
                        "is_real_rubat": False
                    })
                    
                    ai_response_count += 1
                    await broadcast(ai_message)
            
            # Команды для настоящей рубать
            elif data.startswith("/"):
                if websocket == config.REAL_RUBAT_WS:
                    if data == "/ai off":
                        config.AUTO_ANSWERER_ACTIVE = False
                        await broadcast("Автоответчик выключен")
                    elif data == "/ai on":
                        config.AUTO_ANSWERER_ACTIVE = True
                        await broadcast("Автоответчик включен")
                    elif data == "/stats":
                        stats = f"Сообщений: {len(chat_history)} | Онлайн: {len(active_users)} | Ответов автоответчика: {ai_response_count}"
                        await websocket.send_text(stats)
                        
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Очистка при отключении
        clients.discard(websocket)
        if websocket in user_nicks:
            nick = user_nicks[websocket]
            active_users.discard(nick)
            
            # Если это была настоящая рубать
            if websocket == config.REAL_RUBAT_WS:
                config.REAL_RUBAT_CONNECTED = False
                config.REAL_RUBAT_WS = None
                config.AUTO_ANSWERER_ACTIVE = True
                
                await broadcast("🔥 НАСТОЯЩАЯ РУБАТЬ ПОКИНУЛА ЧАТ")
                await broadcast("Рубать-бот активирован")
                await broadcast("Продолжайте общение с автоответчиком, мудаки")
            
            if nick:
                await broadcast(f"{nick} вышел")
            
            del user_nicks[websocket]

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
