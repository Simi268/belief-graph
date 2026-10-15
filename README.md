Belief-Graph — Verified Recovery API patch

Included:
- app/main.py: complete updated API file based on the current persistence-enabled main.py
- app/recovery.py: complete RecoveryEngine with optional replacement execution and execution status tracking

What changes:
1. The recovery API reads the simulated failure's expected (actual) and received (assumed) versions.
2. It configures DynamicAPIEnvironment to the actual version.
3. It passes the environment into RecoveryEngine so the replacement action is executed once.
4. It reports `recovered` only if the environment confirms the retry succeeded; otherwise `retry_failed`.
5. If no replacement action can be executed, status is `recovery_planned` or `revised`.
6. The endpoint persists the graph after recovery, including execution status/result fields.

Before replacing:
- Make a backup copy of app/main.py and app/recovery.py.
- This assumes app/environment.py has DynamicAPIEnvironment and set_api_version(), and app/models.py and app/replanner.py are from the execution upgrade (ActionExecutionStatus, execution_status, execution_result).
- The API simulates an environment based on the failure evidence supplied by the UI; it is a deterministic demo environment, not a live external API.

After replacing both files, run:
    python -m pytest -q

Then restart the backend:
    python -m uvicorn app.main:app --reload

No claim is made that the user's local tests have been run.
