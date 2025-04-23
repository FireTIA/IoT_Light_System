import os
from datetime import datetime
from flask import Blueprint, request, jsonify

note_blueprint = Blueprint('note', __name__)

# Глобальные переменные
BASE_DIR = None
NOTE_DIR = None
DELETED_DIR = None
MODIFY_DIR = None

def init_directories(app):
    """
    Вызывается из main.py, когда приложение уже инициализировано.
    """
    global BASE_DIR, NOTE_DIR, DELETED_DIR, MODIFY_DIR

    BASE_DIR = app.root_path
    NOTE_DIR = os.path.join(BASE_DIR, 'note')
    DELETED_DIR = os.path.join(NOTE_DIR, 'del')
    MODIFY_DIR = os.path.join(NOTE_DIR, 'modify')

    os.makedirs(NOTE_DIR, exist_ok=True)
    os.makedirs(DELETED_DIR, exist_ok=True)
    os.makedirs(MODIFY_DIR, exist_ok=True)

def get_ip():
    return request.remote_addr or 'unknown'

def get_timestamp():
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    time_str = now.strftime("%H-%M-%S")
    return date_str, time_str

@note_blueprint.route('/create', methods=['POST'])
def create_note():
    if not NOTE_DIR:
        return jsonify({'status': 'error', 'message': 'Система заметок не инициализирована'}), 500

    data = request.get_json()
    note_name = data.get('name')
    if not note_name:
        return jsonify({'status': 'error', 'message': 'Имя заметки обязательно'}), 400

    note_file = os.path.join(NOTE_DIR, f"{note_name}.txt")
    if os.path.exists(note_file):
        return jsonify({'status': 'error', 'message': 'Заметка с таким именем уже существует'}), 400

    date_str, time_str = get_timestamp()
    ip = get_ip()

    content = (
        f"1| Date_creation - {date_str}\n"
        f"2| Time_creation - {time_str}\n"
        f"3| Date_modify - {date_str}\n"
        f"4| Time_modify - {time_str}\n"
        f"5| IP_Last_modify - {ip}\n"
        f"6| IP_creation - {ip}\n"
        "7| --- Note start ---\n"
        "8| (Содержимое заметки...)\n"
        "9| --- Note end ---\n"
    )

    try:
        with open(note_file, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    return jsonify({'status': 'success', 'message': f'Заметка {note_name} успешно создана'}), 200

@note_blueprint.route('/save', methods=['POST'])
def save_note():
    if not NOTE_DIR or not MODIFY_DIR:
        return jsonify({'status': 'error', 'message': 'Система заметок не инициализирована'}), 500

    data = request.get_json()
    note_name = data.get('name')
    new_content = data.get('content')
    if not note_name or new_content is None:
        return jsonify({'status': 'error', 'message': 'Имя заметки и новое содержимое обязательны'}), 400

    note_file = os.path.join(NOTE_DIR, f"{note_name}.txt")
    if not os.path.exists(note_file):
        return jsonify({'status': 'error', 'message': 'Заметка не найдена'}), 404

    date_str, time_str = get_timestamp()
    backup_filename = f"{note_name}-{date_str}_{time_str}.txt_mod"
    backup_path = os.path.join(MODIFY_DIR, backup_filename)

    try:
        # Создаём резервную копию
        with open(note_file, 'r', encoding='utf-8') as f:
            current_content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(current_content)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Ошибка при создании резервной копии: {str(e)}'}), 500

    ip = get_ip()
    try:
        with open(note_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Обновляем метаданные
        lines[2] = f"3| Date_modify - {date_str}\n"
        lines[3] = f"4| Time_modify - {time_str}\n"
        lines[4] = f"5| IP_Last_modify - {ip}\n"

        start_idx, end_idx = None, None
        for idx, line in enumerate(lines):
            if '--- Note start ---' in line:
                start_idx = idx
            if '--- Note end ---' in line:
                end_idx = idx
                break

        if start_idx is not None and end_idx is not None:
            new_lines = lines[:start_idx+1]
            new_lines.append(new_content + "\n")
            new_lines.append(lines[end_idx])
            if end_idx + 1 < len(lines):
                new_lines.extend(lines[end_idx+1:])
            lines = new_lines
        else:
            # Если маркеры не найдены – полностью формируем структуру
            lines = [
                f"1| Date_creation - {date_str}\n",
                f"2| Time_creation - {time_str}\n",
                f"3| Date_modify - {date_str}\n",
                f"4| Time_modify - {time_str}\n",
                f"5| IP_Last_modify - {ip}\n",
                f"6| IP_creation - {ip}\n",
                "7| --- Note start ---\n",
                new_content + "\n",
                "9| --- Note end ---\n"
            ]

        with open(note_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Ошибка при сохранении: {str(e)}'}), 500

    return jsonify({'status': 'success', 'message': f'Заметка {note_name} успешно сохранена'}), 200

@note_blueprint.route('/delete', methods=['POST'])
def delete_note():
    if not NOTE_DIR or not DELETED_DIR:
        return jsonify({'status': 'error', 'message': 'Система заметок не инициализирована'}), 500

    data = request.get_json()
    note_name = data.get('name')
    if not note_name:
        return jsonify({'status': 'error', 'message': 'Имя заметки обязательно'}), 400

    note_file = os.path.join(NOTE_DIR, f"{note_name}.txt")
    if not os.path.exists(note_file):
        return jsonify({'status': 'error', 'message': 'Заметка не найдена'}), 404

    date_str, time_str = get_timestamp()
    deleted_filename = f"{note_name}-{date_str}_{time_str}.txt_del"
    deleted_path = os.path.join(DELETED_DIR, deleted_filename)
    try:
        os.rename(note_file, deleted_path)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Ошибка при удалении: {str(e)}'}), 500

    return jsonify({'status': 'success', 'message': f'Заметка {note_name} успешно удалена'}), 200

@note_blueprint.route('/copy', methods=['POST'])
def copy_note():
    if not NOTE_DIR:
        return jsonify({'status': 'error', 'message': 'Система заметок не инициализирована'}), 500

    data = request.get_json()
    note_name = data.get('name')
    new_name = data.get('new_name')
    if not note_name or not new_name:
        return jsonify({'status': 'error', 'message': 'Оригинальное и новое имя заметки обязательны'}), 400

    original_file = os.path.join(NOTE_DIR, f"{note_name}.txt")
    new_file = os.path.join(NOTE_DIR, f"{new_name}.txt")
    if not os.path.exists(original_file):
        return jsonify({'status': 'error', 'message': 'Исходная заметка не найдена'}), 404
    if os.path.exists(new_file):
        return jsonify({'status': 'error', 'message': 'Заметка с новым именем уже существует'}), 400

    try:
        with open(original_file, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(new_file, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Ошибка при копировании: {str(e)}'}), 500

    return jsonify({'status': 'success', 'message': f'Заметка успешно скопирована в {new_name}'}), 200

@note_blueprint.route('/list', methods=['GET'])
def list_notes():
    if not NOTE_DIR:
        return jsonify({'status': 'error', 'message': 'Система заметок не инициализирована'}), 500

    try:
        notes = []
        for filename in os.listdir(NOTE_DIR):
            # Исключаем резервные и удаленные
            if filename.endswith(".txt") and not filename.endswith("_mod") and not filename.endswith("_del"):
                notes.append(filename[:-4])
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    return jsonify({'status': 'success', 'notes': notes}), 200

@note_blueprint.route('/info', methods=['GET'])
def note_info():
    if not NOTE_DIR:
        return jsonify({'status': 'error', 'message': 'Система заметок не инициализирована'}), 500

    note_name = request.args.get('name')
    if not note_name:
        return jsonify({'status': 'error', 'message': 'Имя заметки обязательно'}), 400

    note_file = os.path.join(NOTE_DIR, f"{note_name}.txt")
    if not os.path.exists(note_file):
        return jsonify({'status': 'error', 'message': 'Заметка не найдена'}), 404

    try:
        with open(note_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    return jsonify({'status': 'success', 'content': content}), 200
