import streamlit as st
import requests
import json
import time
import pandas as pd
import asyncio
import os
from mcp import ClientSession
from mcp.client.sse import sse_client

async def run_mcp_eval(tool_name: str, args: dict):
    # Connect directly to the internal docker-compose service
    url = os.getenv("DEEPEVAL_MCP_URL", "http://deepeval-mcp:8083/sse")
    # Spoof the Host header to bypass FastMCP's strict Host validation
    headers = {"Host": "127.0.0.1:8000"}
    async with sse_client(url, headers=headers) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=args)
            return result.content[0].text

API_URL = os.getenv("API_URL", "http://app:8000")

st.set_page_config(page_title="Underwriting Agent", layout="wide")

st.title("🛡️ P&C Underwriting Agent")

tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "📊 Evals", "🔍 Observability", "🚀 DeepMCP Evals"])

# State variables
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "latest_agent_steps" not in st.session_state:
    st.session_state.latest_agent_steps = []
if "latest_telemetry" not in st.session_state:
    st.session_state.latest_telemetry = None

with tab1:
    st.header("Ask the Underwriting Agent")
    
    # Display chat history
    messages_container = st.container(height=600)
    with messages_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(
                    f'<div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">'
                    f'<div style="background-color: #dcf8c6; padding: 10px 15px; border-radius: 15px; color: black; max-width: 70%;">'
                    f'{msg["content"]}</div></div>',
                    unsafe_allow_html=True
                )
            else:
                with st.chat_message(msg["role"]):
                    if "telemetry" in msg and msg["telemetry"]:
                        safety = msg["telemetry"].get("safety_eval", {})
                        if safety.get("status") == "PASSED":
                            st.caption(f"✅ Safety Eval: PASSED")
                        elif safety.get("status") == "FAILED":
                            st.error(f"❌ Safety Eval: FAILED - {safety.get('reason')}")
                            
                    st.markdown(msg["content"])
                    if "citations" in msg and msg["citations"]:
                        with st.expander("Sources"):
                            for c in msg["citations"]:
                                st.markdown(f"- **{c['source_document']}** ({c['section_or_page']})")
                    if "agent_steps" in msg and msg["agent_steps"]:
                        with st.expander("Agent Reasoning & Steps"):
                            for step in msg["agent_steps"]:
                                st.markdown(f"**Node: {step['node']}**")
                                # Show some key state changes
                                st_update = step.get('state_update', {})
                                if 'intent' in st_update and st_update['intent']:
                                    st.caption(f"Intent: {st_update['intent']} | LOB: {st_update.get('lob_filter', '')} | State: {st_update.get('state_filter', '')}")
                                if 'is_sufficient' in st_update:
                                    st.caption(f"Quality Grader Sufficient: {st_update['is_sufficient']}")
                                if 'search_query' in st_update and st_update['search_query']:
                                    st.caption(f"Search Query: {st_update['search_query']}")
                    if "eval_results" in msg and msg["eval_results"]:
                        st.markdown("**Evaluation Results**")
                        st.dataframe(pd.DataFrame(msg["eval_results"]), use_container_width=True)
                            
    query = st.chat_input("Enter your underwriting question...")
    
    if query:
        # Append user query
        st.session_state.chat_history.append({"role": "user", "content": query})
        with messages_container:
            st.markdown(
                f'<div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">'
                f'<div style="background-color: #dcf8c6; padding: 10px 15px; border-radius: 15px; color: black; max-width: 70%;">'
                f'{query}</div></div>',
                unsafe_allow_html=True
            )
                
            with st.chat_message("assistant"):
                with st.spinner("Analyzing..."):
                    try:
                        resp = requests.post(f"{API_URL}/chat", json={"query": query})
                        if resp.status_code == 200:
                            data = resp.json()
                            answer = data.get("answer", "No answer provided.")
                            citations = data.get("citations", [])
                            agent_steps = data.get("agent_steps", [])
                            telemetry = data.get("evaluation_telemetry", {})
                            
                            safety = telemetry.get("safety_eval", {})
                            if safety.get("status") == "PASSED":
                                st.caption(f"✅ Safety Eval: PASSED")
                            elif safety.get("status") == "FAILED":
                                st.error(f"❌ Safety Eval: FAILED - {safety.get('reason')}")
                                
                            st.markdown(answer)
                            
                            if citations:
                                with st.expander("Sources"):
                                    for c in citations:
                                        st.markdown(f"- **{c['source_document']}** ({c['section_or_page']})")
                                        
                            if agent_steps:
                                with st.expander("Agent Reasoning & Steps"):
                                    for step in agent_steps:
                                        st.markdown(f"**Node: {step['node']}**")
                                        st_update = step.get('state_update', {})
                                        if 'intent' in st_update and st_update['intent']:
                                            st.caption(f"Intent: {st_update['intent']} | LOB: {st_update.get('lob_filter', '')} | State: {st_update.get('state_filter', '')}")
                                        if 'is_sufficient' in st_update:
                                            st.caption(f"Quality Grader Sufficient: {st_update['is_sufficient']}")
                                        if 'search_query' in st_update and st_update['search_query']:
                                            st.caption(f"Search Query: {st_update['search_query']}")
                            
                            # Save to state
                            st.session_state.latest_agent_steps = agent_steps
                            st.session_state.latest_telemetry = telemetry
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": answer,
                                "citations": citations,
                                "agent_steps": agent_steps,
                                "telemetry": telemetry,
                                "query": query,
                                "retrieved_contexts": data.get("retrieved_contexts", [])
                            })
                        else:
                            st.error(f"Error: {resp.text}")
                    except Exception as e:
                        st.error(f"Connection error: {e}")

    # Display evaluation button for the last assistant message
    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "assistant":
        last_msg = st.session_state.chat_history[-1]
        if "eval_results" not in last_msg:
            if st.button("Run Selected Evaluations"):
                if "selected_metrics" in st.session_state and st.session_state.selected_metrics:
                    with st.spinner("Running DeepEval..."):
                        try:
                            eval_req = {
                                "query": last_msg.get("query", ""),
                                "actual_output": last_msg["content"],
                                "retrieval_context": last_msg.get("retrieved_contexts", []),
                                "requested_metrics": st.session_state.selected_metrics,
                                "agent_steps": last_msg.get("agent_steps", [])
                            }
                            eval_resp = requests.post(f"{API_URL}/evaluate", json=eval_req)
                            if eval_resp.status_code == 200:
                                results = eval_resp.json().get("results", {})
                                df_data = []
                                for m_name, m_res in results.items():
                                    df_data.append({
                                        "Metric": m_name,
                                        "Score (0-3)": m_res.get("score"),
                                        "Passed": m_res.get("passed"),
                                        "Reason": m_res.get("reason")
                                    })
                                st.session_state.chat_history[-1]["eval_results"] = df_data
                                st.rerun()
                            else:
                                st.error(f"Evaluation Error: {eval_resp.text}")
                        except Exception as e:
                            st.error(f"Connection error: {e}")
                else:
                    st.warning("Please select at least one evaluation metric from the sidebar.")

