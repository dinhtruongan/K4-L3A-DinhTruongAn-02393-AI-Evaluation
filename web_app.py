"""Web Application Server for OrbitTech AI Support & Evaluation Suite.

Serves an interactive web interface for:
1. Live RAG Chat & Trace Inspection (configured LLM / BM25).
2. AI Evaluation Benchmark Dashboard (Visualizes golden dataset & benchmark results).
3. Failure Analysis & Diagnostics.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from domain_assistant import DomainAssistant
from template import RAGASEvaluator

# Load environment configuration
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

CORPUS_DIR = ROOT_DIR / "data" / "technology_store"
GOLDEN_PATH = ROOT_DIR / "golden_dataset.json"
BENCHMARK_PATH = ROOT_DIR / "artifacts" / "benchmark_results.json"
WEB_DIR = ROOT_DIR / "web"

app = FastAPI(title="OrbitTech AI Support & Evaluation Suite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
assistant: DomainAssistant | None = None
evaluator = RAGASEvaluator()
golden_data: dict[str, Any] = {}
golden_pairs_map: dict[str, dict[str, Any]] = {}
benchmark_data: dict[str, Any] = {}


def load_resources() -> None:
    global assistant, golden_data, golden_pairs_map, benchmark_data
    if CORPUS_DIR.exists():
        assistant = DomainAssistant.from_corpus(CORPUS_DIR)
    else:
        raise RuntimeError(f"Corpus directory not found: {CORPUS_DIR}")

    if GOLDEN_PATH.exists():
        golden_data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        for pair in golden_data.get("qa_pairs", []):
            golden_pairs_map[pair["id"]] = pair
            golden_pairs_map[pair["question"].strip().lower()] = pair

    if BENCHMARK_PATH.exists():
        benchmark_data = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))


load_resources()


class ChatRequest(BaseModel):
    question: str
    top_k: int = 5
    expected_answer: str | None = None
    expected_doc: str | None = None


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    return {
        "status": "ready" if assistant else "not_ready",
        "corpus_id": assistant.corpus_id if assistant else "unknown",
        "total_chunks": len(assistant.retriever.chunks) if assistant else 0,
        "model": getattr(assistant.generator, "model", "unknown") if assistant else "unknown",
        "provider": getattr(assistant.generator, "provider", "unknown") if assistant else "unknown",
        "base_url": getattr(assistant.generator, "base_url", None) if assistant else None,
        "has_api_key": bool(getattr(assistant.generator, "client", None)) if assistant else False,
        "benchmark_cases": len(benchmark_data.get("results", [])),
        "golden_cases": len(golden_data.get("qa_pairs", [])),
    }


@app.get("/api/questions")
def get_questions() -> list[dict[str, Any]]:
    return golden_data.get("qa_pairs", [])


@app.get("/api/benchmark")
def get_benchmark() -> dict[str, Any]:
    if not benchmark_data:
        if BENCHMARK_PATH.exists():
            return json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="Benchmark results not found")

    # Enrich benchmark results with golden metadata
    results = []
    for item in benchmark_data.get("results", []):
        enriched = dict(item)
        qid = item.get("id")
        if qid in golden_pairs_map:
            gold = golden_pairs_map[qid]
            enriched["expected_answer"] = gold.get("expected_answer", "")
            enriched["contexts"] = gold.get("contexts", [])
            enriched["attack_type"] = gold.get("attack_type")
        results.append(enriched)

    return {
        "summary": benchmark_data.get("summary", {}),
        "results": results,
    }


@app.post("/api/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    if not assistant:
        raise HTTPException(status_code=500, detail="Domain Assistant not initialized")

    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    top_k = max(1, min(10, request.top_k))

    start_time = time.perf_counter()
    request_assistant = DomainAssistant(
        assistant.corpus_id, assistant.retriever, assistant.generator, top_k=top_k
    )
    response = request_assistant.answer_with_trace(question)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 1)

    # Check if there is an expected answer for evaluation
    expected_answer = request.expected_answer
    matched_id = None
    if not expected_answer:
        matched = golden_pairs_map.get(question.lower())
        if matched:
            expected_answer = matched.get("expected_answer")
            matched_id = matched.get("id")

    eval_info = None
    if expected_answer:
        context_str = "\n\n".join(c.text for c in response.retrieved_chunks)
        contexts_list = [c.text for c in response.retrieved_chunks]
        eval_res = evaluator.run_full_eval(
            answer=response.actual_answer,
            question=question,
            context=context_str,
            expected=expected_answer,
            contexts=contexts_list,
        )
        overall_score = eval_res.overall_score()
        eval_info = {
            "matched_id": matched_id,
            "expected_answer": expected_answer,
            "faithfulness": round(eval_res.faithfulness, 4),
            "relevance": round(eval_res.relevance, 4),
            "completeness": round(eval_res.completeness, 4),
            "context_recall": round(eval_res.context_recall or 0.0, 4),
            "context_precision": round(eval_res.context_precision or 0.0, 4),
            "overall_score": round(overall_score, 4),
            "passed": eval_res.passed,
            "failure_type": eval_res.failure_type,
        }

    return {
        "question": question,
        "actual_answer": response.actual_answer,
        "latency_ms": latency_ms,
        "model": getattr(assistant.generator, "model", "unknown"),
        "retrieved_chunks": [
            {
                "chunk_id": c.chunk_id,
                "source_doc": c.source_doc,
                "title": c.title,
                "score": round(c.score, 4),
                "text": c.text,
            }
            for c in response.retrieved_chunks
        ],
        "eval": eval_info,
    }


# Mount static directory for frontend assets
if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


@app.get("/")
def serve_index() -> HTMLResponse:
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Web UI is loading...</h1>", status_code=200)
    return HTMLResponse(index_file.read_text(encoding="utf-8"), media_type="text/html")


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting OrbitTech AI Web UI at http://127.0.0.1:{port}")
    uvicorn.run("web_app:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
