from typing import Protocol


class WorkerJob(Protocol):
    name: str

    async def run_once(self) -> None:
        pass


class NoopWorkerJob:
    name = "noop"

    async def run_once(self) -> None:
        return None


__all__ = ["NoopWorkerJob", "WorkerJob"]
