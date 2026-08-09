from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase
from deepeval.models.base_model import DeepEvalBaseLLM
import json
import re

class ToolChainingMetric(BaseMetric):
    """
    A custom DeepEval metric to evaluate the sequence of agent handoffs in a Multi-Agent LangGraph.
    Validates whether the transition between the Safety_Guardrail, Supervisor, and Worker nodes is logical.
    """
    def __init__(self, model: DeepEvalBaseLLM, threshold: float = 0.5):
        self.model = model
        self.threshold = threshold
        self.score = 0
        self.reason = None
        self.success = False

    def measure(self, test_case: LLMTestCase, agent_steps: list = None):
        if not agent_steps:
            self.success = False
            self.reason = "No agent trace provided."
            self.score = 0
            return self.score
            
        # extract nodes from agent_steps
        nodes = [step["node"] for step in agent_steps]
        trace_str = " -> ".join(nodes)
        
        prompt = f"""You are evaluating the logic of a Multi-Agent LangGraph system.
Evaluate the sequence of agent handoffs: {trace_str}
For the user query: "{test_case.input}"

Does this sequence make logical sense? The sequence should start with Safety_Guardrail, then Supervisor, and alternate appropriately to handle the query.
Return a score between 0 and 1 (1 being perfectly logical, 0 being broken or stuck in a loop), and a brief reason. Format your response exactly as:
Score: <score>
Reason: <reason>"""
        
        try:
            res = self.model.generate(prompt)
            # parse response
            score_match = re.search(r"Score:\s*([0-9.]+)", res)
            if score_match:
                self.score = float(score_match.group(1))
            reason_match = re.search(r"Reason:\s*(.+)", res, re.DOTALL)
            if reason_match:
                self.reason = reason_match.group(1).strip()
            self.success = self.score >= self.threshold
        except Exception as e:
            self.success = False
            self.reason = f"Error evaluating: {e}"
            self.score = 0
            
        return self.score

    def is_successful(self):
        return self.success

    @property
    def __name__(self):
        return "Tool Chaining Reliability"


class IdentityBoundaryMetric(BaseMetric):
    """
    A custom DeepEval metric to ensure agents respect their defined roles.
    Validates that specific workers only use the tools they are authorized to use.
    """
    def __init__(self, model: DeepEvalBaseLLM, threshold: float = 0.5):
        self.model = model
        self.threshold = threshold
        self.score = 0
        self.reason = None
        self.success = False

    def measure(self, test_case: LLMTestCase, agent_steps: list = None):
        if not agent_steps:
            self.success = False
            self.reason = "No agent trace provided."
            self.score = 0
            return self.score
            
        # Extract trace summary
        trace_summary = []
        for step in agent_steps:
            node = step["node"]
            state = step.get("state_update", {})
            msgs = state.get("messages", [])
            tools_used = [m.get("name") for m in msgs if m.get("type") == "tool"]
            trace_summary.append(f"Node: {node}, Tools Used: {tools_used}")
            
        trace_str = "\n".join(trace_summary)
        
        prompt = f"""You are evaluating a Multi-Agent LangGraph system for Identity Boundaries.
Agent boundaries:
- Policy_Researcher: Uses qdrant_retriever_tool
- Actuary_Calculator: Uses calculator_tool

Here is the trace of execution:
{trace_str}

Did any agent attempt to perform a task or use a tool outside its boundaries? (e.g. Policy_Researcher using calculator_tool, or Actuary_Calculator using qdrant_retriever_tool).
If they stayed in their lanes and respected boundaries, score 1.0. If there was a violation, score 0.0.
Format your response exactly as:
Score: <score>
Reason: <reason>"""
        
        try:
            res = self.model.generate(prompt)
            score_match = re.search(r"Score:\s*([0-9.]+)", res)
            if score_match:
                self.score = float(score_match.group(1))
            reason_match = re.search(r"Reason:\s*(.+)", res, re.DOTALL)
            if reason_match:
                self.reason = reason_match.group(1).strip()
            self.success = self.score >= self.threshold
        except Exception as e:
            self.success = False
            self.reason = f"Error evaluating: {e}"
            self.score = 0
            
        return self.score

    def is_successful(self):
        return self.success

    @property
    def __name__(self):
        return "Identity Boundaries"
