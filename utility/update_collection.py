import os
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVectorParams, Modifier, VectorParams, Distance

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = "pnc_underwriting_manuals"

def update_collection():
    client = QdrantClient(url=QDRANT_URL)
    
    if client.collection_exists(QDRANT_COLLECTION):
        print(f"Collection '{QDRANT_COLLECTION}' exists. Dropping for full re-ingestion.")
        client.delete_collection(collection_name=QDRANT_COLLECTION)
        
    print(f"Creating collection '{QDRANT_COLLECTION}' with named dense and sparse vectors...")
    
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config={
            "dense": VectorParams(size=768, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                modifier=Modifier.IDF
            )
        }
    )
    
    print("Collection recreated successfully! You can now ingest data with named vectors.")

if __name__ == "__main__":
    update_collection()
