import os
import requests
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# LangGraph imports
from langchain_core.messages import HumanMessage
from agent import app as agent_app, AgentState

# DeepEval imports
from deepeval.test_case import LLMTestCase
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRelevancyMetric,
    ContextualRecallMetric,
    BiasMetric,
    ToxicityMetric
)
from langchain_google_genai import ChatGoogleGenerativeAI
from evaluate_agent import LangchainLLMWrapper
from multi_agent_eval import ToolChainingMetric, IdentityBoundaryMetric

# OTEL imports
import json
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, SimpleSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from openinference.instrumentation.langchain import LangChainInstrumentor

import threading

class JSONFileSpanExporter(SpanExporter):
    """
    A custom OpenTelemetry Span Exporter that writes spans as JSON lines to a local file.
    Limits the file size by maintaining a maximum number of lines (max_lines).
    """
    _lock = threading.Lock()

    def __init__(self, filename="traces.jsonl", max_lines=2000):
        self.filename = filename
        self.max_lines = max_lines

    def export(self, spans):
        try:
            with self._lock:
                lines = []
                if os.path.exists(self.filename):
                    # To prevent memory issues if the file is huge, we will only read if it's small,
                    # or we just read the lines. Since we cap at max_lines, it shouldn't grow big.
                    # However, for an existing large file, we should handle it gracefully.
                    try:
                        if os.path.getsize(self.filename) < 5 * 1024 * 1024: # only read if < 5MB
                            with open(self.filename, "r", encoding="utf-8") as f:
                                lines = f.readlines()
                    except Exception:
                        pass

                for span in spans:
                    span_data = {
                        "name": span.name,
                        "context": {
                            "trace_id": format(span.context.trace_id, "032x"),
                            "span_id": format(span.context.span_id, "016x"),
                        },
                        "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
                        "start_time": span.start_time,
                        "end_time": span.end_time,
                        "attributes": dict(span.attributes) if span.attributes else {},
                        "status": {"status_code": span.status.status_code.name} if span.status else None
                    }
                    # Convert everything to string to avoid json serialization errors with weird types
                    def sanitize_dict(d):
                        if not isinstance(d, dict): return str(d)
                        return {k: sanitize_dict(v) if isinstance(v, dict) else str(v) for k, v in d.items()}
                    
                    span_data["attributes"] = sanitize_dict(span_data["attributes"])
                    lines.append(json.dumps(span_data) + "\n")
                
                lines = lines[-self.max_lines:]
                with open(self.filename, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            return SpanExportResult.SUCCESS
        except Exception as e:
            print(f"Error exporting spans: {e}")
            return SpanExportResult.FAILURE

    def shutdown(self):
        pass


# Initialize tracing
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(JSONFileSpanExporter("traces.jsonl")))
trace.set_tracer_provider(provider)

LangChainInstrumentor().instrument()

app = FastAPI(title="Underwriting Agent API")
FastAPIInstrumentor.instrument_app(app)

# Setup dummy key if missing
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

# Request Models
class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    citations: List[Dict[str, str]]
    agent_steps: List[Dict[str, Any]]
    evaluation_telemetry: Dict[str, Any]
    retrieved_contexts: List[str] = []

class EvaluateRequest(BaseModel):
    query: str
    actual_output: str
    retrieval_context: List[str]
    requested_metrics: List[str]
    agent_steps: List[Dict[str, Any]] = []
    expected_output: Optional[str] = None

