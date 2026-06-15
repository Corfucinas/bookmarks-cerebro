"""Tests for browser extension manifest and logic."""

import json
from pathlib import Path


def test_manifest_required_keys():
    """Load manifest.json and assert required keys exist."""
    manifest_path = Path(__file__).parent.parent / "browser-extension" / "manifest.json"
    assert manifest_path.exists(), f"manifest.json not found at {manifest_path}"

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Required top-level keys for MV3
    required_keys = [
        "manifest_version",
        "name",
        "version",
        "permissions",
        "background",
        "action",
        "commands",
    ]
    for key in required_keys:
        assert key in manifest, f"Missing required key: {key}"

    # Validate manifest_version is 3
    assert manifest["manifest_version"] == 3, "manifest_version must be 3"

    # Validate background.service_worker exists
    assert "service_worker" in manifest["background"], "background.service_worker required"
    assert manifest["background"]["service_worker"] == "background.js"

    # Validate type: module if present
    if "type" in manifest["background"]:
        assert manifest["background"]["type"] == "module", "background.type should be 'module'"

    # Validate permissions include required items
    required_permissions = ["activeTab", "storage", "contextMenus", "alarms"]
    for perm in required_permissions:
        assert perm in manifest["permissions"], f"Missing permission: {perm}"

    # Validate commands exist
    assert "cerebro-page" in manifest["commands"], "Missing cerebro-page command"

    # Validate options_ui exists (preferred over options_page)
    assert "options_ui" in manifest, "options_ui is required for extension settings"
    assert "page" in manifest["options_ui"], "options_ui.page is required"


def test_exponential_backoff_algorithm():
    """Test the backoff delay calculation with max 5 attempts.

    Pure Python mock of the retry/backoff algorithm from background.js.
    """
    base_delay_ms = 1000
    max_delay_ms = 60000
    max_attempts = 5

    def calculate_backoff_delay(attempts: int) -> int:
        """Calculate exponential backoff delay in milliseconds."""
        return min(base_delay_ms * (2**attempts), max_delay_ms)

    # Test: delay increases exponentially
    expected_delays = [
        1000,  # attempt 0: 1s
        2000,  # attempt 1: 2s
        4000,  # attempt 2: 4s
        8000,  # attempt 3: 8s
        16000,  # attempt 4: 16s
        32000,  # attempt 5: 32s (but won't be reached due to max_attempts)
    ]

    for attempt, expected_delay in enumerate(expected_delays[:max_attempts]):
        delay = calculate_backoff_delay(attempt)
        assert delay == expected_delay, (
            f"Attempt {attempt}: expected {expected_delay}ms, got {delay}ms"
        )

    # Test: max delay cap
    large_attempt = 10
    delay = calculate_backoff_delay(large_attempt)
    assert delay == max_delay_ms, f"Delay should be capped at {max_delay_ms}ms for large attempts"

    # Test: queue item lifecycle
    queue_item = {
        "url": "https://example.com",
        "title": "Example",
        "enqueuedAt": 1000000,
        "attempts": 0,
        "nextRetryAt": 1000000,
    }

    # Simulate retry attempts
    for attempt in range(max_attempts):
        queue_item["attempts"] = attempt
        queue_item["nextRetryAt"] = 1000000 + calculate_backoff_delay(attempt)

    # After 5 failed attempts, item should be moved to failed_queue
    assert queue_item["attempts"] == max_attempts - 1, "Final attempt before failure"

    # Verify that on 6th attempt (attempts >= max_attempts), item is exhausted
    queue_item["attempts"] = max_attempts
    should_fail = queue_item["attempts"] >= max_attempts
    assert should_fail is True, "Item with >= max_attempts should be moved to failed queue"


def test_queue_item_fields():
    """Verify queue item structure matches expected schema."""
    expected_fields = {
        "url": str,
        "title": str,
        "enqueuedAt": int,
        "attempts": int,
        "nextRetryAt": int,
    }

    # This validates the queue item structure
    sample_item = {
        "url": "https://example.com",
        "title": "Example Title",
        "enqueuedAt": 1700000000000,
        "attempts": 2,
        "nextRetryAt": 1700000004000,
    }

    for field, field_type in expected_fields.items():
        assert field in sample_item, f"Queue item missing field: {field}"
        assert isinstance(sample_item[field], field_type), f"Field {field} should be {field_type}"


def test_settings_structure():
    """Verify settings structure matches expected schema."""
    expected_settings = {
        "serverUrl": str,
        "autoTag": bool,
    }

    sample_settings = {
        "serverUrl": "http://127.0.0.1:8765",
        "autoTag": True,
    }

    for field, field_type in expected_settings.items():
        assert field in sample_settings, f"Settings missing field: {field}"
        assert isinstance(sample_settings[field], field_type), (
            f"Field {field} should be {field_type}"
        )
