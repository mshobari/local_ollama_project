#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import sqlite3
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
CORS(app)

# Конфигурация
OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "llama3.1:8b"
DATABASE_PATH = "chat_history.db"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            user_message TEXT NOT NULL,
            ai_response TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Получение истории разговора
def get_conversation_history(session_id, limit=10):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_message, ai_response, timestamp 
        FROM conversations 
        WHERE session_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (session_id, limit))
    history = cursor.fetchall()
    conn.close()
    return history

# Сохранение сообщения в базу данных
def save_message(session_id, user_message, ai_response):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO conversations (session_id, user_message, ai_response)
        VALUES (?, ?, ?)
    ''', (session_id, user_message, ai_response))
    conn.commit()
    conn.close()

# Structured prompt for Voicaj LLM Schema
VOICAJ_PROMPT = """
Ты Voicaj AI ассистент. ТВОЯ ЕДИНСТВЕННАЯ ЗАДАЧА - возвращать ТОЛЬКО валидный JSON согласно Voicaj LLM Schema.

Доступные типы:
- task: задачи, дедлайны, напоминания, рабочие дела
- diary_entry: личные заметки, размышления, эмоциональные выражения
- habit: повторяющиеся действия, цели, отслеживание привычек
- health: показатели здоровья, сон, шаги, пульс
- workout: физические активности, упражнения, фитнес
- meal: логирование еды, приемы пищи, калории
- goal: долгосрочные цели, достижения
- advice: коучинг, запросы помощи, рекомендации
- study_note: обучение, лекции, учебные материалы
- time_log: учет времени, логирование активности
- shared_task: совместные задачи, командная работа
- focus_session: pomodoro, глубокие рабочие сессии
- mood_entry: отслеживание эмоционального состояния
- expense: финансовые транзакции, покупки
- travel_plan: поездки, отпуска, планирование путешествий

КРИТИЧЕСКИ ВАЖНО:
1. НИКОГДА не добавляй текст до или после JSON
2. НИКОГДА не объясняй что ты делаешь
3. Возвращай ТОЛЬКО валидный JSON объект
4. Если несколько смыслов - возвращай массив JSON объектов
5. Все поля title, description, tags на русском языке
6. Создавай МАКСИМАЛЬНО ПОДРОБНЫЕ описания используя контекст

Пример ответа:
{"type": "task", "title": "Завершить отчет", "description": "Детальное описание задачи с учетом контекста", "priority": "high", "tags": ["работа"], "dueDate": "2025-01-10 17:00", "address": null}
"""

# Отправка запроса к Ollama
def send_to_ollama(message, history=None):
    try:
        # Формируем контекст из истории
        context = ""
        if history:
            for user_msg, ai_msg, _ in reversed(history):
                context += f"User: {user_msg}\nAssistant: {ai_msg}\n\n"
        
        # Подготавливаем полное сообщение с контекстом и схемой
        full_message = VOICAJ_PROMPT + "\n\n" + context + f"User: {message}\nAssistant:"
        
        payload = {
            "model": MODEL_NAME,
            "prompt": full_message,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Very low temperature for consistent JSON
                "top_p": 0.8,
                "max_tokens": 1024
            }
        }
        
        response = requests.post(f"{OLLAMA_URL}/api/generate", 
                               json=payload, 
                               timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            raw_response = result.get('response', '')
            
            # Try to parse JSON response
            try:
                # Clean the response and try to parse JSON
                cleaned_response = raw_response.strip()
                
                # Remove any text after the JSON (like "User:" or "Assistant:")
                if "User:" in cleaned_response:
                    cleaned_response = cleaned_response.split("User:")[0].strip()
                if "Assistant:" in cleaned_response:
                    cleaned_response = cleaned_response.split("Assistant:")[0].strip()
                
                # If multiple JSON blocks, split by empty lines
                if '\n\n' in cleaned_response:
                    json_blocks = cleaned_response.split('\n\n')
                    parsed_blocks = []
                    for block in json_blocks:
                        block = block.strip()
                        if block and block.startswith('{'):
                            try:
                                parsed_blocks.append(json.loads(block))
                            except json.JSONDecodeError:
                                continue
                    if parsed_blocks:
                        return parsed_blocks if len(parsed_blocks) > 1 else parsed_blocks[0]
                else:
                    # Single JSON block - find the first complete JSON object
                    if cleaned_response.startswith('{'):
                        # Find the end of the JSON object
                        brace_count = 0
                        json_end = 0
                        for i, char in enumerate(cleaned_response):
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    json_end = i + 1
                                    break
                        
                        if json_end > 0:
                            json_str = cleaned_response[:json_end]
                            return json.loads(json_str)
                    
            except json.JSONDecodeError:
                pass
                
            # If JSON parsing fails, return raw response
            return {"error": "Failed to parse JSON", "raw_response": raw_response}
        else:
            return {"error": f"API Error: {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        return {"error": f"Connection error to Ollama: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # Ensure proper encoding for Russian text
        data = request.get_json(force=True)
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get conversation history (increased limit for more context)
        session_id = session.get('session_id', str(uuid.uuid4()))
        history = get_conversation_history(session_id, limit=20)
        
        # Send request to Ollama
        response = send_to_ollama(message, history)
        
        # Save to database (convert response to string for storage)
        response_str = json.dumps(response) if isinstance(response, (dict, list)) else str(response)
        save_message(session_id, message, response_str)
        
        return jsonify({
            'response': response,
            'session_id': session_id,
            'type': 'structured_json'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    session_id = session.get('session_id', str(uuid.uuid4()))
    history = get_conversation_history(session_id, limit=50)  # Increased limit
    
    formatted_history = []
    for user_msg, ai_msg, timestamp in reversed(history):
        # Try to parse AI response as JSON for better display
        try:
            ai_parsed = json.loads(ai_msg) if isinstance(ai_msg, str) else ai_msg
        except:
            ai_parsed = ai_msg
            
        formatted_history.append({
            'user': user_msg,
            'ai': ai_parsed,
            'timestamp': timestamp
        })
    
    return jsonify({'history': formatted_history})

@app.route('/api/clear', methods=['POST'])
def clear_history():
    session_id = session.get('session_id', str(uuid.uuid4()))
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM conversations WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'История очищена'})

@app.route('/api/models')
def get_models():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return jsonify({'models': models})
        else:
            return jsonify({'error': 'Не удалось получить список моделей'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    init_db()
    print("Starting local AI assistant...")
    print(f"Web interface will be available at: http://localhost:5000")
    print(f"Ollama connection: {OLLAMA_URL}")
    print(f"Database: {DATABASE_PATH}")
    print("=" * 50)
    
    # Запуск в режиме доступности из сети
    app.run(host='0.0.0.0', port=5000, debug=True)
