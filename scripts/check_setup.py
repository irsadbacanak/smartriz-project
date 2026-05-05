import os

import chromadb
import requests
from dotenv import load_dotenv
from openai import OpenAI


def check_deepinfra() -> bool:
    print("1. Checking DeepInfra API...")
    load_dotenv()
    api_key = os.getenv("DEEPINFRA_API_KEY")

    if not api_key:
        print("   ❌ Failed: DEEPINFRA_API_KEY not found in .env file.")
        return False

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepinfra.com/v1/openai",
    )

    try:
        client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            messages=[{"role": "user", "content": "Say 'hello'."}],
            max_tokens=10,
        )
        print("   ✅ DeepInfra API is working.")
        return True
    except Exception as error:
        print(f"   ❌ DeepInfra API Error: {error}")
        return False


def check_ollama() -> bool:
    print("2. Checking Local Ollama Server...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [model.get("name", "unknown") for model in models]
            joined_names = ", ".join(model_names) if model_names else "(no models found)"
            print(f"   ✅ Ollama is running. Available models: {joined_names}")
            return True

        print(f"   ❌ Ollama returned status code: {response.status_code}")
        return False
    except requests.exceptions.ConnectionError:
        print("   ❌ Failed to connect to Ollama. Make sure the Ollama app is running.")
        return False
    except requests.exceptions.Timeout:
        print("   ❌ Ollama request timed out.")
        return False


def check_chromadb() -> bool:
    print("3. Checking ChromaDB Vector Database...")
    db_path = os.path.join("data", "chroma_db")

    if not os.path.exists(db_path):
        print("   ❌ ChromaDB folder not found in data/ directory.")
        return False

    try:
        client = chromadb.PersistentClient(path=db_path)
        collection = client.get_collection(name="triz_principles")
        count = collection.count()
        print(f"   ✅ ChromaDB is working. Found {count} embedded principles.")
        return True
    except Exception as error:
        print(f"   ❌ ChromaDB Error: {error}")
        return False


if __name__ == "__main__":
    print("=== System Setup Validation ===\n")

    deepinfra_ok = check_deepinfra()
    ollama_ok = check_ollama()
    chroma_ok = check_chromadb()

    print("\n=== Final Report ===")
    if deepinfra_ok and ollama_ok and chroma_ok:
        print("🚀 All systems are ready! Week 1 tasks are successfully completed.")
    else:
        print("⚠️ Some systems failed. Please check the errors above before proceeding.")
