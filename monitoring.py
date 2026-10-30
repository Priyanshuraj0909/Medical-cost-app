"""Bounded, process-local aggregate counters. Never retain request profiles."""
from collections import Counter
from threading import Lock


class ServiceMetrics:
    LATENCY_BOUNDS = (.005, .01, .025, .05, .1, .25, .5, 1, 2, 5)

    def __init__(self):
        self._lock = Lock()
        self.requests = Counter()
        self.duration_seconds = 0.0
        self.out_of_range = Counter()
        self.latency_buckets = Counter()

    def record(self, outcome: str, duration: float, outside: list[str]):
        with self._lock:
            self.requests[outcome] += 1
            if outcome == "success":
                self.duration_seconds += duration
                self.out_of_range.update(outside)
                for bound in self.LATENCY_BOUNDS:
                    if duration <= bound:
                        self.latency_buckets[bound] += 1

    def render(self) -> str:
        with self._lock:
            lines = [
                "# HELP careestimate_requests_total Prediction requests by outcome.",
                "# TYPE careestimate_requests_total counter",
            ]
            for outcome in ("success", "validation_error", "unavailable", "failure"):
                lines.append(f'careestimate_requests_total{{outcome="{outcome}"}} {self.requests[outcome]}')
            lines.extend([
                "# HELP careestimate_prediction_duration_seconds Successful inference latency.",
                "# TYPE careestimate_prediction_duration_seconds histogram",
                f"careestimate_prediction_duration_seconds_sum {self.duration_seconds}",
                f"careestimate_prediction_duration_seconds_count {self.requests['success']}",
                "# HELP careestimate_out_of_range_total Successful profiles outside recorded training ranges.",
                "# TYPE careestimate_out_of_range_total counter",
            ])
            for bound in self.LATENCY_BOUNDS:
                lines.append(f'careestimate_prediction_duration_seconds_bucket{{le="{bound}"}} {self.latency_buckets[bound]}')
            lines.append(f'careestimate_prediction_duration_seconds_bucket{{le="+Inf"}} {self.requests["success"]}')
            for name, count in sorted(self.out_of_range.items()):
                lines.append(f'careestimate_out_of_range_total{{feature="{name}"}} {count}')
            return "\n".join(lines) + "\n"
