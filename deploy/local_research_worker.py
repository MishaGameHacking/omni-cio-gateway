"""Isolated local public-document selector. Never imports the owner application."""
from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import signal
import socketserver
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import local_research as contract

MODEL_FILE = Path("/opt/analyst-local-ai/model.litertlm")
MAX_CONTEXT_TOKENS = 2048
MAX_OUTPUT_TOKENS = 64


def verify_model(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != contract.MODEL_SHA256:
        raise ValueError("local_model_checksum_mismatch")


def model_select(engine, runtime, context):
    # Validate all incoming keys and bounds. No path/URL/credential/tools can be
    # supplied through this private socket, even by a compromised caller.
    if not isinstance(context, dict) or set(context) != {
            "title", "fragments", "source_sha256", "coverage", "whole_document_reviewed"}:
        raise ValueError("invalid_context")
    rows = context["fragments"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= contract.MAX_PARAGRAPHS:
        raise ValueError("invalid_fragments")
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {"id", "text"} or type(row["id"]) is not int or row["id"] != index:
            raise ValueError("invalid_fragment")
        if not isinstance(row["text"], str) or not row["text"].strip() or len(row["text"].encode()) > 1200:
            raise ValueError("invalid_fragment")
    if not isinstance(context["title"], str) or len(context["title"]) > 400:
        raise ValueError("invalid_title")
    prompt = json.dumps({"title": context["title"], "fragments": rows}, ensure_ascii=False)
    # Count actual model tokens and reserve room for chat template and output.
    if len(engine.tokenize(contract.SYSTEM_PROMPT + prompt)) + 256 > MAX_CONTEXT_TOKENS:
        raise ValueError("local_context_full")
    with engine.create_conversation(
            messages=[runtime.Message.system(contract.SYSTEM_PROMPT)], tools=[],
            automatic_tool_calling=False, max_output_tokens=MAX_OUTPUT_TOKENS,
            thinking_config=runtime.ThinkingConfig(enable_thinking=False, thinking_token_budget=0),
            sampler_config=runtime.SamplerConfig(top_k=1, temperature=0.0, seed=7),
            extra_context={"enable_thinking": False}) as conversation:
        response = conversation.send_message(prompt)
    content = response.get("content") if isinstance(response, dict) else None
    if not isinstance(content, list) or len(content) != 1 or content[0].get("type") != "text":
        raise ValueError("local_response_invalid")
    raw = content[0].get("text")
    contract.decode_selection(raw, context)
    return raw


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No public source text, prompts or model prose in service logs.

    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def do_POST(self):
        if self.path != "/select" or self.headers.get("Transfer-Encoding"):
            self.send_error(400)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= contract.MAX_INPUT_BYTES:
                raise ValueError("input_bound")
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError("incomplete_input")
            context = json.loads(raw)
            # SIGALRM default terminates stuck native inference. systemd restarts
            # only this isolated worker; the owner API and DB remain separate.
            signal.alarm(15)
            output = model_select(self.server.engine, self.server.runtime, context).encode()
            signal.alarm(0)
        except (ValueError, TypeError, RuntimeError, OSError, RecursionError):
            signal.alarm(0)
            self.send_error(503)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(output)))
        self.send_header("X-Model-SHA256", contract.MODEL_SHA256)
        self.end_headers()
        self.wfile.write(output)


def main():
    verify_model(MODEL_FILE)
    import litert_lm
    litert_lm.set_min_log_severity(litert_lm.LogSeverity.ERROR)
    with litert_lm.Engine(str(MODEL_FILE), backend=litert_lm.Backend.CPU(thread_count=1),
                          max_num_tokens=MAX_CONTEXT_TOKENS,
                          cache_dir="/var/cache/analyst-local-ai") as engine:
        path = Path(contract.SOCKET)
        # systemd RuntimeDirectory owns and recreates this private directory.
        if path.exists():
            path.unlink()
        with socketserver.UnixStreamServer(str(path), Handler) as server:
            os.chmod(path, 0o660)
            server.engine, server.runtime = engine, litert_lm
            server.serve_forever()


if __name__ == "__main__":
    main()
