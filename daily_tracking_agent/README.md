# Daily Tracking Control Tool

Local-first Python tool for daily system/software task tracking. It reads only a OneDrive-synced local Excel file, copies it to a temp folder, analyzes the temp copy, writes local reports, and optionally sends a concise summary to Microsoft Teams through a Power Automate webhook.

## What It Does

- Validates OneDrive/local file readiness before reading Excel.
- Copies the Excel file to `temp/` and analyzes only the temp copy.
- Checks schedule, progress, delta, estimate sanity, overload, blockers, and data quality.
- Generates Markdown and Excel reports.
- Optionally uses local Ollama only.
- Sends Teams summary through Power Automate.
- Runs manually by double-click or automatically at 08:00 through Windows Task Scheduler.

## Safety Rules

- No SharePoint login.
- No Microsoft Graph API.
- No Azure App Registration.
- No username/password storage.
- No write-back to the source Excel file.
- No full Excel data sent to a cloud LLM.
- Ollama is local only and optional.

## Recommended Windows Folder

This guide assumes:

```text
D:\Tool_xam\BlackSlave\daily_tracking_agent
```

If your folder is different, replace the path in commands.

## Files You Usually Touch

```text
config.yaml                              Main configuration
RUN_DAILY_WITH_OLLAMA.bat                Double-click daily run
ASK_TRACKING.bat                         Double-click local question mode
scripts/register_windows_task.ps1        Register 08:00 scheduled run
modules/report_builder.py                Teams/full report structure
modules/query_engine.py                  Member report / Q&A structure
modules/ollama_reviewer.py               Ollama prompts
modules/rule_checker.py                  Tracking sanity rules
```

## First-Time Machine Setup

If Python and Ollama are already installed, you do not need to install them again.

Check Python:

```powershell
python --version
```

Expected: Python 3.11+.

Check Ollama:

```powershell
ollama list
```

Use an existing model name from this output, for example `llama3.1` or `qwen3b`. You do not need to pull a new model if the model already exists.

Create/install Python environment:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip check
```

If `pip check` prints:

```text
No broken requirements found.
```

the Python setup is OK.

## Config YAML

Open:

```text
D:\Tool_xam\BlackSlave\daily_tracking_agent\config.yaml
```

### OneDrive Local Excel

Set the folder containing the Excel file and the file name:

```yaml
sync:
  folder_path: "C:/Users/HuyTQ136/FPT Software Company Limited/OnedriveSharing - TMCSYSAUTOSA1/No2.LowVoltagePowerSupplySystem/00_Share/02_FromFPT/01_Project_Management/02_Project_Plan"
  tracking_file: "YOUR_TRACKING_FILE.xlsx"
  wait_sync_seconds: 90
  retry_interval_seconds: 5
  max_source_file_age_hours: 24
  fail_on_stale_source: false
```

Use `/` in YAML paths. Do not paste a SharePoint URL.

Find the Excel file name:

```powershell
dir "C:\Users\HuyTQ136\FPT Software Company Limited\OnedriveSharing - TMCSYSAUTOSA1\No2.LowVoltagePowerSupplySystem\00_Share\02_FromFPT\01_Project_Management\02_Project_Plan\*.xlsx"
```

### Report Folder

```yaml
report:
  output_folder: "C:/Users/HuyTQ136/FPT Software Company Limited/OnedriveSharing - TMCSYSAUTOSA1/No2.LowVoltagePowerSupplySystem/00_Share/02_FromFPT/01_Project_Management/02_Project_Plan/Reports"
  max_teams_issues: 3
  max_my_focus_items: 3
  max_team_actions: 5
  max_full_report_issues: 30
  include_raw_issue_table: false
  write_excel: true
```

### Your PIC Names

Put every name variant used for you in the Excel `PIC` column:

```yaml
user:
  my_pic_names:
    - "Huy"
    - "Huy Truong"
    - "Truong Huy"
```

### Ollama

Use a model that already exists in `ollama list`:

```yaml
ollama:
  enabled: true
  base_url: "http://localhost:11434"
  model: "llama3.1"
  timeout_seconds: 60
  max_rows_for_ai_review: 20
