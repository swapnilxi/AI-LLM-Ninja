
from flask import Flask, jsonify, request
from flask_cors import CORS
from celery import Celery
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_community.llms import Ollama

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5173"}}, supports_credentials=True)


# Celery configuration
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# LangChain and Ollama configuration
langchain_api_key = os.getenv("LANGCHAIN_API_KEY")
if langchain_api_key is None:
    raise ValueError("LANGCHAIN_API_KEY environment variable not set. Please set it in your .env file.")

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = langchain_api_key

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant. Please respond to the user queries"),
        ("user", "Question:{question}")
    ]
)

llm = Ollama(model="llama2")
output_parser = StrOutputParser()
chain = prompt | llm | output_parser

# Example data (existing application data)
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

# Hardcoded data from data.js
chatHistory = [
    {
        "chatId": 1,
        "chatText": 'Can you summarize the impact of inflation on global ...',
        "date": '2024-08-14',
        "rating": 4.5,
    },
    {
        "chatId": 2,
        "chatText": 'What are the key benefits of using AI in healthcare ...',
        "date": '2024-07-13',
        "rating": 4.8,
    },
    {
        "chatId": 3,
        "chatText": 'Give me a quick overview of the latest trends in cybe...',
        "date": '2024-08-08',
        "rating": 4.0,
    },
    {
        "chatId": 4,
        "chatText": 'What is the role of blockchain technology in financi...',
        "date": '2024-07-25',
        "rating": 3.5,
    },
    {
        "chatId": 5,
        "chatText": 'Explain the difference between machine learning and d...',
        "date": '2024-08-15',
        "rating": 4.2,
    },
]

webSearches = [
    {
        "searchId": 1,
        "title": 'Understanding the Impact of Inflation on Global Markets',
        "snippet": 'Inflation affects global markets in various ways, influencing interest rates, consumer prices, and investment strategies.',
        "link": 'https://www.example.com/inflation-global-markets',
        "icon": 'https://www.google.com/favicon.ico',
    },
    {
        "searchId": 2,
        "title": 'AI in Healthcare: Revolutionizing Patient Care',
        "snippet": 'AI technology is transforming healthcare by enabling personalized treatment plans, improving diagnostics, and optimizing workflows.',
        "link": 'https://www.example.com/ai-healthcare',
        "icon": 'https://www.google.com/favicon.ico',
    },
    {
        "searchId": 3,
        "title": 'Latest Cybersecurity Trends to Watch in 2024',
        "snippet": 'Stay ahead of the curve with these emerging cybersecurity trends that are shaping the future of digital protection.',
        "link": 'https://www.example.com/cybersecurity-trends-2024',
        "icon": 'https://www.google.com/favicon.ico',
    },
    {
        "searchId": 4,
        "title": 'Blockchain Technology in Financial Services',
        "snippet": 'Blockchain is redefining financial services by enhancing transparency, reducing fraud, and streamlining transactions.',
        "link": 'https://www.example.com/blockchain-finance',
        "icon": 'https://www.google.com/favicon.ico',
    },
]

# New routes for chatHistories and webSearches
@app.route('/api/chat_history', methods=['GET'])
def get_chat_histories():
    return jsonify(chatHistory)

@app.route('/api/web_searches', methods=['GET'])
def get_web_searches():
    return jsonify(webSearches)

# Task for long operations
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

# New route for LangChain processing
@app.route('/process', methods=['POST'])
def process():
    data = request.json
    input_text = data.get("question")

    if not input_text:
        return jsonify({"error": "No question provided"}), 400

    try:
        response = chain.invoke({"question": input_text})
        return jsonify({"response": response})
    except Exception as e:
        if "404" in str(e):
            return jsonify({"error": "Ollama call failed with status code 404. The model 'llama2' was not found. Ensure the model is pulled using `ollama pull llama2`."}), 404
        else:
            return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# Existing routes

@app.route('/api/generate', methods=['POST'])
def post_text_query():
    user_id = request.json.get('user_id')
    chat_id = request.json.get('chat_id')
    query = request.json.get('query')
    mode = request.json.get('mode')
    persona = request.json.get('persona')
    use_cache = request.json.get('use_cache')

    task = long_task.apply_async(args=[user_id, chat_id, query, mode, persona])
    return jsonify({"task_id": task.id}), 202

@app.route('/api/recommend-prompt', methods=['POST'])
def post_recommended_prompts():
    user_id = request.json.get('user_id')
    chat_id = request.json.get('chat_id')
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

@app.route('/api/save-feedback', methods=['POST'])
def post_save_feedback():
    data = request.json
    feedback.append(data)
    return jsonify({"status": "success", "data": data}), 201

@app.route('/api/update-embeddings-roles', methods=['POST'])
def post_update_embedding_roles():
    data = request.json
    embedding_roles.append(data)
    return jsonify({"status": "success", "data": data}), 201

@app.route('/api/update-embedding-flags', methods=['POST'])
def post_update_embedding_flags():
    data = request.json
    embedding_flags.append(data)
    return jsonify({"status": "success", "data": data}), 201

@app.route('/api/get-rag-analytics-data', methods=['POST'])
def post_rag_analytics_data():
    data = request.json
    rag_analytics.append(data)
    return jsonify({"status": "success", "data": data}), 201

@app.route('/api/upload_documents', methods=['POST'])
def post_upload_documents():
    role = request.args.get('role')
    files = request.files.getlist('files')
    access_roles = request.form.get('access_roles')
    for file in files:
        # Process the file (e.g., save to disk or cloud storage)
        pass
    return jsonify({"status": "success"}), 200

@app.route('/api/recent_uploads', methods=['POST'])
def get_document_upload_status():
    # Return the status of recent uploads
    return jsonify({"uploadedFiles": []}), 200

@app.route('/api/get_roles', methods=['POST'])
def get_guard_rail_roles():
    return jsonify({"roles": roles}), 200

@app.route('/api/profiles/list', methods=['POST'])
def get_guardrail_profiles():
    return jsonify({"profiles": profile_options}), 200

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

@app.route('/api/card_list', methods=['GET'])
def get_card_list():
    return jsonify(card_list)

@app.route('/api/icons_list', methods=['GET'])
def get_icons_list():
    return jsonify(icons_list)

@app.route('/api/pre_populated_questions', methods=['GET'])
def get_pre_populated_questions():
    return jsonify(pre_populated_questions)

if __name__ == '__main__':
    app.run(debug=True)


