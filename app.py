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

# Отправка запроса к Ollama
def send_to_ollama(message, history=None):
    try:
        # Формируем контекст из истории
        context = ""
        if history:
            for user_msg, ai_msg, _ in reversed(history):
                context += f"Пользователь: {user_msg}\nАссистент: {ai_msg}\n\n"
        
        # Подготавливаем полное сообщение с контекстом
        full_message = context + f"Пользователь: {message}\nАссистент:"
        
        payload = {
            "model": MODEL_NAME,
            "prompt": full_message,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 2048
            }
        }
        
        response = requests.post(f"{OLLAMA_URL}/api/generate", 
                               json=payload, 
                               timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', 'Извините, не удалось получить ответ.')
        else:
            return f"Ошибка API: {response.status_code}"
            
    except requests.exceptions.RequestException as e:
        return f"Ошибка подключения к Ollama: {str(e)}"
    except Exception as e:
        return f"Произошла ошибка: {str(e)}"

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({'error': 'Сообщение не может быть пустым'}), 400
        
        # Получаем историю разговора
        session_id = session.get('session_id', str(uuid.uuid4()))
        history = get_conversation_history(session_id, limit=5)
        
        # Отправляем запрос к Ollama
        response = send_to_ollama(message, history)
        
        # Сохраняем в базу данных
        save_message(session_id, message, response)
        
        return jsonify({
            'response': response,
            'session_id': session_id
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history')
def get_history():
    session_id = session.get('session_id', str(uuid.uuid4()))
    history = get_conversation_history(session_id, limit=20)
    
    formatted_history = []
    for user_msg, ai_msg, timestamp in reversed(history):
        formatted_history.append({
            'user': user_msg,
            'ai': ai_msg,
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
    print("Запуск локального AI-ассистента...")
    print(f"Веб-интерфейс будет доступен по адресу: http://localhost:5000")
    print(f"Подключение к Ollama: {OLLAMA_URL}")
    print(f"База данных: {DATABASE_PATH}")
    print("=" * 50)
    
    # Запуск в режиме доступности из сети
    app.run(host='0.0.0.0', port=5000, debug=True)
