@echo off
REM NexusPour ERP - Deep Bug Hunter One-Click Trigger
echo ========================================================
echo  NexusPour ERP - Deep Bug Hunter & System Health Audit
echo  Owner & Architect: Omid Pourmahmoud
echo ========================================================
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe tests\deep_bug_hunter.py
) else (
    python tests\deep_bug_hunter.py
)
