import os
from collections.abc import Iterator
from urllib.parse import quote
from uuid import uuid4

import psycopg
import pytest

from app.agent.checkpoint import postgres_workflow_service
from app.agent.models import ApprovalResume
from app.agent.steps import InMemoryAgentStepSink
from tests.test_agent_workflow import ScriptedActions, request

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_P7_INTEGRATION") != "1",
        reason="set RUN_P7_INTEGRATION=1 to test LangGraph restart recovery against PostgreSQL",
    ),
]


@pytest.fixture
def checkpoint_dsn() -> Iterator[str]:
    host = os.getenv("PLATFORM_DB_HOST", "localhost")
    port = int(os.getenv("PLATFORM_DB_PORT", "5432"))
    database = os.getenv("PLATFORM_DB_NAME", "copilot_platform")
    username = os.getenv("PLATFORM_DB_USER", "copilot")
    password = os.getenv("PLATFORM_DB_PASSWORD", "change-me-platform")
    parameters = {
        "host": host,
        "port": port,
        "dbname": database,
        "user": username,
        "password": password,
    }
    with psycopg.connect(**parameters, autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS p7_test CASCADE")
        connection.execute("CREATE SCHEMA p7_test")
    encoded_user = quote(username, safe="")
    encoded_password = quote(password, safe="")
    dsn = (
        f"postgresql://{encoded_user}:{encoded_password}@{host}:{port}/{database}"
        "?options=-csearch_path%3Dp7_test"
    )
    yield dsn
    with psycopg.connect(**parameters, autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS p7_test CASCADE")


def test_postgres_checkpoint_resumes_after_connection_and_service_restart(
    checkpoint_dsn: str,
) -> None:
    actions = ScriptedActions(risk="approval")
    sink = InMemoryAgentStepSink()
    run = request()

    with postgres_workflow_service(
        dsn=checkpoint_dsn,
        actions=actions,
        step_sink=sink,
        setup=True,
    ) as workflow:
        waiting = workflow.start(run)
        assert waiting.status == "WAITING_APPROVAL"

    with postgres_workflow_service(
        dsn=checkpoint_dsn,
        actions=actions,
        step_sink=sink,
    ) as restarted_workflow:
        recovered = restarted_workflow.inspect(run.run_id)
        completed = restarted_workflow.resume(
            run_id=run.run_id,
            tenant_id=run.tenant_id,
            resume=ApprovalResume(
                approval_id=str(uuid4()),
                decision="approved",
                decided_by=str(uuid4()),
            ),
        )

    assert recovered.status == "WAITING_APPROVAL"
    assert completed.status == "COMPLETED"
    assert actions.executions == 1
