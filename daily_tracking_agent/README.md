# Daily Tracking Control Tool

Local-first Python tool for daily system/software task tracking. It reads only a OneDrive-synced local Excel file, copies it to a temp folder, analyzes the temp copy, writes local reports, and optionally sends a concise summary to Microsoft Teams through a Power Automate webhook.

## What It Does

- Validates OneDrive/local file readiness before reading Excel.
- Copies the Excel file to `temp/` and analyzes only the temp copy.
- Keeps a last-good local snapshot so the morning report can still run if the live workbook is locked by Excel/OneDrive.
- Checks schedule, progress, delta, estimate sanity, overload, blockers, and data quality.
- Detects urgent/unplanned work and estimates affected planned tasks plus OT hours.
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

## Tomorrow Company-PC Setup Checklist

Use this short path when setting up the common/company Windows machine.

1. Put the repo here:

```text
D:\Tool_xam\BlackSlave\daily_tracking_agent
```

2. Open PowerShell:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
python --version
ollama list
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip check
```

3. Edit `config.yaml`:

```yaml
sync.folder_path: local OneDrive folder containing the tracking Excel
sync.tracking_file: exact tracking workbook file name
report.output_folder: OneDrive/SharePoint-synced Reports folder
urgent.external_file: OneDrive/SharePoint-synced urgent_tasks.xlsx
command_inbox.file: OneDrive/SharePoint-synced tracking_commands.xlsx
ollama.model: one model from `ollama list`
teams.webhook_url: Power Automate HTTP POST URL containing `sig=`
teams.enabled: true
```

4. Copy or keep these intake files in the configured OneDrive folder:

```text
urgent_tasks.xlsx
Sheet: UrgentTasks
Table: UrgentTasksTable

tracking_commands.xlsx
Sheet: Commands
Table: TrackingCommandsTable
```

5. Test once without Teams:

```powershell
python main.py --config config.yaml --dry-run --no-ollama
```

6. Test Teams webhook:

```powershell
python main.py --config config.yaml --no-ollama
```

7. Register 08:00 daily run:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_windows_task.ps1 -StartTime "08:00"
```

8. Register Teams command inbox checker:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_command_inbox_task.ps1 -StartTime "07:30" -EndTime "19:30" -IntervalMinutes 1
```

After this, normal usage is only:

```text
08:00 auto short report -> Teams
Team member posts "check Lion" -> Power Automate writes tracking_commands.xlsx -> common PC replies to Teams
Double-click RUN_URGENT_IMPACT.bat when urgent work appears
Double-click ASK_TRACKING.bat when you want a member report
```

## Files You Usually Touch

```text
config.yaml                              Main configuration
RUN_DAILY_WITH_OLLAMA.bat                Double-click daily run
ASK_TRACKING.bat                         Double-click local question mode
RUN_COMMAND_INBOX.bat                    Double-click one command inbox check
scripts/register_windows_task.ps1        Register 08:00 scheduled run
scripts/register_command_inbox_task.ps1  Register Teams command inbox checker
modules/report_builder.py                Teams/full report structure
modules/query_engine.py                  Member report / Q&A structure
modules/ollama_reviewer.py               Ollama prompts
modules/rule_checker.py                  Tracking sanity rules
modules/urgent_impact_analyzer.py        Urgent/unplanned impact and OT analyzer
urgent_tasks.xlsx                        Reviewable urgent/unplanned work intake file
tracking_commands.xlsx                   Teams command inbox file
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
  allow_snapshot_when_locked: true
  max_snapshot_age_hours: 24
  snapshot_folder: "D:/Tool_xam/BlackSlave/daily_tracking_agent/temp/source_snapshots"
```

Use `/` in YAML paths. Do not paste a SharePoint URL.

Find the Excel file name:

```powershell
dir "C:\Users\HuyTQ136\FPT Software Company Limited\OnedriveSharing - TMCSYSAUTOSA1\No2.LowVoltagePowerSupplySystem\00_Share\02_FromFPT\01_Project_Management\02_Project_Plan\*.xlsx"
```

### If The Excel File Is Open/Locked

The first successful run stores a last-good snapshot under `temp/source_snapshots/`.

Morning behavior:

```text
1. Validate OneDrive folder and tracking file.
2. Try to copy the live Excel file to temp.
3. If the live file is locked, retry until wait_sync_seconds.
4. If still locked and allow_snapshot_when_locked=true, use the last-good snapshot.
5. Add a High sync warning into Teams/report so everyone knows the report may not include latest edits.
```

This still never analyzes the source workbook directly and never writes back to it. If there is no snapshot yet, the tool fails before Excel analysis and can send a failure notification.

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

### Urgent / Unplanned Work Impact

The tool can detect urgent work automatically from `Item`, `Target`, and `Note` text. No extra user input is required if the tracking sheet contains words such as `urgent`, `hotfix`, `support`, or `unplanned`.

Config:

```yaml
urgent:
  enabled: true
  external_file: "C:/Users/HuyTQ136/FPT Software Company Limited/OnedriveSharing - TMCSYSAUTOSA1/No2.LowVoltagePowerSupplySystem/00_Share/02_FromFPT/01_Project_Management/02_Project_Plan/urgent_tasks.xlsx"
  sheet_name: "UrgentTasks"
  impact_window_days: 5
  keywords:
    - urgent
    - hotfix
    - ad-hoc
    - adhoc
    - unplanned
    - escalation
    - support
    - interrupt
    - firefighting
    - production issue
    - customer urgent
