package domain.abac

# 白皮书 §2.2: 高敏操作会话时长测试

test_allow_system_admin_anything {
    allow with input as {
        "subject": {"roles": ["system_admin"], "clearance_level": "public", "workspace_id": "ws1"},
        "action": {"type": "refund", "category": "financial"},
        "resource": {"type": "payment", "classification": "top_secret", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard", "session_duration_seconds": 10},
    }
}

test_deny_high_privilege_short_session {
    deny with input as {
        "subject": {"roles": ["director"], "clearance_level": "secret", "workspace_id": "ws1"},
        "action": {"type": "refund", "category": "financial"},
        "resource": {"type": "payment", "classification": "public", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard", "session_duration_seconds": 120},
    }
}

test_allow_high_privilege_long_session {
    allow with input as {
        "subject": {"roles": ["director"], "clearance_level": "secret", "workspace_id": "ws1"},
        "action": {"type": "refund", "category": "financial"},
        "resource": {"type": "payment", "classification": "public", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard", "session_duration_seconds": 600},
    }
}

test_allow_normal_action_short_session {
    allow with input as {
        "subject": {"roles": ["analyst"], "clearance_level": "secret", "workspace_id": "ws1"},
        "action": {"type": "view", "category": "general"},
        "resource": {"type": "doc", "classification": "public", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard", "session_duration_seconds": 10},
    }
}

test_deny_insufficient_clearance {
    deny with input as {
        "subject": {"roles": ["guest"], "clearance_level": "public", "workspace_id": "ws1"},
        "action": {"type": "view", "category": "general"},
        "resource": {"type": "doc", "classification": "secret", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard"},
    }
}

test_deny_workspace_isolation {
    deny with input as {
        "subject": {"roles": ["analyst"], "clearance_level": "secret", "workspace_id": "ws1"},
        "action": {"type": "view", "category": "general"},
        "resource": {"type": "doc", "classification": "public", "workspace_id": "ws2"},
        "environment": {"isolation_level": "strict"},
    }
}
