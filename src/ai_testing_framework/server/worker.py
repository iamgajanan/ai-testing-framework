from __future__ import annotations

import argparse
import asyncio
import logging
import os
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load repository .env for local worker execution. Existing process environment
# variables keep precedence, so CI and production injected configuration wins.
load_dotenv(override=False)

from ..cloud.contracts import ExecutionRequest, ExecutionStatus
from ..cloud.runner import ExecutionRunnerError, IsolatedExecutionRunner
from .db import SupabaseDataError, SupabaseServiceClient, SupabaseWorkerClient
from .executions import ExecutionRecord
from .storage import SupabaseStorageClient

logger = logging.getLogger("ai_testing_framework.worker")


class ExecutionWorker:
    def __init__(self, poll_seconds: float = 2.0) -> None:
        self.poll_seconds = max(0.25, poll_seconds)
        self.db = SupabaseWorkerClient()
        self.service = SupabaseServiceClient()
        self.storage = SupabaseStorageClient()
        self.engine = IsolatedExecutionRunner()

    async def run_once(self) -> bool:
        rows = await self.db.claim_next_execution()
        if not rows or not rows[0]:
            return False
        record = ExecutionRecord.from_row(rows[0])
        workspace = Path(tempfile.mkdtemp(prefix=f"ai-test-{record.id}-", dir=os.environ.get("WORKER_TMP_DIR")))
        try:
            suite_path = workspace / Path(record.spec.suite_path).name
            suite_data = await self.storage.download_bytes(record.spec.suite_path, bucket="test-suites")
            suite_path.write_bytes(suite_data)
            output_dir = workspace / "reports"
            request = ExecutionRequest(
                organization_id=str(record.organization_id),
                project_id=str(record.project_id),
                requested_by=str(record.requested_by),
                spec=replace(record.spec, suite_path=str(suite_path), output_dir=str(output_dir)),
                metadata=record.metadata,
            )
            result = await asyncio.to_thread(self.engine.execute, request)
            artifacts = await self._persist_artifacts(record, output_dir)
            result["artifacts"] = artifacts
            terminal = result.get("status", ExecutionStatus.FAILED)
            if isinstance(terminal, ExecutionStatus):
                terminal = terminal.value
            else:
                terminal = str(terminal)
            if terminal not in {ExecutionStatus.PASSED.value, ExecutionStatus.FAILED.value}:
                terminal = ExecutionStatus.FAILED.value
            await self.db.complete_execution(
                str(record.id), terminal, _jsonable(result),
                None if terminal == ExecutionStatus.PASSED.value else "One or more tests failed",
            )
            return True
        except (ExecutionRunnerError, SupabaseDataError, OSError) as exc:
            logger.exception("Execution %s failed", record.id)
            await self.db.complete_execution(str(record.id), ExecutionStatus.FAILED.value, None, str(exc))
            return True
        except Exception as exc:  # noqa: BLE001 - worker must persist execution failures
            logger.exception("Unexpected execution %s failure", record.id)
            await self.db.complete_execution(str(record.id), ExecutionStatus.FAILED.value, None, str(exc))
            return True
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    async def _persist_artifacts(self, record: ExecutionRecord, output_root: Path) -> list[dict[str, Any]]:
        if not output_root.exists() or not output_root.is_dir():
            return []
        artifacts: list[dict[str, Any]] = []
        for path in sorted(output_root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(output_root).as_posix()
            storage_path = f"{record.organization_id}/{record.project_id}/{record.id}/{relative}"
            stored = await self.storage.upload_file(str(path), storage_path)
            rows = await self.service.insert(
                "execution_artifacts",
                {
                    "organization_id": str(record.organization_id),
                    "project_id": str(record.project_id),
                    "execution_id": str(record.id),
                    "name": relative,
                    "storage_path": stored.storage_path,
                    "content_type": stored.content_type,
                    "size_bytes": stored.size_bytes,
                },
            )
            if not rows:
                raise SupabaseDataError(f"Failed to persist artifact metadata for {relative}")
            artifacts.append({
                "id": rows[0]["id"],
                "name": stored.name,
                "storage_path": stored.storage_path,
                "content_type": stored.content_type,
                "size_bytes": stored.size_bytes,
            })
        return artifacts

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
    if isinstance(value, ExecutionStatus):
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
