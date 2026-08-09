import os
import json
from mcp.server.fastmcp import FastMCP
from deepeval.test_case import LLMTestCase
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric, ContextualPrecisionMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_google_genai import ChatGoogleGenerativeAI

# Ensure Google API key is set
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

# Custom DeepEval Judge Wrapper for Langchain LLM
class LangchainLLMWrapper(DeepEvalBaseLLM):
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

# Create FastMCP server
mcp = FastMCP("DeepEval MCP Server")

# Initialize Judge LLM (using lazy initialization inside tools or globally)
# We initialize globally so we don't recreate it every time
judge_llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0)
deepeval_judge = LangchainLLMWrapper(judge_llm)


@mcp.tool()
def evaluate_faithfulness(input_text: str, actual_output: str, retrieval_context: list[str]) -> str:
    """
    Evaluates the faithfulness of an actual output based on the provided retrieval context.
    Faithfulness checks if the LLM hallucinated facts outside of the retrieval context.
    """
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        retrieval_context=retrieval_context
    )
    metric = FaithfulnessMetric(threshold=0.7, model=deepeval_judge, include_reason=True)
    metric.measure(test_case)
    
    return json.dumps({
        "score": metric.score,
        "is_successful": metric.is_successful(),
        "reason": metric.reason
    })

@mcp.tool()
def evaluate_answer_relevancy(input_text: str, actual_output: str) -> str:
    """
    Evaluates the answer relevancy of an actual output to the input text.
    Answer Relevancy checks if the LLM's answer is directly addressing the question.
    """
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output
    )
    metric = AnswerRelevancyMetric(threshold=0.7, model=deepeval_judge, include_reason=True)
    metric.measure(test_case)
    
    return json.dumps({
        "score": metric.score,
        "is_successful": metric.is_successful(),
        "reason": metric.reason
    })

@mcp.tool()
def evaluate_contextual_precision(input_text: str, actual_output: str, expected_output: str, retrieval_context: list[str]) -> str:
    """
    Evaluates contextual precision. Checks if the relevant context nodes are ranked highly.
    """
    test_case = LLMTestCase(
        input=input_text,
        actual_output=actual_output,
        expected_output=expected_output,
        retrieval_context=retrieval_context
    )
    metric = ContextualPrecisionMetric(threshold=0.7, model=deepeval_judge, include_reason=True)
    metric.measure(test_case)
    
    return json.dumps({
        "score": metric.score,
        "is_successful": metric.is_successful(),
        "reason": metric.reason
    })

if __name__ == "__main__":
    # Runs the MCP server in SSE mode (default port is usually 8000)
    mcp.run(transport='sse')
