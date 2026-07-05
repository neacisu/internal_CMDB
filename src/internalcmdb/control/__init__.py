"""Legacy control-plane modules kept for unit-test coverage.

Runtime code uses ``internalcmdb.governance`` (PolicyEnforcer, ActionWorkflow).
Do not import this package from production paths — it will be removed once
governance tests fully subsume the control/ test suite.
"""
