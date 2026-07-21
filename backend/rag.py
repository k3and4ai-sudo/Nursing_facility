import requests
from backend.config import OLLAMA_URL, OLLAMA_EMBED_MODEL
from backend.database import add_memory, search_memories

def get_embedding(text: str) -> list:
    """
    Fetches the vector embedding from Ollama for the given text.
    """
    if not text:
        return []
    
    url = f"{OLLAMA_URL}/api/embeddings"
    payload = {
        "model": OLLAMA_EMBED_MODEL,
        "prompt": text
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json().get("embedding", [])
    except Exception as e:
        print(f"Error calling Ollama embedding API: {e}")
        return []

def store_conversation_memory(user_id: int, user_text: str, ai_text: str):
    """
    Combines a turn of conversation into a chunk, generates its embedding, and saves it.
    """
    memory_chunk = f"利用者: {user_text}\nAI: {ai_text}"
    embedding = get_embedding(memory_chunk)
    if embedding:
        add_memory(user_id, memory_chunk, embedding)
        print(f"Stored conversation memory for user {user_id}")
    else:
        print(f"Failed to store conversation memory due to missing embedding")

def get_relevant_context(user_id: int, current_input: str, limit: int = 3) -> str:
    """
    Finds past relevant conversation segments and returns a formatted context string.
    """
    query_vector = get_embedding(current_input)
    if not query_vector:
        return ""
    
    matched_chunks = search_memories(user_id, query_vector, limit)
    if not matched_chunks:
        return ""
        
    context = "\n=== 過去の会話履歴からの関連情報 ===\n"
    context += "\n---\n".join(matched_chunks)
    context += "\n===================================\n"
    return context
