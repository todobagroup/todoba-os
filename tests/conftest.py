"""
TODOBA Test Configuration

Provides non-production environment values required
before application modules are imported during tests.
"""

import os


os.environ.setdefault(
    "TODOBA_TRUSTED_AGENT_ID",
    "trusted-agent-001",
)

os.environ.setdefault(
    "TODOBA_TRUSTED_AGENT_SECRET",
    "test-trusted-agent-secret",
)

os.environ.setdefault(
    "TODOBA_EXECUTION_MISSION_SIGNING_SECRET",
    "test-execution-mission-signing-secret",
)