```

If your Ollama runs on port `11435`, use:

```yaml
base_url: "http://localhost:11435"
```

Test Ollama API:

```powershell
curl http://localhost:11434/api/tags
```

or:

```powershell
curl http://localhost:11435/api/tags
```

Use whichever port returns JSON.

### Teams

After Power Automate is ready, set:

```yaml
teams:
  enabled: true
  webhook_url: "PASTE_HTTP_POST_URL_WITH_SIG_HERE"
  send_failure_notification: true
```

For local testing without Teams:

```yaml
teams:
  enabled: false
```

## Power Automate Setup For Teams

This setup uses a Premium-capable Power Automate HTTP trigger.

### Flow Shape

```text
Trigger: When an HTTP request is received
Action:  Microsoft Teams - Post message in a chat or channel
```

The tool sends:

```json
{
  "text": "Daily report summary..."
}
```

### Create Flow

1. Open `https://make.powerautomate.com`.
2. Create a new flow.
3. Add trigger:

```text
When an HTTP request is received
```

4. In `Request Body JSON Schema`, paste:

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string"
    }
  },
  "required": [
    "text"
  ]
}
```

5. Add action:

```text
Microsoft Teams -> Post message in a chat or channel
```

6. Configure action:

```text
Post as: Flow bot
Post in: Group chat
Group chat: choose your group chat
Message: @{triggerBody()?['text']}
```

If using a channel instead:

```text
Post in: Channel
Team: choose team
Channel: choose channel
Message: @{triggerBody()?['text']}
```

7. Save the flow.
8. Click the trigger again and copy `HTTP POST URL`.

The correct HTTP POST URL usually contains:

```text
/triggers/manual/paths/invoke
sig=
```

Do not copy the browser address bar URL.

### Test Webhook In PowerShell

Use the real HTTP POST URL copied from the trigger:

```powershell
$url = "PASTE_HTTP_POST_URL_WITH_SIG_HERE"

$body = @{
  text = "Test Daily Tracking webhook"
} | ConvertTo-Json

Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
```

If the group chat receives the message, paste the same URL into `config.yaml`.

If you see:

```text
OAuth authorization scheme required
```

you copied the wrong URL. Copy `HTTP POST URL` from the trigger, not the browser URL. The usable URL must include `sig=`.

## Running The Tool

Activate venv:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
.\.venv\Scripts\activate
```

Dry-run without Teams and without Ollama:

```powershell
python main.py --config config.yaml --dry-run --no-ollama
```

Dry-run with Ollama:

```powershell
python main.py --config config.yaml --dry-run --with-ollama
```

Real run with Teams enabled:

```powershell
python main.py --config config.yaml --with-ollama
```

Important: `--dry-run` never sends Teams messages.

Double-click daily run:

```text
RUN_DAILY_WITH_OLLAMA.bat
```

The runner starts Ollama if possible, waits for the API, runs the tool, writes reports, and sends Teams if enabled.

## Ask A Member Question

Examples:

```powershell
python main.py --config config.yaml --pic Tiger --with-ollama
python main.py --config config.yaml --ask "Tiger hôm nay cần làm gì, có trễ hay quá 8h không?" --with-ollama
python main.py --config config.yaml --pic Lion --pic Cat --no-ollama
```

Double-click:

```text
ASK_TRACKING.bat
```

Member report answers:

- what the member should do today,
- whether anything is overdue or due today,
- whether workload exceeds 8 MH/day,
- what “done today” means for selected tasks,
- risks/clarifications.

## Schedule 08:00 Daily Automation