with tab2:
    st.header("DeepEval Agent Evaluation")
    st.markdown("Run a live evaluation on a QA pair.")
    
    eval_q = st.text_input("Question to evaluate")
    eval_a = st.text_area("Generated Answer")
    eval_c = st.text_area("Retrieved Contexts (one per line)")
    eval_eo = st.text_area("Expected Answer (Ground Truth)")
    
    if st.button("Run Evaluation"):
        if eval_q and eval_a and eval_c:
            contexts = [c.strip() for c in eval_c.split("\n") if c.strip()]
            with st.spinner("Running DeepEval (Gemini 3.1 Pro)..."):
                try:
                    resp = requests.post(f"{API_URL}/evaluate", json={
                        "query": eval_q,
                        "actual_output": eval_a,
                        "retrieval_context": contexts,
                        "expected_output": eval_eo if eval_eo.strip() else None,
                        "requested_metrics": ["Answer Relevancy", "Contextual Precision", "Contextual Recall"],
                        "agent_steps": []
                    })
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("results", {})
                        
                        if results:
                            cols = st.columns(len(results))
                            for idx, (m_name, m_res) in enumerate(results.items()):
                                cols[idx].metric(m_name, f"{m_res.get('score', 0):.2f}")
                            
                            st.subheader("Reasoning")
                            st.json({m: r.get("reason") for m, r in results.items()})
                        else:
                            st.info("No metrics returned.")
                    else:
                        st.error(f"Error: {resp.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")
        else:
            st.warning("Please fill out all fields.")

