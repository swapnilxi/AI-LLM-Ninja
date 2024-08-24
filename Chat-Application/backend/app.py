from flask import Flask, jsonify, request
from flask_cors import CORS
from celery import Celery

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)  # Allow all origins and credentials

app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

roles = [
    {"id": 1, "name": "Admin"},
    {"id": 2, "name": "User"},
    {"id": 3, "name": "Guest"},
    {"id": 4, "name": "Moderator"}
]

user_profiles = [
    {"id": 1, "profile": "Admin"},
    {"id": 2, "profile": "User"},
    {"id": 3, "profile": "Guest"},
    {"id": 4, "profile": "Moderator"}
]

profile_options = [
    {"label": "Admin", "value": "admin"},
    {"label": "User", "value": "user"},
    {"label": "Guest", "value": "guest"},
    {"label": "Moderator", "value": "moderator"}
]

chat_data = [
    {"id": 1, "message": "Hello!"},
    {"id": 2, "message": "How are you?"},
    {"id": 3, "message": "What can I help you with today?"}
]

chat_history = [
    {"id": 1, "message": "Hello!"},
    {"id": 2, "message": "How are you?"},
    {"id": 3, "message": "Good, thanks!"},
    {"id": 4, "message": "What's your name?"}
]

rag_analytics = [
    {"id": 1, "metric": "response_time", "value": "100ms"},
    {"id": 2, "metric": "accuracy", "value": "95%"}
]

embedding_flags = [
    {"id": 1, "flag": "is_active", "value": True},
    {"id": 2, "flag": "is_trained", "value": False}
]

embedding_roles = [
    {"id": 1, "role": "Admin", "permissions": ["read", "write", "execute"]},
    {"id": 2, "role": "User", "permissions": ["read", "write"]}
]

card_list = [
    {
        "id": 1,
        "title": "Admin",
        "cardtitle": "Admin",
        "description": "Administrator tasks and settings.",
        "textcolor": "blue",
        "subcards": [
            {
                "title": "User Management",
                "description": "Manage users and permissions.",
                "route": "/user-management",
                "persona": "Admin",
                "active": True
            },
            {
                "title": "System Settings",
                "description": "Configure system-wide settings.",
                "route": "/system-settings",
                "persona": "Admin",
                "active": True
            }
        ]
    },
    {
        "id": 2,
        "title": "Document Owner",
        "cardtitle": "Document Owner",
        "description": "Manage and own documents.",
        "textcolor": "green",
        "subcards": [
            {
                "title": "Document Creation",
                "description": "Create and manage documents.",
                "route": "/document-creation",
                "persona": "Document Owner",
                "active": True
            },
            {
                "title": "Document Review",
                "description": "Review and approve documents.",
                "route": "/document-review",
                "persona": "Document Owner",
                "active": True
            }
        ]
    },
    {
        "id": 3,
        "title": "Auditor",
        "cardtitle": "Auditor",
        "description": "Audit documents and processes.",
        "textcolor": "red",
        "subcards": [
            {
                "title": "Audit Planning",
                "description": "Plan audit activities.",
                "route": "/audit-planning",
                "persona": "Auditor",
                "active": True
            },
            {
                "title": "Audit Execution",
                "description": "Execute audit tasks.",
                "route": "/audit-execution",
                "persona": "Auditor",
                "active": True
            }
        ]
    },
    {
        "id": 4,
        "title": "User",
        "cardtitle": "User",
        "description": "Regular user tasks.",
        "textcolor": "purple",
        "subcards": [
            {
                "title": "Profile Management",
                "description": "Manage your profile.",
                "route": "/profile-management",
                "persona": "User",
                "active": True
            },
            {
                "title": "Settings",
                "description": "Configure user settings.",
                "route": "/user-settings",
                "persona": "User",
                "active": True
            }
        ]
    }
]

icons_list = [
    {"id": 1, "icon": "GridOn"},
    {"id": 2, "icon": "List"},
    {"id": 3, "icon": "Note"},
    {"id": 4, "icon": "CheckBox"},
    {"id": 5, "icon": "TextFields"},
    {"id": 6, "icon": "History"},
    {"id": 7, "icon": "CloseFullscreen"},
    {"id": 8, "icon": "ExpandLess"},
    {"id": 9, "icon": "ExpandMore"}
]