Run once:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_windows_task.ps1 -StartTime "08:00"
```

Then open Windows Task Scheduler and check:

```text
Daily Tracking Control Report
```

Right-click -> `Run` once to test.

At 08:00, Windows runs:

```text
scripts\run_daily_with_ollama.ps1
```

Flow:

```text
Task Scheduler
-> start Ollama if needed
-> validate local OneDrive file
-> copy Excel to temp
-> analyze temp copy
-> write reports
-> POST {"text": "..."} to Power Automate
-> Power Automate posts to Teams group chat/channel
-> tool exits
```

The tool does not keep a terminal running. Ollama may continue running in the background, which is OK.

Remove scheduled task:

```powershell
Unregister-ScheduledTask -TaskName "Daily Tracking Control Report" -Confirm:$false
```

## Report Output

Markdown and Excel reports are written to:

```yaml
report.output_folder
```

Teams summary includes:

- Health and report confidence,
- Do today,
- Member actions today,
- Re-plan needed,
- Blockers,
- Data fix,
- Daily questions,
- Full report path.

Full Markdown report includes:

- Executive Summary,
- Today Commitment,
- Re-plan Needed,
- Blockers,
- Data Quality Must Fix,
- Workload Heatmap,
- My Focus Today,
- Team Actions by PIC,
- Delay Risks,
- Estimate Concerns,
- Suggested Daily Meeting Questions.

## Where To Edit Report Structure

Teams summary and full Markdown/Excel report:

```text
modules/report_builder.py
```

Main functions:

```python
build_teams_summary()
_full_markdown()
```

Member report / local question report:

```text
modules/query_engine.py
```

Main functions:

```python
build_member_report()
build_daily_brief()
```

## Where To Edit Ollama Prompt

Daily suspicious-row reviewer prompt:

```text
modules/ollama_reviewer.py
```

Function:

```python
review_with_ollama()
```

Local Q&A prompt:

```text
modules/ollama_reviewer.py
```

Function:

```python
answer_question_with_ollama()
```

Only filtered/suspicious rows or compact local context are sent to Ollama. The full workbook is not sent.

## Where To Edit Rules

Tracking sanity rules:

```text
modules/rule_checker.py
```

Workload rules:

```text
modules/workload_analyzer.py
```

Estimate baseline rules:

```text
modules/estimate_analyzer.py
config.yaml -> estimate_baseline
```

Priority scoring:

```text
modules/priority_engine.py
```

Excel parsing / header detection:

```text
modules/excel_loader.py
modules/data_normalizer.py
```

Sync validation:

```text
modules/sync_guard.py
```

Teams HTTP sender:

```text
modules/teams_sender.py
```

## Updating An Already-Setup Windows Machine

If the tool is already set up on the company Windows machine, do not reinstall.

Option 1, use git:

```powershell
cd D:\Tool_xam\BlackSlave
git pull
```

Option 2, replace only changed files from GitHub/local copy. For documentation-only updates, replace:

```text
daily_tracking_agent\README.md
```

For report format updates, replace:

```text
daily_tracking_agent\modules\report_builder.py
daily_tracking_agent\modules\query_engine.py
```

For prompt updates, replace:

```text
daily_tracking_agent\modules\ollama_reviewer.py
```

## Troubleshooting

### Excel Lock File

If log says:

```text
~$tracking_file.xlsx exists
```

close Excel, wait for OneDrive sync, then rerun.

### PowerShell Path Has Spaces

Use quotes:

```powershell
cd "C:\Users\HuyTQ136\FPT Software Company Limited\..."
```

### Teams Message Not Sent

Check:

```yaml
teams:
  enabled: true
```

Do not use `--dry-run` for a real Teams send.

Inspect:

```text
logs\daily_tracking_agent.log
```

### Ollama Port

Check:

```powershell
curl http://localhost:11434/api/tags
curl http://localhost:11435/api/tags
```

Use the working port in `ollama.base_url`.

### Ollama Model

Check:

```powershell
ollama list
```

Use the exact model name in:

```yaml
ollama:
  model: "..."
```

### Python Requirements

Inside venv:

```powershell
pip check
python -c "import pandas, openpyxl, requests, pydantic, yaml, tabulate; print('requirements OK')"
```

### Flow Saved But Cannot Be Used

In Power Automate:

- Ensure trigger is `When an HTTP request is received`.
- Ensure schema has `text`.
- Ensure Teams action has `Post as`, `Post in`, chat/channel, and `Message`.
- Message should be:

```text
@{triggerBody()?['text']}
```

No extra HTML text should be visible in the message field.
