import os
import json
from deepeval import evaluate
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric, ContextualPrecisionMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from agent import app, AgentState

# Ensure Google API key is set
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

# 1. Custom DeepEval Judge Wrapper for Langchain LLM
class LangchainLLMWrapper(DeepEvalBaseLLM):
    """
    Adapter class to bridge LangChain LLMs with the DeepEval framework.
    Allows using LangChain models (like Gemini) as custom evaluators/judges.
    """
    def __init__(self, model):
        self.model = model

    def load_model(self):
        return self.model

    def _extract_text(self, content):
        if isinstance(content, list):
            return "".join([c.get("text", "") if isinstance(c, dict) else str(c) for c in content])
        return str(content)

    def generate(self, prompt: str) -> str:
        res = self.model.invoke(prompt)
        return self._extract_text(res.content)

    async def a_generate(self, prompt: str) -> str:
        res = await self.model.ainvoke(prompt)
        return self._extract_text(res.content)

    def get_model_name(self):
        return "Gemini 3.1 Pro"

def main():
    """
    Main evaluation script to benchmark the LangGraph agent against a ground truth dataset.
    Loads questions, queries the agent, and computes DeepEval metrics:
    Faithfulness, Answer Relevancy, and Contextual Precision.
    """
    # 2. Load Ground Truth Data
    print("Loading Ground Truth Data...")
    with open("ground_truth.json", "r") as f:
        ground_truth_data = json.load(f)

    # 3. Initialize the Judge Model using the requested Gemini 3.1 Pro
    print("Initializing Gemini 3.1 Pro Judge...")
    judge_llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
    deepeval_judge = LangchainLLMWrapper(judge_llm)

    # 4. Define Metrics
    print("Initializing Metrics...")
    faithfulness = FaithfulnessMetric(threshold=0.7, model=deepeval_judge, include_reason=True)
    answer_relevancy = AnswerRelevancyMetric(threshold=0.7, model=deepeval_judge, include_reason=True)
    contextual_precision = ContextualPrecisionMetric(threshold=0.7, model=deepeval_judge, include_reason=True)
    
    metrics = [faithfulness, answer_relevancy, contextual_precision]

    test_cases = []
    
    print(f"Generating responses for {len(ground_truth_data)} questions using LangGraph agent...")
    # 5. Execution Logic: Loop through ground_truth.json
    for idx, item in enumerate(ground_truth_data):
        question = item["question"]
        expected_output = item["answer"]
        
        print(f"\n[{idx + 1}/{len(ground_truth_data)}] Asking Agent: {question}")
        
        # Invoke the LangGraph Agent
        state = {"messages": [HumanMessage(content=question)]}
        result = app.invoke(state)
        
        # Extract messages from result
        messages = result.get("messages", []) if isinstance(result, dict) else getattr(result, "messages", [])
        
        actual_output = ""
        if messages:
            actual_output = messages[-1].content
            
        retrieved_contexts = []
        for m in messages:
            if getattr(m, "type", "") == "tool" and "qdrant_retriever_tool" in getattr(m, "name", ""):
                if m.content and m.content != "No relevant documents found.":
                    docs = m.content.split("\n\n---\n\n")
                    retrieved_contexts.extend(docs)
            
        # Ensure actual_output is a string (LangChain Gemini wrapper sometimes returns a list of blocks)
        if isinstance(actual_output, list):
            parts = []
            for item in actual_output:
                if isinstance(item, dict) and "text" in item:
                    parts.append(item["text"])
                else:
                    parts.append(str(item))
            actual_output = " ".join(parts)
        elif not isinstance(actual_output, str):
            actual_output = str(actual_output)

        # Wrap response and retrieved contexts in DeepEval TestCase
        test_case = LLMTestCase(
            input=question,
            actual_output=actual_output,
            expected_output=expected_output,
            retrieval_context=retrieved_contexts
        )
        test_cases.append(test_case)

    # 6. Evaluate Test Cases
    print("\nRunning DeepEval Evaluation...")
    results = evaluate(
        test_cases,
        metrics=metrics
    )
    
    # 7. Output: Generate Final Summary Report
    print("\n" + "="*50)
    print("FINAL EVALUATION SUMMARY REPORT")
    print("="*50)
    
    # Aggregate scores for averaging
    scores = {
        "Faithfulness": [],
        "Answer Relevancy": [],
        "Contextual Precision": []
    }
    
    # results is an EvaluationResult object, so we access test_results
    test_results = getattr(results, "test_results", results)
    for res in test_results:
        for metric_result in res.metrics_data:
            # Map the metric score to the respective list
            if "Faithful" in metric_result.name:
                scores["Faithfulness"].append(metric_result.score)
            elif "Relevancy" in metric_result.name:
                scores["Answer Relevancy"].append(metric_result.score)
            elif "Precision" in metric_result.name:
                scores["Contextual Precision"].append(metric_result.score)
                
    for metric_name, score_list in scores.items():
        if score_list:
            avg = sum(score_list) / len(score_list)
            print(f"Average {metric_name} Score: {avg:.2f}")
        else:
            print(f"Average {metric_name} Score: N/A")

if __name__ == "__main__":
    main()
