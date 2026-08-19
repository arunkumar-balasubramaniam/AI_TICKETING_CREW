import os
import warnings
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from langchain_community.utilities import SerpAPIWrapper

from rag_engine import search_knowledge_base
from google_service import send_email_response

warnings.filterwarnings("ignore", category=DeprecationWarning)
load_dotenv()

crew_llm = LLM(
    model="gpt-4o-mini",
    temperature=0.2,
    max_tokens=400
)

# Tool 1: SerpAPI Web Search Fallback
@tool("Web Search Tool")
def serp_web_search(query: str) -> str:
    """Performs a live Google search via SerpAPI if knowledge base retrieval is insufficient."""
    try:
        search = SerpAPIWrapper()
        return search.run(query)
    except Exception as e:
        return f"Web search failed: {str(e)}"


# Tool 2: Dispatch Threaded Email Response to Customer
@tool("Send Threaded Email Response")
def dispatch_email(customer_recipient_email: str, subject: str, response_body: str,
                   thread_id: str = None, message_id_header: str = None) -> str:
    """
    Sends the drafted response directly to the customer's email address in the existing Gmail thread.
    """
    email_success = send_email_response(
        to_email=customer_recipient_email,
        subject=subject,
        body=response_body,
        thread_id=thread_id,
        message_id_header=message_id_header
    )
    return f"Email Sent to Customer ({customer_recipient_email}): {email_success}"


# --- AGENTS SETUP ---

agent_1_resolver = Agent(
    role="SkyRoute Resolution Specialist",
    goal="Understand customer inquiries. If the user asks about previous conversation history (e.g., 'what was my first question?'), formulate the answer directly using the provided 'Previous Conversation' context. For policy/flight questions, retrieve official policies from FAISS.",
    backstory="You are an intelligent support specialist. You recall previous interactions from the conversation history provided to you, and retrieve airline manual facts for policy queries.",
    tools=[search_knowledge_base],
    llm=crew_llm,
    max_iter=2,
    verbose=True
)

agent_2_validator = Agent(
    role="Support Quality & Verification Auditor",
    goal="Evaluate Agent 1's draft. Assign a Confidence Score (0-100%). If the score is >= 70% (grounded in airline policy manual or conversation history), accept and approve it immediately. Only trigger the web search tool if the confidence score is < 70% due to missing critical policy information.",
    backstory="You are a strict QA auditor ensuring airline responses meet the minimum 70% confidence threshold and preventing unnecessary web searches when internal knowledge is sufficient.",
    tools=[serp_web_search],
    llm=crew_llm,
    verbose=True
)

agent_3_dispatcher = Agent(
    role="Customer Communications Officer",
    goal="Format and send the finalized email response to the customer at '{sender_email}' for Ticket '{ticket_id}', maintaining warm and professional customer service standards.",
    backstory="You ensure threaded email delivery via Gmail directly to the customer's email address.",
    tools=[dispatch_email],
    llm=crew_llm,
    verbose=True
)


# --- PIPELINE ORCHESTRATION ---

def process_ticket(ticket_id: str, sender_email: str, subject: str, customer_query: str, 
                   thread_id: str = None, message_id_header: str = None):
    """
    Executes the 3-agent CrewAI pipeline preserving state, memory, and Gmail thread context.
    """
    print(f"\n🚀 Processing Ticket [{ticket_id}] for Customer: {sender_email} (Thread: {thread_id})...")

    task_1 = Task(
        description=(
            f"Input Data:\n{customer_query}\n\n"
            "Instructions:\n"
            "1. Check if 'Previous Conversation' is present in the input above.\n"
            "2. If the user's latest query is asking about the conversation history (e.g. 'what did I ask earlier?', 'what was my first question?'), answer directly using the conversation history.\n"
            "3. If the user is asking about airline policies/procedures, use 'SkyRoute Knowledge Base Search' to retrieve facts.\n"
            "Draft a helpful, polite response answering the customer's query directly."
        ),
        expected_output="A grounded, polite response answering the customer query using memory context or policy data.",
        agent=agent_1_resolver
    )

    task_2 = Task(
        description=(
            f"Input Data:\n{customer_query}\n\n"
            "Evaluation Instructions:\n"
            "1. Inspect Agent 1's draft response.\n"
            "2. If Agent 1 successfully answered the query using the policy manual or conversation history, assign a Confidence Score >= 80% and mark Source as 'Knowledge Base'. Do NOT use web search.\n"
            "3. If Agent 1 could NOT answer the query (e.g., states 'I couldn't find information' or scores < 70%), you MUST call the 'Web Search Tool' using the customer's question as the search query. Synthesize the live web search findings into a complete, factual answer and mark Source as 'Web Search'.\n"
            "Output format:\n"
            "Score: <number>%\n"
            "Source: <Knowledge Base or Web Search>\n"
            "Final Answer: <the factual answer to send to the customer>"
        ),
        expected_output="Validated factual response with confidence score and source indicator.",
        agent=agent_2_validator
    )

    task_3 = Task(
        description=(
            f"Ticket ID: '{ticket_id}'\n"
            f"Customer Email: '{sender_email}'\n"
            f"Subject: '{subject}'\n"
            f"Thread ID: '{thread_id}'\n"
            f"Message ID Header: '{message_id_header}'\n\n"
            "Format a warm, professional customer service email response from the validated answer.\n"
            f"Call 'Send Threaded Email Response' with customer_recipient_email='{sender_email}', "
            f"subject='{subject}', response_body=<your formatted email>, thread_id='{thread_id}', and message_id_header='{message_id_header}'."
        ),
        expected_output=f"Confirmation that email was dispatched directly to {sender_email}.",
        agent=agent_3_dispatcher
    )

    crew = Crew(
        agents=[agent_1_resolver, agent_2_validator, agent_3_dispatcher],
        tasks=[task_1, task_2, task_3],
        process=Process.sequential,
        verbose=True
    )

    inputs = {
        "ticket_id": ticket_id,
        "sender_email": sender_email,
        "subject": subject,
        "customer_query": customer_query,
        "thread_id": thread_id,
        "message_id_header": message_id_header
    }

    return crew.kickoff(inputs=inputs)