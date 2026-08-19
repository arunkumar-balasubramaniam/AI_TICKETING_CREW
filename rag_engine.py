import os
import warnings
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from crewai.tools import tool

# Suppress minor deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

load_dotenv()

INDEX_PATH = "faiss_index"
PDF_FILE_PATH = "skyroute_knowledge_base_full.pdf"


def build_vector_store(pdf_path: str = PDF_FILE_PATH, index_path: str = INDEX_PATH):
    """
    Reads the PDF, creates embeddings, and saves the FAISS index locally.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file '{pdf_path}' not found. Please place it in the project root.")

    print(f"📄 Loading document: {pdf_path}...")
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()

    print("✂️ Splitting document into semantic chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} chunks.")

    print("🧠 Generating embeddings and building FAISS index...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vector_store = FAISS.from_documents(chunks, embeddings)
    
    # Save the index locally for fast access
    vector_store.save_local(index_path)
    print(f"✅ FAISS index saved successfully at '{index_path}'.")
    return vector_store


def get_vector_store(index_path: str = INDEX_PATH):
    """
    Loads existing FAISS index or builds it if not already present.
    """
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    if os.path.exists(index_path):
        return FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    else:
        return build_vector_store(index_path=index_path)


def query_knowledge_base(query: str) -> str:
    """
    Core retrieval function.
    """
    try:
        vector_store = get_vector_store()
        docs_and_scores = vector_store.similarity_search_with_score(query, k=2)
        
        if not docs_and_scores:
            return "No matching records found in the knowledge base."

        results = []
        for i, (doc, score) in enumerate(docs_and_scores, start=1):
            results.append(f"[Snippet {i}]:\n{doc.page_content.strip()}")

        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"Error retrieving knowledge base: {str(e)}"


@tool("SkyRoute Knowledge Base Search")
def search_knowledge_base(query: str) -> str:
    """
    Searches the official SkyRoute Airlines knowledge base and FAQs.
    Use this tool to find information regarding flight booking, baggage rules,
    cancellations, refunds, seat selection, check-in policies, and customer support.
    """
    return query_knowledge_base(query)


if __name__ == "__main__":
    print("Testing FAISS RAG setup...")
    
    test_query = "What is the domestic baggage allowance?"
    print(f"\nTesting Query: '{test_query}'\n")
    
    # Direct test via the helper function
    response = query_knowledge_base(test_query)
    print("--- Retrieval Output ---")
    print(response)