```

For local testing inside the repo, this can stay as:

```yaml
external_file: "./urgent_tasks.xlsx"
```

### Teams Command Inbox

Config:

```yaml
command_inbox:
  enabled: true
  file: "C:/Users/HuyTQ136/FPT Software Company Limited/.../02_Project_Plan/tracking_commands.xlsx"
  sheet_name: "Commands"
  max_commands_per_run: 5
  max_response_chars: 4000
```

For local testing inside the repo:

```yaml
file: "./tracking_commands.xlsx"
```

What it reports:

- urgent/unplanned remaining MH by PIC,
- total priority work today versus 8 MH/day capacity,
- estimated OT hours,
- planned tasks likely affected by urgent work,
- suggested daily question for re-prioritization.

Example:

```text
Urgent impact / OT
- Tiger: urgent 5.0 MH, today total 12.0/8.0 MH, OT 4.0 MH, affected tasks 2
  - may affect Row 21: M1/System spec, due in 1d, rem 4.0 MH
```

### Urgent Task Workbook Format

The recommended intake file is:

```text
urgent_tasks.xlsx
Sheet: UrgentTasks
Table: UrgentTasksTable
```

Recommended columns:

```text
ID
Date
PIC
EstimateMH
Item
Due
Reason
Status
Source
CreatedBy
CreatedAt
TeamsMessage
Decision
ImpactNote
```

Required fields:

```text
PIC
EstimateMH
Item
```

Useful optional fields:

```text
ID, Date, Due, Reason, Status, Source, CreatedBy, CreatedAt, TeamsMessage, Decision, ImpactNote
```

Status handling:

- `open` is included.
- blank status is included.
- `done`, `cancelled`, `canceled`, `closed` are ignored.
- rows dated today are included.
- rows with blank date are included.

Keep this file in a OneDrive-synced folder if Power Automate will append rows to it.

The current recommended setup uses XLSX because the team can filter by PIC/status/date and update `Decision` after the daily discussion.

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

## Power Automate For Urgent Task Capture

This is separate from the report-sending webhook above.

Goal:

```text
User posts urgent command in Teams
-> Power Automate appends one row to urgent_tasks.xlsx
-> You run RUN_URGENT_IMPACT.bat when you want an update
-> Tool reads tracking sheet + urgent_tasks.xlsx
-> Tool posts short impact/OT update to Teams
```

Suggested user command format:

```text
urgent Cat 3h support customer issue ABC
urgent Tiger 2h hotfix integration build
urgent Lion 1.5h clarify customer question
```

Recommended XLSX target:

```text
C:\Users\HuyTQ136\FPT Software Company Limited\...\02_Project_Plan\urgent_tasks.xlsx
```

### Manual First

Before automating Power Automate append, open `urgent_tasks.xlsx` and add one row in sheet `UrgentTasks`:

```text
ID: U-001
Date: 2026-05-23
PIC: Cat
EstimateMH: 3
Item: Support customer issue ABC
Due: today
Reason: Customer escalation
Status: open
Source: manual
```

Then run:

```powershell
python main.py --config config.yaml --urgent-impact-only --dry-run --no-ollama
```

If output looks correct, run without `--dry-run` to send Teams:

```powershell
python main.py --config config.yaml --urgent-impact-only --no-ollama
```

### Power Automate Append Idea

Use a Teams trigger that your tenant allows, for example:

```text
When a new message is added in a chat or channel
```

or a Teams workflow trigger for selected chat/channel messages.

Flow shape:

```text
Trigger: new Teams message
Condition: message starts with "urgent "
Parse: urgent <PIC> <MH>h <description>
Action: append row to urgent_tasks.xlsx / UrgentTasksTable
```

The local Python tool does not need Graph API. Power Automate only captures the urgent command into a small Excel intake file.

Simple parsed fields:

```text
ID = concat('U-', formatDateTime(utcNow(),'yyyyMMdd-HHmmss'))
Date = formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd')
PIC = second token
EstimateMH = number before "h"
Item = remaining text
Due = today
Status = open
Source = teams
CreatedAt = current time
TeamsMessage = original message text
```

If parsing in Power Automate is too annoying, use a stricter command:

```text
urgent|Cat|3|support customer issue ABC
urgent|Tiger|2|hotfix integration build
```

Then split by `|` and append columns directly.

For the append action, use:

```text
Excel Online (Business) - Add a row into a table
Location: OneDrive for Business
Document Library: OneDrive
File: urgent_tasks.xlsx
Table: UrgentTasksTable
```

Map the columns:

```text
ID           -> concat('U-', formatDateTime(utcNow(),'yyyyMMdd-HHmmss'))
Date         -> formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd')
PIC          -> parsed PIC
EstimateMH   -> parsed hour number
Item         -> parsed description
Due          -> today
Reason       -> parsed description or blank
Status       -> open
Source       -> teams
CreatedBy    -> sender display name
CreatedAt    -> formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd HH:mm')
TeamsMessage -> original message body
```

### Recommended Low-Effort Workflow

1. User posts urgent command in Teams.
2. Power Automate appends row to `urgent_tasks.xlsx`.
3. When PM/Huy wants update, double-click:

```text
RUN_URGENT_IMPACT.bat
```

4. Tool posts short impact:

```text
Urgent Impact Update - 2026-05-23

