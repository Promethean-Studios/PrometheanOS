import json

from src.system.security.permissions import (
    AuditLogger,
    PermissionBroker,
    PermissionRequest,
)


def request(operation, confirmed=False, target="test-target", reason="test reason", component="test-agent"):
    return PermissionRequest(operation, target, reason, component, confirmed)


def test_unknown_operation_is_rejected_and_audited():
    logger = AuditLogger()
    broker = PermissionBroker(logger)

    result = broker.request(request("shell.arbitrary", target="sudo rm -rf /"))

    assert result.allowed is False
    assert result.result == "rejected"
    assert result.reason == "operation is not allowlisted"
    assert logger.events[-1]["requested_action"] == "shell.arbitrary"


def test_confirmation_required_operation_is_denied_without_confirmation():
    logger = AuditLogger()
    broker = PermissionBroker(logger)
    broker.register_handler("files.delete", lambda target: None)

    result = broker.request(request("files.delete"))

    assert result.allowed is False
    assert result.result == "confirmation_required"
    assert logger.events[-1]["user_confirmation"] is False


def test_high_risk_operation_requires_explicit_confirmation():
    broker = PermissionBroker()
    broker.register_handler("firewall.modify", lambda target: None)

    denied = broker.request(request("firewall.modify"))
    allowed = broker.request(request("firewall.modify", confirmed=True))

    assert denied.allowed is False
    assert denied.level == "HIGH_RISK"
    assert allowed.allowed is True


def test_safe_operation_requires_registered_non_shell_implementation():
    broker = PermissionBroker()
    request_value = request("read.hardware")

    assert broker.request(request_value).allowed is False
    broker.register_safe_handler("read.hardware", lambda target: {"target": target})
    assert broker.request(request_value).allowed is True


def test_audit_log_excludes_secret_values(tmp_path):
    path = tmp_path / "permission-audit.jsonl"
    logger = AuditLogger(path)
    broker = PermissionBroker(logger)

    broker.request(request("configuration.modify", target="api_key=do-not-log", reason="password=do-not-log"))

    event = json.loads(path.read_text(encoding="utf-8").strip())
    encoded = json.dumps(event)
    assert "do-not-log" not in encoded
    assert event["requested_action"] == "configuration.modify"
    assert "timestamp" in event
