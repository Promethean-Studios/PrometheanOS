from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Mapping, Optional


class PermissionCategory(str, Enum):
    READ_SYSTEM_INFO = "READ_SYSTEM_INFO"
    READ_HARDWARE = "READ_HARDWARE"
    READ_PROCESSES = "READ_PROCESSES"
    INSTALL_SOFTWARE = "INSTALL_SOFTWARE"
    MODIFY_CONFIGURATION = "MODIFY_CONFIGURATION"
    EXECUTE_COMMAND = "EXECUTE_COMMAND"
    DELETE_FILES = "DELETE_FILES"
    ADMIN_OPERATION = "ADMIN_OPERATION"


class PermissionLevel(str, Enum):
    SAFE = "SAFE"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    HIGH_RISK = "HIGH_RISK"


@dataclass(frozen=True)
class OperationPolicy:
    operation: str
    category: PermissionCategory
    level: PermissionLevel
    description: str


@dataclass(frozen=True)
class PermissionRequest:
    operation: str
    target: str
    reason: str
    requesting_component: str
    user_confirmed: bool = False


@dataclass(frozen=True)
class PermissionResult:
    allowed: bool
    operation: str
    target: str
    level: Optional[str]
    result: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


SAFE_OPERATIONS = {
    "read.system_status": OperationPolicy("read.system_status", PermissionCategory.READ_SYSTEM_INFO, PermissionLevel.SAFE, "Read Promethean system status"),
    "read.hardware": OperationPolicy("read.hardware", PermissionCategory.READ_HARDWARE, PermissionLevel.SAFE, "Read hardware capabilities"),
    "read.processes": OperationPolicy("read.processes", PermissionCategory.READ_PROCESSES, PermissionLevel.SAFE, "Read AI workload process metadata"),
}

CONFIRMATION_OPERATIONS = {
    "software.install": OperationPolicy("software.install", PermissionCategory.INSTALL_SOFTWARE, PermissionLevel.CONFIRMATION_REQUIRED, "Install explicitly selected software"),
    "configuration.modify": OperationPolicy("configuration.modify", PermissionCategory.MODIFY_CONFIGURATION, PermissionLevel.CONFIRMATION_REQUIRED, "Modify an explicitly selected configuration"),
    "service.stop": OperationPolicy("service.stop", PermissionCategory.ADMIN_OPERATION, PermissionLevel.CONFIRMATION_REQUIRED, "Stop an explicitly selected service"),
    "files.delete": OperationPolicy("files.delete", PermissionCategory.DELETE_FILES, PermissionLevel.CONFIRMATION_REQUIRED, "Delete explicitly selected files"),
}

HIGH_RISK_OPERATIONS = {
    "boot.modify": OperationPolicy("boot.modify", PermissionCategory.ADMIN_OPERATION, PermissionLevel.HIGH_RISK, "Modify boot configuration"),
    "partition.modify": OperationPolicy("partition.modify", PermissionCategory.ADMIN_OPERATION, PermissionLevel.HIGH_RISK, "Modify disk partitions"),
    "firewall.modify": OperationPolicy("firewall.modify", PermissionCategory.ADMIN_OPERATION, PermissionLevel.HIGH_RISK, "Modify firewall configuration"),
    "system.privileged_modify": OperationPolicy("system.privileged_modify", PermissionCategory.ADMIN_OPERATION, PermissionLevel.HIGH_RISK, "Perform a privileged system modification"),
}

OPERATION_POLICIES = {**SAFE_OPERATIONS, **CONFIRMATION_OPERATIONS, **HIGH_RISK_OPERATIONS}
_SECRET_KEY = re.compile(r"(password|passwd|secret|token|api[_-]?key|private[_-]?key|credential)", re.I)


def _safe_text(value: Any) -> str:
    text = str(value)
    return "[REDACTED]" if _SECRET_KEY.search(text) else text[:512]


class AuditLogger:
    """Append safe permission events; never records commands or secret arguments."""

    def __init__(self, path: Optional[Path | str] = None):
        self.path = Path(path) if path else None
        self.events = []
        self._lock = Lock()

    def record(self, request: PermissionRequest, result: PermissionResult) -> None:
        event = {
            "requested_action": _safe_text(request.operation),
            "requesting_component": _safe_text(request.requesting_component),
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "result": result.result,
            "user_confirmation": bool(request.user_confirmed),
            "target": _safe_text(request.target),
        }
        with self._lock:
            self.events.append(event)
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, sort_keys=True) + "\n")


class PermissionBroker:
    """Authorize named operations; it intentionally has no shell or sudo interface."""

    def __init__(self, audit_logger: Optional[AuditLogger] = None, policies: Optional[Mapping[str, OperationPolicy]] = None):
        self.audit_logger = audit_logger or AuditLogger()
        self.policies = dict(policies or OPERATION_POLICIES)
        self._handlers: Dict[str, Callable[[str], Any]] = {}

    def describe(self) -> Dict[str, Any]:
        return {
            operation: {"category": policy.category.value, "level": policy.level.value, "description": policy.description}
            for operation, policy in sorted(self.policies.items())
        }

    def register_safe_handler(self, operation: str, handler: Callable[[str], Any]) -> None:
        policy = self.policies.get(operation)
        if policy is None or policy.level is not PermissionLevel.SAFE:
            raise ValueError("register_safe_handler only accepts known SAFE operations")
        self._handlers[operation] = handler

    def register_handler(self, operation: str, handler: Callable[[str], Any]) -> None:
        """Register a reviewed, operation-specific implementation.

        This registers capability metadata only; the broker never invokes shell
        commands or arbitrary callables on behalf of an assistant.
        """
        if operation not in self.policies:
            raise ValueError("operation is not allowlisted")
        self._handlers[operation] = handler

    def request(self, request: PermissionRequest) -> PermissionResult:
        policy = self.policies.get(request.operation)
        if policy is None:
            result = PermissionResult(False, request.operation, _safe_text(request.target), None, "rejected", "operation is not allowlisted")
        elif not request.target or not request.reason or not request.requesting_component:
            result = PermissionResult(False, request.operation, _safe_text(request.target), policy.level.value, "rejected", "operation, target, reason, and requesting component are required")
        elif request.operation not in self._handlers:
            result = PermissionResult(False, request.operation, _safe_text(request.target), policy.level.value, "rejected", "operation has no registered implementation")
        elif policy.level is not PermissionLevel.SAFE and not request.user_confirmed:
            result = PermissionResult(False, request.operation, _safe_text(request.target), policy.level.value, "confirmation_required", "explicit user confirmation is required")
        else:
            result = PermissionResult(True, request.operation, _safe_text(request.target), policy.level.value, "authorized", "allowlisted operation authorized")
        self.audit_logger.record(request, result)
        return result
