from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any

from ..cloud.contracts import ExecutionRequest, ExecutionSpec, ExecutionStatus
from ..cloud.engine import LocalEngineAdapter
from .db import SupabaseDataError, SupabaseWorkerClient
from .executions import ExecutionRecord

logger = logging.getLogger("ai_testing_framework.worker")


class ExecutionWorker:
    def __init__(self, poll_seconds: float = 2.0) -> None:
        self.poll_seconds = max(0.25, poll_seconds)
        self.db = SupabaseWorkerClient()
        self.engine = LocalEngineAdapter()

    async def run_once(self) -> bool:
        rows = await self.db.claim_next_execution()
        if not rows or not rows[0]:
            return False
        record = ExecutionRecord.from_row(rows[0])
        request = ExecutionRequest(
            organization_id=str(record.organization_id),
            project_id=str(record.project_id),
            requested_by=str(record.requested_by),
            spec=record.spec,
            metadata=record.metadata,
        )
        try:
            result = await asyncio.to_thread(self.engine.execute, request)
            terminal = str(result.get("status", ExecutionStatus.FAILED))
            if terminal not in {ExecutionStatus.PASSED, ExecutionStatus.FAILED}:
                terminal = ExecutionStatus.FAILED
            await self.db.complete_execution(str(record.id), terminal, _jsonable(result), None if terminal == ExecutionStatus.PASSED else "One or more tests failed")
            return True
        except Exception as exc:  # noqa: BLE001 - worker must persist execution failures
            logger.exception("Execution %s failed", record.id)
            await self.db.complete_execution(str(record.id), ExecutionStatus.FAILED, None, str(exc))
            return True

    async def run_forever(self) -> None:
        logger.info("Execution worker started; polling every %.2fs", self.poll_seconds)
        while True:
            try:
                claimed = await self.run_once()
            except SupabaseDataError:
                logger.exception("Queue database operation failed")
                claimed = False
            if not claimed:
                await asyncio.sleep(self.poll_seconds)


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (ExecutionStatus,)):
        return value.value
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI Testing Framework execution worker")
    parser.add_argument("--poll-seconds", type=float, default=float(os.environ.get("WORKER_POLL_SECONDS", "2")))
    parser.add_argument("--once", action="store_true", help="Process at most one queued execution and exit")
    args = parser.parse_args()
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    worker = ExecutionWorker(args.poll_seconds)
    if args.once:
        asyncio.run(worker.run_once())
    else:
        asyncio.run(worker.run_forever())
