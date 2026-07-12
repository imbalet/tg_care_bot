import asyncio
from typing import Any

from backend.worker import Worker
from backend.worker.jobs import RetryPolicy, run_with_retry


class RecordingJob:
    name = "recording"

    def __init__(self) -> None:
        self.calls = 0

    async def run_once(self) -> None:
        self.calls += 1


class FlakyJob:
    name = "flaky"

    def __init__(self) -> None:
        self.calls = 0

    async def run_once(self) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")


class RecordingLogger:
    def __init__(self) -> None:
        self.warnings: list[dict[str, Any]] = []
        self.exceptions: list[dict[str, Any]] = []

    def warning(self, event: str, **kwargs: object) -> None:
        self.warnings.append({"event": event, **kwargs})

    def exception(self, event: str, **kwargs: object) -> None:
        self.exceptions.append({"event": event, **kwargs})


def test_worker_runs_registered_jobs() -> None:
    async def run_worker_once() -> None:
        job = RecordingJob()
        worker = Worker(poll_interval_seconds=0.01, jobs=[job])
        await worker.run_once()
        assert job.calls == 1

    asyncio.run(run_worker_once())


def test_worker_retries_transient_job_failure() -> None:
    async def run_worker_once() -> None:
        job = FlakyJob()
        worker = Worker(
            poll_interval_seconds=0.01,
            jobs=[job],
            retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0),
        )
        await worker.run_once()
        assert job.calls == 2

    asyncio.run(run_worker_once())


def test_run_with_retry_logs_and_raises_after_limit() -> None:
    async def run_operation() -> None:
        async def failing_operation() -> None:
            raise RuntimeError("permanent failure")

        logger = RecordingLogger()
        policy = RetryPolicy(max_attempts=2, base_delay_seconds=0)

        try:
            await run_with_retry(failing_operation, policy, logger, "failing")
        except RuntimeError:
            pass
        else:
            raise AssertionError("run_with_retry did not raise")

        assert logger.warnings[0]["event"] == "worker_operation_retrying"
        assert logger.exceptions[0]["event"] == "worker_operation_failed"

    asyncio.run(run_operation())


def test_worker_can_stop() -> None:
    async def run_worker() -> None:
        worker = Worker(poll_interval_seconds=0.01)
        task = asyncio.create_task(worker.run())
        worker.stop()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(run_worker())
