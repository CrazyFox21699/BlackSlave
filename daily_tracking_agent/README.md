# Daily Tracking Control Tool

Local-first Python tool for daily system/software task tracking. It reads only a OneDrive-synced local Excel file, copies it to a temp folder, analyzes the temp copy, writes local reports, and optionally sends a short summary to a Power Automate / Teams Workflow webhook.

## Key Safety Rules

- No SharePoint login.
- No Microsoft Graph API.
- No Azure App Registration.
- No username/password storage.
- The source Excel file is never modified.
- Excel analysis starts only after sync validation succeeds.
- The tool analyzes only a temp copy created with `shutil.copy2()`.
- Ollama is optional and local only.
- No full Excel data is sent to any cloud LLM.

## Install

```bash
cd daily_tracking_agent
python -m venv .venv
.venv/Scripts/activate   # Windows
pip install -r requirements.txt
```

On macOS/Linux use `source .venv/bin/activate`.

## Portable Windows Mode

Use this mode when you want to copy the whole folder and run by double-click.

Folder layout for portable use:

```text
daily_tracking_agent/
├─ SETUP_FIRST_TIME.bat
├─ RUN_DAILY_WITH_OLLAMA.bat
├─ ASK_TRACKING.bat
├─ config.yaml
├─ main.py
├─ scripts/
├─ modules/
├─ reports/
├─ temp/
└─ logs/
```

First-time setup:

1. Install Python 3.11+.
2. Install Ollama for Windows if you want local AI review.
3. Double-click `SETUP_FIRST_TIME.bat`.
4. Edit `config.yaml`.

Minimum config to edit:

```yaml
sync:
  folder_path: "C:/Users/Huy/OneDrive - Company/Project/Daily Tracking"
  tracking_file: "daily_tracking_master.xlsx"

report:
  output_folder: "C:/Users/Huy/OneDrive - Company/Project/Daily Tracking/Reports"

teams:
  enabled: true
  webhook_url: "https://..."

ollama:
  enabled: true
```

Daily manual run:

- Double-click `RUN_DAILY_WITH_OLLAMA.bat`.

What the double-click runner does:

- starts Ollama if `ollama` is available,
- waits for `http://localhost:11434/api/tags`,
- runs `main.py --with-ollama`,
- falls back to rule-based mode if Ollama is not installed or not ready,
- writes reports locally,
- sends Teams summary if `teams.enabled: true`.

Local question mode:

- Double-click `ASK_TRACKING.bat`, then type a question such as `Lion hôm nay cần làm gì?`.
- Or run:

```bat
ASK_TRACKING.bat Lion hôm nay cần làm gì?
```

Expected result after double-click daily run:

- a Teams message is posted if webhook is configured,
- Markdown and Excel reports are written to `report.output_folder`,
- logs are written to `logs/daily_tracking_agent.log`,
- the source Excel file is never modified.

If Ollama is not installed or does not start, the same double-click runner still creates a rule-based report.

## Configure OneDrive Sync

Edit `config.yaml`:

```yaml
sync:
  folder_path: "C:/Users/Huy/OneDrive - Company/Project/Daily Tracking"
  tracking_file: "daily_tracking_master.xlsx"
```

Make sure OneDrive has fully synced the folder. If the workbook is open and Excel creates a `~$daily_tracking_master.xlsx` lock file, the tool waits and retries.

## Teams Webhook

Create a Power Automate or Teams Workflow trigger that accepts an HTTP POST body. Configure:

```yaml
teams:
  enabled: true
  webhook_url: "https://..."
  send_failure_notification: true
```

The payload is intentionally simple:

```json
{"text": "summary text"}
```

## Run

```bash
python main.py --config config.yaml
python main.py --config config.yaml --dry-run
python main.py --config config.yaml --no-teams
python main.py --config config.yaml --no-ollama
python main.py --config config.yaml --today 2026-05-23
python main.py --config config.yaml --ask "Lion hôm nay cần làm gì?"
python main.py --config config.yaml --pic Lion --pic Cat
```

`--dry-run` still validates sync, copies the workbook, analyzes data, and writes reports. It does not send Teams messages.

## Ollama

Ollama is disabled in the example config. To enable:

```yaml
ollama:
  enabled: true
  base_url: "http://localhost:11434"
  model: "qwen2.5:7b"
```

Only selected suspicious rows are sent to the local Ollama API, limited by `max_rows_for_ai_review`.

Ollama is used in two optional places:

- Daily review: it reviews only suspicious candidate rows after rule-based checks.
- Local Q&A: when you run `--ask`, the tool first builds a compact local answer from filtered rows/issues, then Ollama can rewrite or reason over that compact context. It does not receive the full Excel workbook.

