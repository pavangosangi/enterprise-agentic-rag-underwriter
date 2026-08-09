import os
import json
import random
from typing import List
from pydantic import BaseModel, Field
import time

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.chat_models import ChatOllama
from qdrant_client import QdrantClient

# Ensure Google API key is set safely via environment variables
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = "pnc_underwriting_manuals"

class Triplet(BaseModel):
    question: str = Field(description="A complex, multi-part question requiring both policy research and mathematical calculation.")
    context: str = Field(description="The exact verbatim quote from the text that provides the policy details needed to answer the question.")
    answer: str = Field(description="The correct interpretation and the final calculated answer.")

class TripletsList(BaseModel):
    triplets: List[Triplet]

def main():
    qdrant = QdrantClient(url=QDRANT_URL)
    
    # Try getting 150 points
    res = qdrant.scroll(collection_name=QDRANT_COLLECTION, limit=150, with_payload=True)[0]
    
    if not res:
        print("No documents found in Qdrant.")
        return

    # Shuffle to get random chunks
    random.seed(42)
    random.shuffle(res)
    
    try:
        # Try Gemini first
        llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)
        llm.invoke("Test")
    except Exception as e:
        print(f"Gemini failed, falling back to Ollama: {e}")
        llm = ChatOllama(base_url=os.getenv("OLLAMA_URL", "http://ollama:11434"), model="llama3.1:8b", temperature=0.2)

    structured_llm = llm.with_structured_output(TripletsList)
    
    all_triplets = []
    
    print(f"Generating 30 agentic evaluation triplets using {llm.__class__.__name__}...")
    
    for point in res:
        if len(all_triplets) >= 10:
            break
            
        text = point.payload.get("text", "")
        if len(text.split()) < 10:
            continue
            
        prompt = f"""
You are an expert underwriter and actuary.
Based on the following text chunk from an underwriting manual, generate 1 or 2 complex 'Question-Context-Answer' triplets designed to test an AI agent's ability to chain multiple tools.

CRITICAL REQUIREMENT: 
The 'question' MUST be a complex, multi-step scenario that requires BOTH:
1. Looking up the specific policy rule or limit from the provided text.
2. Performing a mathematical calculation based on a hypothetical scenario described in the question.

Example Question: "If the manual states the maximum benefit for rental reimbursement is $30/day up to a maximum of $900, and an insured rents a car for 14 days, what is the total amount covered and how much of the maximum limit remains?"

The Context must be the EXACT verbatim quote from the text provided below.
The Answer must be the correct interpretation and include the final result of the mathematical calculation.

Text:
{text}
"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = structured_llm.invoke(prompt)
                if result and result.triplets:
                    for t in result.triplets:
                        # Very simple check
                        if t.context in text or len(t.context) >= 10: 
                            all_triplets.append(t.model_dump())
                            if len(all_triplets) >= 10:
                                break
                    print(f"Generated {len(all_triplets)}/10 agentic triplets so far...")
                time.sleep(2)  # Base sleep to prevent hitting rate limit immediately
                break # Success, exit retry loop
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "503" in error_msg:
                    sleep_time = (attempt + 1) * 15
                    print(f"Rate limited or unavailable. Retrying in {sleep_time} seconds... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(sleep_time)
                else:
                    print(f"Error generating for a chunk: {e}")
                    break # Unhandled error, skip this chunk

    # Save to ground_truth_agentic.json
    output_path = "/app/ground_truth_agentic.json"
    with open(output_path, "w") as f:
        json.dump(all_triplets[:10], f, indent=2)
        
    print(f"Successfully saved {len(all_triplets[:10])} agentic triplets to {output_path}")

if __name__ == "__main__":
    main()
