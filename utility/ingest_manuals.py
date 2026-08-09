import os
import uuid
import requests
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, SparseVectorParams, Modifier, SparseVector
from langchain_ollama import OllamaEmbeddings
from unstructured.chunking.title import chunk_by_title
from unstructured.staging.base import dict_to_elements
from fastembed import SparseTextEmbedding

# Configurations
DATA_DIR = "data"
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = "pnc_underwriting_manuals"
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = "nomic-embed-text-v2-moe"
VECTOR_SIZE = 768  # Dimensions for nomic-embed-text
UNSTRUCTURED_API_URL = os.getenv("UNSTRUCTURED_URL", "http://unstructured-api:8000/general/v0/general")

def extract_metadata_from_filename(filename):
    """
    Extracts basic State and LOB metadata from the filename as an example.
    In a production system, this could be driven by a separate manifest file or more complex regex.
    """
    state = "Unknown"
    lob = "Unknown"
    fn_lower = filename.lower()
    
    # Example logic
    if "oh" in fn_lower or "ohio" in fn_lower:
        state = "OH"
    elif "tx" in fn_lower or "texas" in fn_lower:
        state = "TX"
        
    if "auto" in fn_lower:
        lob = "Personal Auto"
    elif "home" in fn_lower or "property" in fn_lower:
        lob = "Property"
        
    return state, lob

def init_qdrant():
    """Initializes connection to Qdrant and creates the collection if it doesn't exist."""
    client = QdrantClient(url=QDRANT_URL)
    
    if client.collection_exists(QDRANT_COLLECTION):
        print(f"Deleting existing Qdrant collection: {QDRANT_COLLECTION} for full re-ingestion.")
        client.delete_collection(collection_name=QDRANT_COLLECTION)
        
    print(f"Creating Qdrant collection: {QDRANT_COLLECTION} with Hybrid Search (Dense & Sparse)")
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={
            "dense": VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                modifier=Modifier.IDF
            )
        }
    )
    return client

def main():
    # Initialize embeddings
    print(f"Initializing Ollama embeddings model '{OLLAMA_MODEL}'...")
    embeddings = OllamaEmbeddings(
        model=OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL
    )
    
    print("Initializing FastEmbed BM25 model...")
    bm25_model = SparseTextEmbedding(model_name="Qdrant/bm25")
    
    # Initialize Qdrant
    qdrant = init_qdrant()
    
    data_path = Path(DATA_DIR)
    if not data_path.exists():
        print(f"Data directory '{DATA_DIR}' not found.")
        return

    pdf_files = list(data_path.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in '{DATA_DIR}'.")
        return

    for pdf_file in pdf_files:
        print(f"\n--- Processing: {pdf_file.name} ---")
        state, lob = extract_metadata_from_filename(pdf_file.name)
        
        # 1. Partition Document
        print("Partitioning PDF with hi_res strategy (extracting tables as HTML) via API...")
        # hi_res is required to parse complex documents and extract tables cleanly
        with open(pdf_file, "rb") as f:
            files = {"files": (pdf_file.name, f, "application/pdf")}
            data = {
                "strategy": "hi_res",
                "infer_table_structure": "true"
            }
            response = requests.post(UNSTRUCTURED_API_URL, files=files, data=data)
            
            if response.status_code != 200:
                print(f"Failed to partition {pdf_file.name}: {response.text}")
                continue
                
            elements = dict_to_elements(response.json())
        
        # 2. Chunking strategy (Parent-Child Strategy)
        print("Chunking by Title (max 1600 characters ~ 400 tokens)...")
        # chunk_by_title groups NarrativeText and Table elements under their respective 
        # Title and Sub-Title headers, inheriting the section context.
        chunks = chunk_by_title(
            elements,
            max_characters=1600,
            multipage_sections=True,
            combine_text_under_n_chars=500
        )
        
        texts_to_embed = []
        metadatas = []
        
        print(f"Generated {len(chunks)} chunks. Preparing vectors...")
        for chunk in chunks:
            text = chunk.text
            
            # Prepare metadata retaining the Parent's context
            # chunk.metadata.section contains the section header text (the Parent)
            metadata = {
                "source": pdf_file.name,
                "state": state,
                "lob": lob,
                "category": chunk.category,
                "section_title": getattr(chunk.metadata, "section", "Unknown Section"),
                "page_number": getattr(chunk.metadata, "page_number", None)
            }
            
            # Extract HTML table structure cleanly
            if chunk.category == "Table" and hasattr(chunk.metadata, "text_as_html"):
                metadata["text_as_html"] = chunk.metadata.text_as_html
            
            texts_to_embed.append(text)
            metadatas.append(metadata)
            
            # Batch process embedding & upserting to keep memory overhead low
            if len(texts_to_embed) >= 50:
                print(f"Embedding & upserting batch of {len(texts_to_embed)} chunks...")
                dense_vectors = embeddings.embed_documents(texts_to_embed)
                sparse_embeddings = list(bm25_model.embed(texts_to_embed))
                
                batch_points = [
                    PointStruct(
                        id=str(uuid.uuid4()),
                        vector={
                            "dense": dense_vec,
                            "sparse": SparseVector(
                                indices=sparse_vec.indices.tolist(),
                                values=sparse_vec.values.tolist()
                            )
                        },
                        payload={"text": txt, **meta}
                    )
                    for dense_vec, sparse_vec, txt, meta in zip(dense_vectors, sparse_embeddings, texts_to_embed, metadatas)
                ]
                qdrant.upsert(collection_name=QDRANT_COLLECTION, points=batch_points)
                
                texts_to_embed = []
                metadatas = []
                
        # Flush remaining chunks
        if texts_to_embed:
            print(f"Embedding & upserting remaining batch of {len(texts_to_embed)} chunks...")
            dense_vectors = embeddings.embed_documents(texts_to_embed)
            sparse_embeddings = list(bm25_model.embed(texts_to_embed))
            
            batch_points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        "dense": dense_vec,
                        "sparse": SparseVector(
                            indices=sparse_vec.indices.tolist(),
                            values=sparse_vec.values.tolist()
                        )
                    },
                    payload={"text": txt, **meta}
                )
                for dense_vec, sparse_vec, txt, meta in zip(dense_vectors, sparse_embeddings, texts_to_embed, metadatas)
            ]
            qdrant.upsert(collection_name=QDRANT_COLLECTION, points=batch_points)
            
        print(f"Successfully processed {pdf_file.name}")

    print("\nAll processing complete. Knowledge base is ready.")

if __name__ == "__main__":
    main()
