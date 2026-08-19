# SkyRoute Autonomous AI Customer Support System

An end-to-end autonomous customer support pipeline built with CrewAI, LangChain, FAISS RAG, and Google Workspace APIs (Gmail & Google Sheets). The system continuously monitors inbound support emails, retrieves grounded policy guidelines, validates confidence with dynamic web search fallback, intercepts prompt injections via lightweight guardrails, and sends threaded email replies while maintaining real-time audit logs.

---

## 🌟 Key Features

* **Multi-Agent Orchestration (CrewAI)**:
  * **Agent 1 (Resolution Specialist)**: Answers queries by searching the internal FAISS vector store.
  * **Agent 2 (Quality & Verification Auditor)**: Evaluates response confidence against a >= 70% threshold. Automatically triggers live external web search fallback (via SerpAPI) if internal knowledge is absent or low confidence.
  * **Agent 3 (Customer Communications Officer)**: Formats customer-ready responses and dispatches threaded replies via Gmail.
* **Deterministic Enterprise Guardrails**: Lightweight, sub-millisecond regex filters that block prompt injections, jailbreaks, and sensitive financial/credential PII leaks prior to LLM execution.
* **Closed-Loop Gmail API Integration**: Detects unread messages, extracts clean conversation text while stripping reply artifacts, maintains thread context, and replies within the same conversation thread.
* **Real-Time Audit Logging**: Streams ticket IDs, confidence scores, knowledge sources, sanitized responses, and execution latency directly into Google Sheets.

---

## 🏗️ System Architecture

Inbound Email ──► [Gmail API Listener]
│
(Input Guardrails)
├── Blocked ──► [Immediate Security Rejection Email + Sheets Log]
└── Safe
▼
[CrewAI 3-Agent Pipeline]
┌───────────────────────────────────────────────────────────┐
│ 1. Resolver (FAISS Vector RAG Search)                     │
│ 2. Auditor (Confidence Score Check: >= 70% vs. SerpAPI)   │
│ 3. Dispatcher (Format & Deliver Final Email)              │
└───────────────────────────────────────────────────────────┘
│
▼
[Gmail Threaded Reply] + [Google Sheets Audit Log]

---

## 📁 Repository Structure

ai_ticketing_crew/
│
├── .env                              # Environment variables & API keys
├── credentials.json                  # Google OAuth2 client credentials
├── token.json                        # Auto-generated OAuth token cache
├── requirements.txt                  # Python dependencies
├── skyroute_knowledge_base_full.pdf  # Airline policy source document
├── faiss_index/                      # Persisted FAISS vector index files
│
├── guardrails.py                     # Security, PII, and injection filters
├── rag_engine.py                     # Vector store loader and retrieval tools
├── google_service.py                 # Gmail API sender & Google Sheets logging
├── crew_pipeline.py                  # CrewAI agents, tasks, and workflow definitions
└── main_listener.py                  # Main polling service loop

---

## ⚙️ Prerequisites & Setup

### 1. Clone the Repository & Set Up Virtual Environment

```bash
git clone <your-repo-url>
cd ai_ticketing_crew

python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

2. Configure Environment Variables (.env)
Create a .env file in the root directory:

OPENAI_API_KEY=your_openai_api_key
SERPAPI_API_KEY=your_serpapi_api_key
GOOGLE_SHEET_NAME=SkyRoute_Ticket_Logs
OTEL_SDK_DISABLED=true
CREWAI_TELEMETRY_OPT_OUT=true

3. Google Cloud API Credentials
Enable Gmail API and Google Sheets API in the Google Cloud Console.

Download your OAuth 2.0 Client ID file and save it as credentials.json in the root folder.

On the first run, the system will open a browser window to authenticate and generate token.json.

🚀 Running the System
Ingest Knowledge Base (Vector Index Creation)

python rag_engine.py

Start the Autonomous Email Listener

python main_listener.py

```

The service polls for unread customer inquiries every 5 seconds, processes requests through the multi-agent pipeline, delivers threaded replies, and writes audit rows into Google Sheets.

---


## 📊 Live Audit Logs & Ticket Monitoring
All customer support queries, retrieval confidence scores, dynamically resolved sources (Knowledge Base vs. Web Search), and response times are logged in real-time to Google Sheets.

🔗 **[View Live SkyRoute Support Audit Logs (Google Sheet)](https://docs.google.com/spreadsheets/d/1PuksTZgb72Pekqv1UUwl8-QEc-rGPpCm6VMP3r17X9M/edit?usp=sharing)**
