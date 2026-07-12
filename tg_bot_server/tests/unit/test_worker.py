import asyncio

from backend.worker import Worker


class RecordingJob:
    name = "recording"

    def __init__(self) -> None:
        self.calls = 0

    async def run_once(self) -> None:
        self.calls += 1


def test_worker_runs_registered_jobs() -> None:
    async def run_worker_once() -> None:
        job = RecordingJob()
        worker = Worker(poll_interval_seconds=0.01, jobs=[job])
        await worker.run_once()
        assert job.calls == 1

    asyncio.run(run_worker_once())


def test_worker_can_stop() -> None:
    async def run_worker() -> None:
        worker = Worker(poll_interval_seconds=0.01)
        task = asyncio.create_task(worker.run())
        worker.stop()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(run_worker())
