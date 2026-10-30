"""Private-worker contract tests, with no weights, network or model invocation."""
import importlib.util
from pathlib import Path
import sys
from unittest import mock

import pytest

from backend import local_research


@pytest.fixture
def worker():
    path = Path(__file__).resolve().parents[2] / "deploy/local_research_worker.py"
    spec = importlib.util.spec_from_file_location("research_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "path", sys.path.copy()):
        spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("change", [
    {"extra": "untrusted"}, {"source_sha256": []}, {"source_sha256": "x" * 64},
    {"whole_document_reviewed": True}, {"whole_document_reviewed": 0},
    {"coverage": "entire_document"}, {"title": None}, {"title": "a" * 401},
    {"fragments": []}, {"fragments": [{"id": True, "text": "wrong id"}]},
    {"fragments": [{"id": 0, "text": "a" * 1201}]},
    {"fragments": [{"id": 0, "text": "text", "url": "untrusted"}]},
])
def test_invalid_private_request_never_reaches_engine(worker, change):
    context = {**local_research.packet("Report", "Revenue was 100 RUB."), **change}
    engine = mock.Mock()
    runtime = mock.Mock()
    with pytest.raises(ValueError):
        worker.model_select(engine, runtime, context)
    engine.tokenize.assert_not_called()
    engine.create_conversation.assert_not_called()


def test_real_token_limit_checked_before_inference(worker):
    context = local_research.packet("Report", "Revenue was 100 RUB.")
    engine = mock.Mock()
    runtime = mock.Mock()
    engine.tokenize.return_value = [1] * 1900
    with pytest.raises(ValueError, match="local_context_full"):
        worker.model_select(engine, runtime, context)
    engine.create_conversation.assert_not_called()


@pytest.mark.parametrize("content", [["wrong"], [], [{"type": "tool_call"}], [{"type": "text", "text": '{"selected":[999]}'}]])
def test_invalid_provider_output_rejected(worker, content):
    context = local_research.packet("Report", "Revenue was 100 RUB.")
    engine = mock.Mock()
    runtime = mock.Mock()
    engine.tokenize.return_value = [1]
    conversation = mock.MagicMock()
    engine.create_conversation.return_value = conversation
    conversation.__enter__.return_value.send_message.return_value = {"content": content}
    with pytest.raises(ValueError):
        worker.model_select(engine, runtime, context)
    assert engine.create_conversation.call_args.kwargs["tools"] == []
    assert engine.create_conversation.call_args.kwargs["automatic_tool_calling"] is False
