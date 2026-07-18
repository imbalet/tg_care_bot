import asyncio
import logging
import signal

from backend.bootstrap.container import create_container
from backend.bootstrap.settings import get_settings
from backend.common.infrastructure.logging import configure_logging
from backend.worker.jobs import (
    DeadlinesWorkerJob,
    NoopWorkerJob,
    NotificationWorkerJob,
    RetryPolicy,
    WorkerJob,
    WorkerRunner,
    run_with_retry,
)

logger = logging.getLogger(__name__)


class Worker(WorkerRunner):
    def __init__(
        self,
        poll_interval_seconds: float,
        jobs: list[WorkerJob] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._poll_interval_seconds = poll_interval_seconds
        self._jobs = jobs or [NoopWorkerJob()]
        self._retry_policy = retry_policy or RetryPolicy()
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
            await run_with_retry(
                job.run_once,
                self._retry_policy,
                logger,
                job.name,
            )
            logger.info("worker_job_completed", extra={"job_name": job.name})
        logger.info("worker_iteration_completed")


async def amain() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = create_container(settings)
    worker = Worker(
        settings.worker_poll_interval_seconds,
        jobs=[
            DeadlinesWorkerJob(
                container.session_factory,
                settings.worker_batch_limit,
            ),
            NotificationWorkerJob(
                container.session_factory,
                settings.worker_batch_limit,
                customer_bot_token=settings.customer_bot_token,
                executor_bot_token=settings.executor_bot_token,
                telegram_api_base_url=settings.telegram_api_base_url,
                telegram_timeout_seconds=settings.telegram_timeout_seconds,
            ),
        ],
    )
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
