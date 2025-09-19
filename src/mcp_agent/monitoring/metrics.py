"""
Metrics Collection System for FastAgent
Tracks performance metrics, response times, and error rates
"""

import asyncio
import json
import statistics
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    name: str
    type: MetricType
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSummary:
    name: str
    count: int
    min_value: float
    max_value: float
    avg_value: float
    median_value: float
    p95_value: float
    p99_value: float
    last_updated: float


class MetricsCollector:
    """Thread-safe metrics collection system"""

    def __init__(self, max_samples: int = 10000):
        self.max_samples = max_samples
        self._lock = threading.RLock()

        # Storage for different metric types
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=max_samples))
        self.timers: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=max_samples))

        # Labels and metadata
        self.metric_labels: Dict[str, Dict[str, str]] = {}
        self.metric_metadata: Dict[str, Dict[str, Any]] = {}

        # Error tracking
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_rates: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=100))

        # Request tracking
        self.request_counts: Dict[str, int] = defaultdict(int)
        self.response_times: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=1000))

        self.start_time = time.time()

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        with self._lock:
            self.counters[name] += value
            if labels:
                self.metric_labels[name] = labels

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric value"""
        with self._lock:
            self.gauges[name] = value
            if labels:
                self.metric_labels[name] = labels

    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a value in a histogram"""
        with self._lock:
            self.histograms[name].append(value)
            if labels:
                self.metric_labels[name] = labels

    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None):
        """Record a timing measurement"""
        with self._lock:
            self.timers[name].append(duration)
            if labels:
                self.metric_labels[name] = labels

    def record_request(self, endpoint: str, response_time: float, success: bool = True):
        """Record request metrics"""
        with self._lock:
            self.request_counts[endpoint] += 1
            self.response_times[endpoint].append(response_time)

            if not success:
                self.error_counts[endpoint] += 1
                # Calculate error rate (errors per minute)
                current_time = time.time()
                self.error_rates[endpoint].append(current_time)

    def get_error_rate(self, endpoint: str, window_minutes: int = 5) -> float:
        """Calculate error rate for an endpoint over time window"""
        with self._lock:
            if endpoint not in self.error_rates:
                return 0.0

            current_time = time.time()
            cutoff_time = current_time - (window_minutes * 60)

            # Count errors in time window
            recent_errors = sum(1 for error_time in self.error_rates[endpoint] if error_time > cutoff_time)

            # Get total requests in same window (approximate)
            total_requests = self.request_counts.get(endpoint, 0)
            if total_requests == 0:
                return 0.0

            return (recent_errors / total_requests) * 100

    def get_response_time_stats(self, endpoint: str) -> Optional[MetricSummary]:
        """Get response time statistics for an endpoint"""
        with self._lock:
            if endpoint not in self.response_times or not self.response_times[endpoint]:
                return None

            times = list(self.response_times[endpoint])

            return MetricSummary(
                name=f"{endpoint}_response_time",
                count=len(times),
                min_value=min(times),
                max_value=max(times),
                avg_value=statistics.mean(times),
                median_value=statistics.median(times),
                p95_value=self._percentile(times, 95),
                p99_value=self._percentile(times, 99),
                last_updated=time.time(),
            )

    def _percentile(self, data: List[float], percentile: float) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1]
            return lower + (upper - lower) * (index - int(index))

    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all current metrics"""
        with self._lock:
            metrics = {
                "timestamp": time.time(),
                "uptime_seconds": time.time() - self.start_time,
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "request_counts": dict(self.request_counts),
                "error_counts": dict(self.error_counts),
                "response_time_stats": {},
                "error_rates": {},
            }

            # Add response time statistics
            for endpoint in self.response_times:
                stats = self.get_response_time_stats(endpoint)
                if stats:
                    metrics["response_time_stats"][endpoint] = {
                        "count": stats.count,
                        "min_ms": stats.min_value,
                        "max_ms": stats.max_value,
                        "avg_ms": stats.avg_value,
                        "median_ms": stats.median_value,
                        "p95_ms": stats.p95_value,
                        "p99_ms": stats.p99_value,
                    }

            # Add error rates
            for endpoint in self.error_rates:
                metrics["error_rates"][endpoint] = self.get_error_rate(endpoint)

            return metrics

    async def export_metrics(self, file_path: Path):
        """Export metrics to JSON file"""
        metrics = self.get_all_metrics()
        async with asyncio.Lock():
            with open(file_path, "w") as f:
                json.dump(metrics, f, indent=2)


class TimerContext:
    """Context manager for timing operations"""

    def __init__(self, collector: MetricsCollector, metric_name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.metric_name = metric_name
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (time.time() - self.start_time) * 1000  # Convert to milliseconds
            self.collector.record_timer(self.metric_name, duration, self.labels)


class RequestTracker:
    """Decorator and context manager for tracking requests"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    def track_request(self, endpoint: str):
        """Decorator for tracking function calls as requests"""

        def decorator(func):
            async def wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception:
                    success = False
                    raise
                finally:
                    response_time = (time.time() - start_time) * 1000
                    self.collector.record_request(endpoint, response_time, success)

            return wrapper

        return decorator

    def track_mcp_call(self, server_name: str, method: str):
        """Track MCP server calls"""
        return self.track_request(f"mcp_{server_name}_{method}")


# Global metrics collector instance
metrics_collector = MetricsCollector()
request_tracker = RequestTracker(metrics_collector)
