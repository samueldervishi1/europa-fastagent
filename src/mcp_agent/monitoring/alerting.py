"""
Advanced Error Tracking and Alerting System for FastAgent
Provides intelligent error classification, alerting, and recovery suggestions
"""

import hashlib
import json
import time
import traceback
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Optional email dependencies
try:
    import smtplib
    from email.mime.multipart import MimeMultipart
    from email.mime.text import MimeText

    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    SYSTEM_RESOURCE = "system_resource"
    MCP_SERVER = "mcp_server"
    UNKNOWN = "unknown"


@dataclass
class ErrorEvent:
    id: str
    timestamp: float
    category: ErrorCategory
    severity: AlertSeverity
    message: str
    exception_type: str
    stack_trace: str
    context: Dict[str, Any] = field(default_factory=dict)
    count: int = 1
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)


@dataclass
class Alert:
    id: str
    severity: AlertSeverity
    title: str
    message: str
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False


@dataclass
class AlertRule:
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    severity: AlertSeverity
    message_template: str
    cooldown_seconds: int = 300  # 5 minutes default
    enabled: bool = True


class ErrorTracker:
    """Advanced error tracking with pattern recognition and alerting"""

    def __init__(self, max_errors: int = 5000):
        self.max_errors = max_errors
        self.errors: Dict[str, ErrorEvent] = {}
        self.error_patterns: Dict[str, int] = defaultdict(int)
        self.recent_errors: deque = deque(maxlen=1000)

        # Alert management
        self.alerts: Dict[str, Alert] = {}
        self.alert_rules: List[AlertRule] = []
        self.last_alert_times: Dict[str, float] = {}

        # Configuration
        self.config = {
            "smtp_server": "localhost",
            "smtp_port": 587,
            "email_enabled": False,
            "email_to": [],
            "webhook_url": None,
            "slack_webhook": None,
        }

        self._setup_default_rules()

    def _setup_default_rules(self):
        """Setup default alerting rules"""
        self.alert_rules = [
            AlertRule(
                name="high_error_rate",
                condition=lambda ctx: ctx.get("error_rate_per_minute", 0) > 10,
                severity=AlertSeverity.HIGH,
                message_template="High error rate detected: {error_rate_per_minute} errors/minute",
            ),
            AlertRule(
                name="critical_system_error",
                condition=lambda ctx: ctx.get("category") == ErrorCategory.SYSTEM_RESOURCE,
                severity=AlertSeverity.CRITICAL,
                message_template="Critical system resource error: {message}",
            ),
            AlertRule(
                name="mcp_server_down",
                condition=lambda ctx: ctx.get("category") == ErrorCategory.MCP_SERVER and ctx.get("consecutive_failures", 0) > 3,
                severity=AlertSeverity.HIGH,
                message_template="MCP Server {server_name} appears to be down (3+ consecutive failures)",
            ),
            AlertRule(
                name="authentication_failures",
                condition=lambda ctx: ctx.get("category") == ErrorCategory.AUTHENTICATION and ctx.get("count", 0) > 5,
                severity=AlertSeverity.MEDIUM,
                message_template="Multiple authentication failures detected ({count} attempts)",
            ),
        ]

    def categorize_error(self, exception: Exception, context: Dict[str, Any]) -> ErrorCategory:
        """Categorize error based on exception type and context"""
        exception_name = type(exception).__name__.lower()
        error_message = str(exception).lower()

        # Connection-related errors
        if any(keyword in exception_name for keyword in ["connection", "network", "socket"]):
            return ErrorCategory.CONNECTION

        if any(keyword in error_message for keyword in ["connection refused", "network unreachable", "timeout"]):
            return ErrorCategory.CONNECTION

        # Authentication errors
        if any(keyword in exception_name for keyword in ["auth", "permission", "access"]):
            return ErrorCategory.AUTHENTICATION

        if any(keyword in error_message for keyword in ["unauthorized", "forbidden", "invalid token", "api key"]):
            return ErrorCategory.AUTHENTICATION

        # Timeout errors
        if "timeout" in exception_name or "timeout" in error_message:
            return ErrorCategory.TIMEOUT

        # Rate limiting
        if any(keyword in error_message for keyword in ["rate limit", "too many requests", "429"]):
            return ErrorCategory.RATE_LIMIT

        # Validation errors
        if any(keyword in exception_name for keyword in ["validation", "value", "type"]):
            return ErrorCategory.VALIDATION

        # System resource errors
        if any(keyword in exception_name for keyword in ["memory", "disk", "resource"]):
            return ErrorCategory.SYSTEM_RESOURCE

        # MCP server errors
        if context.get("source") == "mcp_server":
            return ErrorCategory.MCP_SERVER

        return ErrorCategory.UNKNOWN

    def determine_severity(self, category: ErrorCategory, error_count: int, context: Dict[str, Any]) -> AlertSeverity:
        """Determine error severity based on category and context"""
        if category == ErrorCategory.SYSTEM_RESOURCE:
            return AlertSeverity.CRITICAL

        if category == ErrorCategory.MCP_SERVER and error_count > 3:
            return AlertSeverity.HIGH

        if category in [ErrorCategory.CONNECTION, ErrorCategory.TIMEOUT] and error_count > 5:
            return AlertSeverity.HIGH

        if error_count > 10:
            return AlertSeverity.MEDIUM

        return AlertSeverity.LOW

    def generate_error_id(self, exception: Exception, context: Dict[str, Any]) -> str:
        """Generate unique error ID based on exception type and location"""
        error_signature = f"{type(exception).__name__}:{exception}:{context.get('function', '')}"
        return hashlib.md5(error_signature.encode()).hexdigest()[:12]

    async def track_error(self, exception: Exception, context: Optional[Dict[str, Any]] = None):
        """Track an error event with intelligent categorization"""
        if context is None:
            context = {}

        error_id = self.generate_error_id(exception, context)
        category = self.categorize_error(exception, context)
        current_time = time.time()

        # Update or create error event
        if error_id in self.errors:
            error_event = self.errors[error_id]
            error_event.count += 1
            error_event.last_seen = current_time
        else:
            error_event = ErrorEvent(
                id=error_id,
                timestamp=current_time,
                category=category,
                severity=self.determine_severity(category, 1, context),
                message=str(exception),
                exception_type=type(exception).__name__,
                stack_trace=traceback.format_exc(),
                context=context,
                first_seen=current_time,
                last_seen=current_time,
            )
            self.errors[error_id] = error_event

        # Update severity based on new count
        error_event.severity = self.determine_severity(category, error_event.count, context)

        # Add to recent errors
        self.recent_errors.append({"id": error_id, "timestamp": current_time, "category": category.value, "message": str(exception)})

        # Check alert conditions
        await self._check_alert_conditions(error_event)

        # Clean up old errors if we exceed max
        if len(self.errors) > self.max_errors:
            oldest_errors = sorted(self.errors.values(), key=lambda e: e.last_seen)
            for old_error in oldest_errors[:100]:  # Remove oldest 100
                del self.errors[old_error.id]

    async def _check_alert_conditions(self, error_event: ErrorEvent):
        """Check if error event triggers any alert rules"""
        current_time = time.time()

        # Calculate metrics for alert rules
        error_rate = self._calculate_error_rate()

        alert_context = {
            "error_rate_per_minute": error_rate,
            "category": error_event.category,
            "message": error_event.message,
            "count": error_event.count,
            "server_name": error_event.context.get("server_name", "unknown"),
            "consecutive_failures": error_event.context.get("consecutive_failures", 0),
        }

        for rule in self.alert_rules:
            if not rule.enabled:
                continue

            rule_key = f"{rule.name}_{error_event.id}"

            # Check cooldown
            if rule_key in self.last_alert_times and current_time - self.last_alert_times[rule_key] < rule.cooldown_seconds:
                continue

            # Check condition
            if rule.condition(alert_context):
                await self._create_alert(rule, alert_context, error_event)
                self.last_alert_times[rule_key] = current_time

    def _calculate_error_rate(self) -> float:
        """Calculate errors per minute over last 5 minutes"""
        current_time = time.time()
        cutoff_time = current_time - 300  # 5 minutes

        recent_count = sum(1 for error in self.recent_errors if error["timestamp"] > cutoff_time)

        return recent_count / 5  # errors per minute

    async def _create_alert(self, rule: AlertRule, context: Dict[str, Any], error_event: ErrorEvent):
        """Create and send alert"""
        alert_id = f"{rule.name}_{int(time.time())}"

        message = rule.message_template.format(**context)

        alert = Alert(
            id=alert_id,
            severity=rule.severity,
            title=f"FastAgent Alert: {rule.name}",
            message=message,
            timestamp=time.time(),
            context=context,
        )

        self.alerts[alert_id] = alert

        # Send alert via configured channels
        await self._send_alert(alert)

    async def _send_alert(self, alert: Alert):
        """Send alert via configured channels"""
        if self.config.get("email_enabled") and self.config.get("email_to") and EMAIL_AVAILABLE:
            await self._send_email_alert(alert)

        if self.config.get("webhook_url"):
            await self._send_webhook_alert(alert)

    async def _send_email_alert(self, alert: Alert):
        """Send alert via email"""
        if not EMAIL_AVAILABLE:
            print("Email alerting not available - missing email dependencies")
            return

        try:
            msg = MimeMultipart()
            msg["From"] = "fastagent@europa.local"
            msg["To"] = ", ".join(self.config["email_to"])
            msg["Subject"] = f"[{alert.severity.value.upper()}] {alert.title}"

            body = f"""
FastAgent Alert

Severity: {alert.severity.value.upper()}
Time: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(alert.timestamp))}

Message: {alert.message}

Context:
{json.dumps(alert.context, indent=2)}
            """

            msg.attach(MimeText(body, "plain"))

            server = smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"])
            server.send_message(msg)
            server.quit()

        except Exception as e:
            print(f"Failed to send email alert: {e}")

    async def _send_webhook_alert(self, alert: Alert):
        """Send alert via webhook"""
        try:
            import aiohttp

            payload = {
                "alert_id": alert.id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp,
                "context": alert.context,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.config["webhook_url"], json=payload) as response:
                    if response.status != 200:
                        print(f"Webhook alert failed: {response.status}")

        except Exception as e:
            print(f"Failed to send webhook alert: {e}")

    def get_error_summary(self) -> Dict[str, Any]:
        """Get comprehensive error summary"""
        current_time = time.time()

        # Group errors by category
        category_counts = defaultdict(int)
        severity_counts = defaultdict(int)

        for error in self.errors.values():
            category_counts[error.category.value] += error.count
            severity_counts[error.severity.value] += 1

        # Recent errors (last hour)
        recent_cutoff = current_time - 3600
        recent_errors = [e for e in self.errors.values() if e.last_seen > recent_cutoff]

        return {
            "total_unique_errors": len(self.errors),
            "total_error_count": sum(e.count for e in self.errors.values()),
            "recent_errors_count": len(recent_errors),
            "error_rate_per_minute": self._calculate_error_rate(),
            "category_breakdown": dict(category_counts),
            "severity_breakdown": dict(severity_counts),
            "active_alerts": len([a for a in self.alerts.values() if not a.resolved]),
            "top_errors": sorted([(e.id, e.message, e.count) for e in self.errors.values()], key=lambda x: x[2], reverse=True)[:10],
        }

    def configure_alerts(self, config: Dict[str, Any]):
        """Configure alert settings"""
        self.config.update(config)

    def acknowledge_alert(self, alert_id: str):
        """Acknowledge an alert"""
        if alert_id in self.alerts:
            self.alerts[alert_id].acknowledged = True

    def resolve_alert(self, alert_id: str):
        """Mark alert as resolved"""
        if alert_id in self.alerts:
            self.alerts[alert_id].resolved = True


# Global error tracker instance
error_tracker = ErrorTracker()
