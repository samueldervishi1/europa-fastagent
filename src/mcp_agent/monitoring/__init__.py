"""
Monitoring package for FastAgent
Provides metrics collection and error tracking capabilities
"""

from .alerting import AlertSeverity, ErrorCategory, ErrorTracker, error_tracker
from .metrics import MetricsCollector, TimerContext, metrics_collector, request_tracker

__all__ = [
    "metrics_collector",
    "request_tracker",
    "MetricsCollector",
    "TimerContext",
    "error_tracker",
    "ErrorTracker",
    "AlertSeverity",
    "ErrorCategory",
]
