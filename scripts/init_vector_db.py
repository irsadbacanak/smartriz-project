import json
import os

import chromadb


def initialize_chromadb() -> None:
    print("Initializing ChromaDB persistent client...")

    db_path = os.path.join("data", "chroma_db")
    os.makedirs(db_path, exist_ok=True)
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(name="triz_principles")

    json_path = os.path.join("data", "knowledge", "principles.json")
    try:
        with open(json_path, "r", encoding="utf-8") as file:
            raw_data = json.load(file)
    except FileNotFoundError:
        print(f"Error: Could not find {json_path}")
        return

    principles = raw_data.get("principles", raw_data) if isinstance(raw_data, dict) else raw_data
    if not isinstance(principles, list):
        print("Error: principles.json format is not supported.")
        return

    documents = []
    ids = []
    metadatas = []

    print("Processing TRIZ principles...")
    for index, item in enumerate(principles):
        if not isinstance(item, dict):
            continue

        text_content = json.dumps(item, ensure_ascii=False)
        principle_id = item.get("id", index + 1)
        ids.append(f"principle_{principle_id}")
        documents.append(text_content)
        metadatas.append(
            {
                "name": str(item.get("name", "")),
                "source": "triz_principles_json",
            }
        )

    if not documents:
        print("Error: No principles found to embed.")
        return

    # Scripti tekrar çalıştırınca duplicate olmaması için koleksiyonu sıfırla.
    existing_count = collection.count()
    if existing_count > 0:
        collection.delete(ids=collection.get(include=[])["ids"])

    print(f"Embedding {len(documents)} principles. This might take a moment...")
    collection.add(documents=documents, ids=ids, metadatas=metadatas)

    print(f"✅ Successfully loaded {collection.count()} principles into ChromaDB at {db_path}!")


if __name__ == "__main__":
    initialize_chromadb()