pre_populated_questions = [
    {"id": 1, "question": "What is your name?"},
    {"id": 2, "question": "How can I help you?"},
    {"id": 3, "question": "What are your working hours?"}
]

feedback = []

@app.route('/api/roles', methods=['GET'])
def get_roles():
    return jsonify(roles)

@app.route('/api/user_profiles', methods=['GET'])
def get_user_profiles():
    return jsonify(user_profiles)

@app.route('/api/profile_options', methods=['GET'])
def get_profile_options():
    return jsonify(profile_options)

@app.route('/api/chat_data', methods=['GET'])
def get_chat_data():
    return jsonify(chat_data)

@app.route('/api/chat_history', methods=['GET'])
def get_chat_history():
    return jsonify(chat_history)

@app.route('/api/rag_analytics', methods=['POST'])
def post_rag_analytics():
    data = request.json
    rag_analytics.append(data)
    return jsonify({"status": "success", "data": data}), 201

@app.route('/api/update_embedding_flags', methods=['POST'])
def post_update_embedding_flags():
    data = request.json
    embedding_flags.append(data)
    return jsonify({"status": "success", "data": data}), 201

@app.route('/api/update_embedding_roles', methods=['POST'])
def post_update_embedding_roles():
    data = request.json
    embedding_roles.append(data)
    return jsonify({"status": "success", "data": data}), 201

@app.route('/api/card_list', methods=['GET'])
def get_card_list():
    return jsonify(card_list)

@app.route('/api/icons_list', methods=['GET'])
def get_icons_list():
    return jsonify(icons_list)

@app.route('/api/pre_populated_questions', methods=['GET'])
def get_pre_populated_questions():
    return jsonify(pre_populated_questions)

@app.route('/api/chat_history', methods=['POST'])
def post_chat_history():
    user_id = request.json.get('userId')
    mode = request.json.get('mode')
    persona = request.json.get('persona')
    n = request.json.get('n', 5)
    response = {
        "prompts": [chat['message'] for chat in chat_history][:n],
        "chat_ids": [chat['id'] for chat in chat_history][:n]
    }
    return jsonify({"response": response}), 200

@app.route('/api/chat_id_response', methods=['POST'])
def post_chat_id_response():
    chat_id = request.json.get('chatId')
    response = next((chat for chat in chat_history if chat['id'] == chat_id), None)
    if response:
        return jsonify({"response": response}), 200
    else:
        return jsonify({"error": "Chat ID not found"}), 404

@app.route('/api/save_feedback', methods=['POST'])
def post_save_feedback():
    data = request.json
    feedback.append(data)
    return jsonify({"status": "success", "data": data}), 201

@celery.task(bind=True)
def long_task(self, user_id, chat_id, query, mode, persona):
    import time
    time.sleep(10)  # Simulate long running task
    response = {
        "text": "This is a response from a long task",
        "chat_id": chat_id,
        "doc_metadata": {
            "names": ["doc1", "doc2", "doc3"],
            "paths": ["/path/to/doc1", "/path/to/doc2", "/path/to/doc3"],
            "pages": [1, 2, 3],
            "scores": [0.9, 0.8, 0.7]
        }
    }
    return {"response": response, "query": query}

@app.route('/api/text_query', methods=['POST'])
def post_text_query():
    user_id = request.json.get('userId')
    chat_id = request.json.get('chatId')
    query = request.json.get('query')
    mode = request.json.get('mode')
    persona = request.json.get('persona')
    use_cache = request.json.get('useCache')

    task = long_task.apply_async(args=[user_id, chat_id, query, mode, persona])
    return jsonify({"task_id": task.id}), 202

@app.route('/api/task_status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = long_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'result': task.result,
        }
    else:
        response = {
            'state': task.state,
            'current': 1,
            'total': 1,
            'status': str(task.info),  # this is the exception raised
        }
    return jsonify(response)

@app.route('/api/recommended_prompts', methods=['POST'])
def post_recommended_prompts():
    user_id = request.json.get('userId')
    chat_id = request.json.get('chatId')
    query = request.json.get('query')
    mode = request.json.get('mode')
    persona = request.json.get('persona')
    n = request.json.get('n', 3)

    prompts = [
        {"prompt": f"Recommended prompt {i} for query '{query}'"}
        for i in range(1, n+1)
    ]
    response = {
        "response": prompts
    }
    return jsonify(response), 200

if __name__ == '__main__':
    app.run(debug=True)
