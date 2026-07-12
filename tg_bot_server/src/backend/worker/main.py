import asyncio
import signal

import structlog

from backend.bootstrap.container import create_container
from backend.bootstrap.settings import get_settings
from backend.common.infrastructure.logging import configure_logging
from backend.worker.jobs import NoopWorkerJob, WorkerJob

logger = structlog.get_logger(__name__)


class Worker:
    def __init__(
        self,
        poll_interval_seconds: float,
        jobs: list[WorkerJob] | None = None,
    ) -> None:
        self._poll_interval_seconds = poll_interval_seconds
        self._jobs = jobs or [NoopWorkerJob()]
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info("worker_started")
        while not self._stop_event.is_set():
            await self.run_once()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval_seconds,
                )
            except TimeoutError:
                continue
        logger.info("worker_stopped")

    async def run_once(self) -> None:
        for job in self._jobs:
            await job.run_once()
            logger.info("worker_job_completed", job_name=job.name)
        logger.info("worker_iteration_completed")


async def amain() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = create_container(settings)
    worker = Worker(settings.worker_poll_interval_seconds)
    loop = asyncio.get_running_loop()
    for signal_number in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_number, worker.stop)
    try:
        await worker.run()
    finally:
        await container.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()


__all__ = ["Worker", "amain", "main"]