Cat: urgent 3.0h + planned 5.6h = 8.6/8h -> OT 0.6h
May affect:
- Row 34: Code-action, due in 2d, rem 2.8h
Decision: reassign/defer affected tasks or accept OT.
```

This avoids polling every 15 minutes and keeps the tool on-demand.

## Power Automate For Member Quick Check

Use this when a member wants a short answer in the Teams group during the day.

Goal:

```text
Member posts "check Lion" in Teams
-> Power Automate appends one row to tracking_commands.xlsx
-> Common PC scheduled task checks pending commands every 1 minute
-> Tool reads tracking Excel temp copy
-> Tool sends short answer back to Teams
-> Tool marks command row as done/error
```

Suggested Teams commands:

```text
check Lion
report Cat
Tiger hôm nay làm gì
check Lion Cat
```

Recommended XLSX target:

```text
C:\Users\HuyTQ136\FPT Software Company Limited\...\02_Project_Plan\tracking_commands.xlsx
```

The file must contain:

```text
Sheet: Commands
Table: TrackingCommandsTable
```

Required columns:

```text
ID
Command
Status
```

Recommended columns:

```text
ID, Date, Command, RequestedBy, Status, CreatedAt, ProcessedAt, Response, TeamsMessage
```

Power Automate flow shape:

```text
Trigger: new Teams message
Condition: message starts with "check " OR "report "
Action: Excel Online (Business) - Add a row into a table
File: tracking_commands.xlsx
Table: TrackingCommandsTable
Status: pending
```

Map the columns:

```text
ID           -> concat('CMD-', formatDateTime(utcNow(),'yyyyMMdd-HHmmss'))
Date         -> formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd')
Command      -> original message text
RequestedBy  -> sender display name
Status       -> pending
CreatedAt    -> formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd HH:mm')
TeamsMessage -> original message body
```

Register the common PC checker once:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_command_inbox_task.ps1 -StartTime "07:30" -EndTime "19:30" -IntervalMinutes 1
```

Manual test:

```powershell
python main.py --config config.yaml --process-command-inbox --dry-run --no-ollama
```

This checker is not a full report loop. If there is no pending command, it exits quickly and does not analyze the tracking sheet.

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

## On-Demand Urgent Impact Update

Use this when urgent work appears after the 08:00 report and you want a short impact/OT update.

Dry-run:

```powershell
python main.py --config config.yaml --urgent-impact-only --dry-run --no-ollama
```

Send Teams:

```powershell
python main.py --config config.yaml --urgent-impact-only --no-ollama
```

Double-click:

```text
RUN_URGENT_IMPACT.bat
```

This mode still validates OneDrive sync and analyzes a temp copy of the tracking Excel. It does not keep a terminal running.

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
- Urgent impact / OT,
- Blockers,
- Data fix,
- Daily questions,
- Full report path.

Full Markdown report includes:

- Executive Summary,
- Today Commitment,
- Re-plan Needed,
- Urgent Impact / OT,
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

Urgent/unplanned impact and OT calculation:

```text
modules/urgent_impact_analyzer.py
config.yaml -> urgent
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
