# AI-LLM-Ninja

A collection of AI and LLM projects, ranging from educational materials to full-stack applications. This repository serves as a portfolio of various works, showcasing different technologies and applications in the field of Artificial Intelligence.

## Projects

### 🤖 AI-Agents

A directory containing various AI agent-related projects.

- **Microsoft's AI Agents Course**: A comprehensive, 10-lesson course created by Microsoft, designed to teach the fundamentals of building AI Agents. It includes code samples, videos, and extra learning resources.
- **Company Analyzer**: An in progress project that was likely intended to be a tool for analyzing company financial data . 
- **Other Agents**: The directory also contains other agent projects such as a `voice_agent` and a `post_agent`.

### 🛍️ Amazon AI Scraping and Research

This project focuses on scraping data from Amazon for research purposes.

- **Amazon Python Scraper**: A set of Python scripts that scrape product information from locally saved Amazon HTML files. It includes separate scrapers for search result pages and individual product pages, and it saves the extracted data to CSV files.

### 💬 Chat Application

A full-stack chat application built with a React frontend and a Flask backend. It's a feature-rich application with a sophisticated backend.

- **Features**:
  - User authentication with roles and permissions (Admin, User, Guest).
  - Real-time chat functionality.
  - Chat history and analytics.
  - Integration with RAG (Retrieval-Augmented Generation) for advanced query handling.
  - Asynchronous task processing using Celery and Redis.



### 🧩 MultiAgent - AgentForge

A full-stack, multi-tenant **multi-agent orchestration platform** (FastAPI + React). See [MultiAgent/README.md](MultiAgent/README.md).

- **Features**:
  - Reusable agents, skills, tools and app connectors (GitHub, Slack, Notion, Jira, Linear, MCP servers, …) that receive org + project context at runtime.
  - Teams with 5 orchestration styles, a visual workflow builder, and cron/interval/webhook automations.
  - Web search + browser tools, document knowledge (agent/project/org), and long-term agent/project memory.
  - Multi-provider models (Claude, OpenAI, Groq, Gemini, Ollama, …) plus an offline mock model.
  - Security: RBAC, encrypted secrets, rate limiting, SSRF protection, audit logs; mobile-responsive dashboard.

### 🛠️ Machine Maintenance Dashboard

A web application built with Flask that serves as a dashboard for monitoring and maintaining industrial machinery.

- **Features**:
  - Predicts the Remaining Useful Life (RUL) of engines.
  - Provides scheduling for maintenance tasks.
  - Tracks inventory of parts and availability of staff.
  - Includes a chat interface for making queries about maintenance data.

### 🧠 RAG Chatbot

A powerful backend service for a Retrieval-Augmented Generation (RAG) chatbot, built using FastAPI.

- **Features**:
  - Allows ingestion of documents in `.txt` and `.pdf` formats.
  - Creates vector embeddings using local models or the OpenAI API.
  - Generates responses using different Large Language Models, including OpenAI's GPT models and models from Groq.
  - Provides a robust API for integration with a frontend.

### 🛒 Shopping Assistant

A full-stack application that is a duplicate of the **Chat Application** project. It has the same Flask backend and React frontend structure.
