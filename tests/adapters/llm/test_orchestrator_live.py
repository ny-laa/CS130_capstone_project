# LIVE TEST - hits the real claude api
# only runs if ANTHROPIC_API_KEY is set in your environment or backend/.env
# run with: ANTHROPIC_API_KEY=your-key pytest tests/adapters/llm/test_orchestrator_live.py -v

import os
import json
import pytest
from dotenv import load_dotenv

# try to load from backend/.env if it exists
load_dotenv("backend/.env")

from backend.orchestrator.orchestrator import GOrchestrator


def test_live_simple_reminder():
    # make sure the key is there before we even try
    assert os.getenv("ANTHROPIC_API_KEY"), "no ANTHROPIC_API_KEY found in env — set it in backend/.env to run live tests"

    orc = GOrchestrator()
    result = orc.handle("Remind me to pick up Jake from school at 3pm")

    print("\n--- claude response ---")
    print(json.dumps(result, indent=2))

    assert isinstance(result, dict)
    assert "task_type" in result
    assert "plan_steps" in result
    assert "response_message" in result
