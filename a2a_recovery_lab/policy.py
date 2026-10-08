"""Explicit, bounded recovery decisions; independent of HTTP and agent wire state."""

import time
from dataclasses import dataclass


class TransportFailure(RuntimeError):
    """An exchange failed; submission acceptance may be unknown."""


class AmbiguousSubmission(RuntimeError):
    pass


class LocalCancellation(RuntimeError):
    pass


class BudgetExhausted(RuntimeError):
    def __init__(self, operation, attempts, reason):
        super().__init__(f"{operation} stopped after {attempts} attempts: {reason}")
        self.operation, self.attempts, self.reason = operation, attempts, reason


@dataclass(frozen=True)
class RecoveryPolicy:
    max_attempts: int = 12
    deadline_seconds: float = 2.0
    retry_delay_seconds: float = 0.01
    peer_deduplication_assumed: bool = False
    unsafe_retry: bool = False

    def __post_init__(self):
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 100:
            raise ValueError("Attempt bound must be in [1,100]")
        if not 0 < self.deadline_seconds <= 4 or not 0 <= self.retry_delay_seconds <= 0.2:
            raise ValueError("Recovery deadline/delay outside the local bounds")

    def run(self, operation, call, *, ready=lambda _: True, canceled=lambda: False,
            clock=time.monotonic, sleep=time.sleep, observe=lambda *_, **__: None):
        deadline = clock() + self.deadline_seconds
        attempts = 0
        if self.unsafe_retry and operation == "submission":
            observe("unsafe_retry_enabled", deduplication_assumed=self.peer_deduplication_assumed)
        for attempt in range(1, self.max_attempts + 1):
            if canceled():
                raise LocalCancellation("Local task canceled before exchange")
            remaining = deadline - clock()
            if remaining <= 0:
                raise BudgetExhausted(operation, attempts, "deadline")
            attempts = attempt
            observe("recovery_attempt", operation=operation, attempt=attempt,
                    remaining_seconds=round(remaining, 6))
            try:
                value = call(attempt, remaining)
                if canceled():
                    observe("late_response_discarded", operation=operation, attempt=attempt)
                    raise LocalCancellation("Response arrived after local cancellation")
                if clock() > deadline:
                    observe("late_response_discarded", operation=operation, attempt=attempt)
                    raise BudgetExhausted(operation, attempts, "deadline")
                if ready(value):
                    return value
            except TransportFailure:
                observe("exchange_failed", operation=operation, attempt=attempt)
                if operation == "submission" and not (
                        self.peer_deduplication_assumed or self.unsafe_retry):
                    observe("submission_inconclusive", operation=operation, attempt=attempt)
                    raise AmbiguousSubmission("Remote acceptance unknown; no deduplication contract for retry")
            if attempt < self.max_attempts:
                remaining = deadline - clock()
                if remaining <= 0:
                    raise BudgetExhausted(operation, attempts, "deadline")
                sleep(min(self.retry_delay_seconds, remaining))
        raise BudgetExhausted(operation, attempts, "attempt_limit")