Examples:

```bash
python main.py --config config.yaml --ask "Lion hôm nay cần làm gì?"
python main.py --config config.yaml --ask "Có task nào estimate quá cao hoặc quá thấp không?"
python main.py --config config.yaml --pic Lion --pic Cat
python main.py --config config.yaml --pic Lion --send-answer-to-teams
```

Each Q&A/member report is also saved under the configured `report.output_folder`.

## Reports

The tool writes:

- Markdown report: executive summary, focus items, team actions, risks, questions, raw issue table.
- Excel report: `Summary`, `MyFocusToday`, `TeamActions`, `Issues`, `WorkloadByPIC`, `DataQuality`, `RawNormalizedData`.

Point `report.output_folder` to a OneDrive-synced report folder if you want the full report synced back to SharePoint through OneDrive.

## Windows Task Scheduler

For full automation, use the included scripts. Register the scheduled task from the project folder:

```powershell
cd C:\Tools\DailyTrackingAgent\daily_tracking_agent
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_windows_task.ps1 -StartTime "08:00"
```

At 08:00 every morning Windows runs `scripts\run_daily_with_ollama.ps1`. The tool starts Ollama if available, validates OneDrive sync readiness, analyzes a temp copy, writes reports, and sends a concise Teams message containing:

- your focus items,
- member actions today,
- delay/overload risks,
- overestimate/underestimate concerns,
- data quality issues,
- daily meeting questions.

Recommended automation setup:

1. Confirm `RUN_DAILY_WITH_OLLAMA.bat` works manually.
2. Confirm Teams webhook receives one test message.
3. Register the scheduled task:

```powershell
cd C:\Tools\DailyTrackingAgent\daily_tracking_agent
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_windows_task.ps1 -StartTime "08:00"
```

4. Open Windows Task Scheduler and verify task `Daily Tracking Control Report`.
5. Use `Run` once from Task Scheduler to test non-interactive execution.

Manual Task Scheduler equivalent if you do not use the included registration script:

- Trigger: every weekday morning.
- Action: Start a program.
- Program: `powershell.exe`
- Arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\Path\To\daily_tracking_agent\scripts\run_daily_with_ollama.ps1"`
- Start in: `C:\Path\To\daily_tracking_agent`

Scheduling is external by design; the app does not run a daemon.

To remove the scheduled task:

```powershell
Unregister-ScheduledTask -TaskName "Daily Tracking Control Report" -Confirm:$false
```

## Dummy Test

```bash
python tests/generate_dummy_excel.py
python main.py --config config.yaml --dry-run
```

This creates `sample_data/daily_tracking_master.xlsx` with a screenshot-style tracker layout: hierarchy columns, two header rows, duplicate `Current Progress` columns, colored progress/delta columns, filter row, summary formulas, and sample invalid values such as `FALSE` in the end-date column.

## Send Teams Automatically Every Morning

1. Create a Power Automate / Teams Workflow with an HTTP request trigger.
2. Put the generated webhook URL into `config.yaml`:

```yaml
teams:
  enabled: true
  webhook_url: "https://..."
  send_failure_notification: true
```

3. Register a daily Windows task at 08:00:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_windows_task.ps1 -StartTime "08:00"
```

The scheduled job runs locally every morning. It first validates OneDrive sync readiness, copies the Excel file to `temp`, analyzes the temp copy, writes local reports, then posts only the concise summary to Teams.

Important: Microsoft Teams does not need to be open for the webhook message to be delivered. When you open Teams in the morning, the posted summary is already in the selected channel/chat.

## Troubleshooting

If the tool says an Excel lock file exists:

- close the workbook in Excel,
- wait for OneDrive to finish syncing,
- rerun the tool.

If Teams does not receive a message:

- check `teams.enabled: true`,
- check the webhook URL,
- run `RUN_DAILY_WITH_OLLAMA.bat` manually and inspect `logs/daily_tracking_agent.log`.

If Ollama does not start:

- confirm `ollama` works in Command Prompt,
- run `ollama serve`,
- run `ollama pull qwen2.5:7b`,
- rerun `RUN_DAILY_WITH_OLLAMA.bat`.

If scheduled task works manually but not at 08:00:

- verify the task is enabled,
- verify the Windows user is logged in or task settings allow running when appropriate,
- check Task Scheduler history,
- check `logs/daily_tracking_agent.log`.

## Failure Behavior

If sync validation fails, the app logs the failure and exits before reading Excel. If configured, it sends a Teams failure notification. If Ollama or Teams fails, the local rule-based report is still generated.