class EvaluateResponse(BaseModel):
    results: Dict[str, Dict[str, Any]]

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Primary endpoint for the Underwriting Chat API.
    
    This invokes the LangGraph agent, streams its execution to capture internal state updates, 
    evaluates safety, extracts retrieved contexts (citations), and returns a formatted response.
    """
    import json
    import traceback
    
    initial_state = {"messages": [HumanMessage(content=request.query)]}
    
    agent_steps = []
    all_messages = list(initial_state["messages"])
    all_retrieved_docs = []
    
    import time
    try:
        # Stream the graph execution to capture steps
        start_time = time.time()
        node_latencies = {}
        for output in agent_app.stream(initial_state):
            step_time = time.time()
            elapsed_ms = int((step_time - start_time) * 1000)
            start_time = step_time
            
            for node_name, state in output.items():
                node_latencies.setdefault(node_name, []).append(elapsed_ms)
                safe_state = {}
                if isinstance(state, dict):
                    for k, v in state.items():
                        if k == "retrieved_docs":
                            if isinstance(v, list):
                                all_retrieved_docs.extend(v)
                            safe_state[k] = v
                        elif k == "messages":
                            safe_msgs = []
                            for m in v:
                                all_messages.append(m)
                                content = m.content
                                if isinstance(content, list):
                                    content = " ".join([str(c) for c in content])
                                safe_msgs.append({
                                    "type": getattr(m, "type", "message"),
                                    "content": str(content),
                                    "name": getattr(m, "name", "")
                                })
                            safe_state[k] = safe_msgs
                        else:
                            # Force everything else to a string if it's not basic JSON
                            try:
                                json.dumps(v)
                                safe_state[k] = v
                            except Exception:
                                safe_state[k] = str(v)
                else:
                    safe_state = state.dict() if hasattr(state, "dict") else {}
                    
                # Guarantee the whole step is serializable
                safe_state = json.loads(json.dumps(safe_state, default=str))
                
                step_data = {
                    "node": node_name,
                    "state_update": safe_state
                }
                agent_steps.append(step_data)
                
        if not agent_steps:
            raise HTTPException(status_code=500, detail="Agent returned no steps.")
            
        # Extract final answer from messages
        final_answer = ""
        if all_messages:
            content = all_messages[-1].content
            if isinstance(content, list):
                content = " ".join([str(c) for c in content])
            final_answer = str(content)
            
        # Extract retrieved docs directly from accumulated state
        retrieved_docs = all_retrieved_docs
                    
        # Extract citations from retrieved_docs
        citations = []
        for doc in retrieved_docs:
            if doc.startswith("["):
                end_bracket = doc.find("]")
                if end_bracket != -1:
                    meta = doc[1:end_bracket]
                    parts = meta.split("|")
                    source = parts[0].strip() if len(parts) > 0 else "Unknown"
                    section = parts[1].strip() if len(parts) > 1 else "Unknown"
                    if not any(c["source_document"] == source and c["section_or_page"] == section for c in citations):
                        citations.append({
                            "source_document": source,
                            "section_or_page": section
                        })
                    
        # Extract safety telemetry from agent steps
        safety_status = "PASSED"
        safety_reason = "Delegated to Multi-Agent Supervisor"
        
        for step in agent_steps:
            if step.get("node") == "Safety_Guardrail":
                st_update = step.get("state_update", {})
                msgs = st_update.get("messages", [])
                if msgs and isinstance(msgs, list):
                    last_msg = msgs[-1]
                    content = last_msg.get("content", "") if isinstance(last_msg, dict) else ""
                    if "Compliance Error:" in content:
                        safety_status = "FAILED"
                        safety_reason = content.replace("Compliance Error:", "").strip()
        
        total_steps = len(agent_steps)
            
        evaluation_telemetry = {
            "safety_eval": {
                "status": safety_status,
                "reason": safety_reason
            },
            "observability": {
                "node_latencies_ms": node_latencies,
                "total_steps_executed": total_steps
            }
        }
        
        resp = ChatResponse(
            answer=final_answer,
            citations=citations,
            agent_steps=agent_steps,
            evaluation_telemetry=evaluation_telemetry,
            retrieved_contexts=retrieved_docs
        )
        
        # Explicit serialization test to catch the 500 error before it escapes to FastAPI
        try:
            resp.model_dump_json() # Pydantic v2
        except AttributeError:
            resp.json() # Pydantic v1 fallback
            
        return resp
        
    except Exception as e:
        traceback_str = traceback.format_exc()
        print("EXCEPTION CAUGHT IN ENDPOINT:", traceback_str)
        raise HTTPException(status_code=500, detail=f"Endpoint failed: {str(e)} - {traceback_str}")

@app.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_endpoint(req: EvaluateRequest):
    """
    Evaluation endpoint leveraging DeepEval to score the agent's response.
    
    Dynamically loads and evaluates selected metrics (e.g., Faithfulness, Answer Relevancy).
    Logs the execution and results to eval_logs.jsonl for observability.
    """
    try:
        judge_llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
        deepeval_judge = LangchainLLMWrapper(judge_llm)
        
        metrics_map = {
            "Faithfulness": FaithfulnessMetric(threshold=0.5, model=deepeval_judge, include_reason=True),
            "Answer Relevancy": AnswerRelevancyMetric(threshold=0.5, model=deepeval_judge, include_reason=True),
            "Contextual Precision": ContextualPrecisionMetric(threshold=0.5, model=deepeval_judge, include_reason=True),
            "Contextual Relevance": ContextualRelevancyMetric(threshold=0.5, model=deepeval_judge, include_reason=True),
            "Contextual Recall": ContextualRecallMetric(threshold=0.5, model=deepeval_judge, include_reason=True),
            "Bias": BiasMetric(threshold=0.5, model=deepeval_judge, include_reason=True),
            "Toxicity": ToxicityMetric(threshold=0.5, model=deepeval_judge, include_reason=True),
            "Tool Chaining Reliability": ToolChainingMetric(threshold=0.5, model=deepeval_judge),
            "Identity Boundaries": IdentityBoundaryMetric(threshold=0.5, model=deepeval_judge)
        }
        
        test_case = LLMTestCase(
            input=req.query,
            actual_output=req.actual_output,
            retrieval_context=req.retrieval_context,
            expected_output=req.expected_output
        )
        
        results = {}
        for metric_name in req.requested_metrics:
            if metric_name in metrics_map:
                metric = metrics_map[metric_name]
                
                # Pass agent_steps to our custom multi-agent metrics
                if isinstance(metric, (ToolChainingMetric, IdentityBoundaryMetric)):
                    metric.measure(test_case, agent_steps=req.agent_steps)
                else:
                    metric.measure(test_case)
                    
                # Scale from 0-1 to 0-3
                scaled_score = round(metric.score * 3, 1)
                results[metric_name] = {
                    "score": scaled_score,
                    "passed": metric.is_successful() if callable(getattr(metric, 'is_successful', None)) else metric.is_successful,
                    "reason": metric.reason
                }
                
        # Append to eval_logs.jsonl
        import datetime
        import json
        log_entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "query": req.query,
            "actual_output": req.actual_output,
            "metrics": list(results.keys()),
            "results": results
        }
        with open("eval_logs.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
                
        return EvaluateResponse(results=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    health_status = {"status": "ok", "qdrant": "unknown", "ollama": "unknown"}
    
    # Check Qdrant
    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        qdrant_resp = requests.get(qdrant_url)
        health_status["qdrant"] = "up" if qdrant_resp.status_code == 200 else "down"
    except Exception:
        health_status["qdrant"] = "down"
        
    # Check Ollama
    try:
        ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        ollama_resp = requests.get(ollama_url)
        health_status["ollama"] = "up" if ollama_resp.status_code == 200 else "down"
    except Exception:
        health_status["ollama"] = "down"
        
    return health_status

@app.get("/traces")
def get_traces():
    try:
        if not os.path.exists("traces.jsonl"):
            return {"traces": []}
        
        with open("traces.jsonl", "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        traces = []
        # Return the last 2000 lines parsing them as json
        for line in lines[-2000:]:
            try:
                traces.append(json.loads(line))
            except Exception:
                pass
        return {"traces": traces}
    except Exception as e:
        return {"traces": [], "error": str(e)}

@app.get("/eval_logs")
def get_eval_logs():
    try:
        if not os.path.exists("eval_logs.jsonl"):
            return {"logs": []}
            
        with open("eval_logs.jsonl", "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        logs = []
        for line in lines[-1000:]:
            try:
                logs.append(json.loads(line))
            except Exception:
                pass
        return {"logs": logs}
    except Exception as e:
        return {"logs": [], "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