with tab3:
    st.header("Observability & Tracing")
    st.markdown("Detailed view of the graph execution from the latest chat interaction.")
    
    if st.session_state.latest_telemetry:
        st.subheader("Performance Metrics")
        telemetry = st.session_state.latest_telemetry
        obs = telemetry.get("observability", {})
        
        col1, col2 = st.columns(2)
        col1.metric("Total Steps Executed", obs.get("total_steps_executed", 0))
        
        with col2:
            st.markdown("**Node Latencies (ms)**")
            st.json(obs.get("node_latencies_ms", {}))
        st.divider()
        
    if st.session_state.latest_agent_steps:
        st.subheader("Execution Trace")
        for i, step in enumerate(st.session_state.latest_agent_steps):
            node = step["node"]
            state = step["state_update"]
            
            with st.container():
                st.markdown(f"### Step {i+1}: `{node}`")
                st.json(state)
                st.divider()
    else:
        st.info("No trace data available. Ask a question in the Chat tab first.")

    st.divider()
    st.subheader("OpenTelemetry Traces")
    st.markdown("Distributed traces generated by `openinference-instrumentation-langchain` and `FastAPIInstrumentor`.")
    try:
        if os.path.exists("traces.jsonl"):
            with open("traces.jsonl", "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            if lines:
                import collections
                traces = collections.defaultdict(list)
                for line in lines:
                    try:
                        span_data = json.loads(line)
                        trace_id = span_data.get('context', {}).get('trace_id', 'unknown')
                        traces[trace_id].append(span_data)
                    except json.JSONDecodeError:
                        pass
                
                trace_ids = list(traces.keys())[-10:]
                st.write(f"Showing last {len(trace_ids)} Traces.")
                
                for trace_id in reversed(trace_ids):
                    spans = traces[trace_id]
                    span_dict = {s.get('context', {}).get('span_id'): s for s in spans}
                    children = collections.defaultdict(list)
                    roots = []
                    
                    for s in spans:
                        parent_id = s.get('parent_id')
                        if parent_id and parent_id in span_dict:
                            children[parent_id].append(s)
                        else:
                            roots.append(s)
                            
                    with st.expander(f"Trace: {trace_id} ({len(spans)} spans)"):
                        def render_span(span, level=0):
                            span_name = span.get('name', 'Unknown Span')
                            indent = "&nbsp;" * (level * 8)
                            st.markdown(f"{indent} ↳ **{span_name}**")
                            for child in children.get(span.get('context', {}).get('span_id'), []):
                                render_span(child, level + 1)
                                
                        for root in roots:
                            render_span(root)
                            
                        st.markdown("---")
                        st.markdown("**Raw Spans Data:**")
                        st.json(spans, expanded=False)
            else:
                st.info("No OTEL traces found in file yet.")
        else:
            st.info("`traces.jsonl` not found. Traces will appear here once generated.")
    except Exception as e:
        st.error(f"Error reading OTEL traces: {e}")

with tab4:
    st.header("🚀 DeepMCP: Containerized Evaluations")
    st.markdown("Run DeepEval metrics directly via the standalone MCP Docker container. This bypasses the FastAPI backend and uses standard input/output streams.")
    
    mcp_q = st.text_input("Question to evaluate", key="mcp_q")
    mcp_a = st.text_area("Generated Answer", key="mcp_a")
    mcp_c = st.text_area("Retrieved Contexts (one per line)", key="mcp_c")
    mcp_eo = st.text_area("Expected Answer (Ground Truth)", key="mcp_eo")
    
    if st.button("Run DeepMCP Evaluation"):
        if mcp_q and mcp_a and mcp_c:
            mcp_contexts = [c.strip() for c in mcp_c.split("\n") if c.strip()]
            
            def render_metric_result(title, raw_result):
                try:
                    res = json.loads(raw_result)
                    st.subheader(title)
                    cols = st.columns(2)
                    cols[0].metric("Score", f"{res.get('score', 0):.2f}")
                    if res.get('is_successful'):
                        cols[1].success("PASSED")
                    else:
                        cols[1].error("FAILED")
                    st.info(res.get('reason', ''))
                    st.divider()
                except Exception:
                    st.write(f"**{title}:**")
                    st.text(raw_result)

            with st.spinner("Connecting to Docker MCP Server..."):
                try:
                    f_args = {"input_text": mcp_q, "actual_output": mcp_a, "retrieval_context": mcp_contexts}
                    f_res = asyncio.run(run_mcp_eval("evaluate_faithfulness", f_args))
                    render_metric_result("Faithfulness", f_res)
                    
                    ar_args = {"input_text": mcp_q, "actual_output": mcp_a}
                    ar_res = asyncio.run(run_mcp_eval("evaluate_answer_relevancy", ar_args))
                    render_metric_result("Answer Relevancy", ar_res)

                    if mcp_eo:
                        cp_args = {"input_text": mcp_q, "actual_output": mcp_a, "expected_output": mcp_eo, "retrieval_context": mcp_contexts}
                        cp_res = asyncio.run(run_mcp_eval("evaluate_contextual_precision", cp_args))
                        render_metric_result("Contextual Precision", cp_res)
                    
                    st.success("DeepMCP Evaluation Complete!")
                except Exception as e:
                    st.error(f"MCP Error: {e}")
        else:
            st.warning("Please fill out Question, Answer, and Context fields.")

# Health Check Sidebar
st.sidebar.title("Evaluation Settings")
st.session_state.selected_metrics = st.sidebar.multiselect(
    "Evaluation Metrics (DeepEval: Scale 0-3)",
    ['Answer Relevancy', 'Faithfulness','Bias', 'Toxicity', 'Tool Chaining Reliability', 'Identity Boundaries'],
    default=['Answer Relevancy', 'Faithfulness','Tool Chaining Reliability', 'Identity Boundaries']
)
st.sidebar.divider()

st.sidebar.title("System Health")
if st.sidebar.button("Check Connectivity"):
    with st.spinner("Pinging services..."):
        try:
            resp = requests.get(f"{API_URL}/health")
            if resp.status_code == 200:
                health = resp.json()
                st.sidebar.success("FastAPI: UP")
                st.sidebar.success(f"Qdrant: {health['qdrant'].upper()}")
                st.sidebar.success(f"Ollama: {health['ollama'].upper()}")
            else:
                st.sidebar.error("FastAPI Error")
        except Exception as e:
            st.sidebar.error("FastAPI Down")
