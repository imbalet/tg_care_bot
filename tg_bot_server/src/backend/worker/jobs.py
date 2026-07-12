import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol


class WorkerJob(Protocol):
    name: str

    async def run_once(self) -> None:
        pass


class WorkerLogger(Protocol):
    def warning(self, event: str, **kwargs: object) -> None:
        pass

    def exception(self, event: str, **kwargs: object) -> None:
        pass


class NoopWorkerJob:
    name = "noop"

    async def run_once(self) -> None:
        return None


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 5.0

    def delay_for_attempt(self, attempt: int) -> float:
        delay = self.base_delay_seconds * (2 ** max(attempt - 1, 0))
        return float(min(delay, self.max_delay_seconds))


async def run_with_retry(
    operation: Callable[[], Awaitable[None]],
    policy: RetryPolicy,
    logger: WorkerLogger,
    operation_name: str,
) -> None:
    for attempt in range(1, policy.max_attempts + 1):
        try:
            await operation()
            return
        except Exception:
            if attempt >= policy.max_attempts:
                logger.exception(
                    "worker_operation_failed",
                    operation_name=operation_name,
                    attempt=attempt,
                    max_attempts=policy.max_attempts,
                )
                raise
            delay = policy.delay_for_attempt(attempt)
            logger.warning(
                "worker_operation_retrying",
                operation_name=operation_name,
                attempt=attempt,
                max_attempts=policy.max_attempts,
                delay_seconds=delay,
            )
            await asyncio.sleep(delay)


__all__ = [
    "NoopWorkerJob",
    "RetryPolicy",
    "WorkerJob",
    "WorkerLogger",
    "run_with_retry",
]
