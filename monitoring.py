"""Bounded, process-local aggregate counters. Never retain request profiles."""
from collections import Counter
from threading import Lock


class ServiceMetrics:
    def __init__(self):
        self._lock = Lock()
        self.requests = Counter()
        self.duration_seconds = 0.0
        self.out_of_range = Counter()

    def record(self, outcome: str, duration: float, outside: list[str]):
        with self._lock:
            self.requests[outcome] += 1
            self.duration_seconds += duration
            self.out_of_range.update(outside)

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP careestimate_requests_total Prediction requests by outcome.",
                "# TYPE careestimate_requests_total counter",
            ]
            for outcome in ("success", "validation_error", "unavailable", "failure"):
                lines.append(f'careestimate_requests_total{{outcome="{outcome}"}} {self.requests[outcome]}')
            lines.extend([
                "# HELP careestimate_prediction_duration_seconds_sum Total successful inference time.",
                "# TYPE careestimate_prediction_duration_seconds_sum counter",
                f"careestimate_prediction_duration_seconds_sum {self.duration_seconds}",
                "# HELP careestimate_out_of_range_total Successful profiles outside recorded training ranges.",
                "# TYPE careestimate_out_of_range_total counter",
            ])
            for name, count in sorted(self.out_of_range.items()):
                lines.append(f'careestimate_out_of_range_total{{feature="{name}"}} {count}')
            return "\n".join(lines) + "\n"
