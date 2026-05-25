# Daily Tracking Agent

Tool local-first để đọc tracking Excel đã sync bằng OneDrive, tạo report ngắn mỗi sáng, và trả lời nhanh khi member hỏi trong Teams.

## Mục Tiêu

- 08:00 sáng: tự đọc tracking sheet và gửi summary ngắn lên Teams.
- Trong ngày: member nhắn `check Lion` trong Teams, máy common tự trả lời Lion hôm nay làm gì.
- Có urgent task: ghi vào `urgent_tasks.xlsx`, tool báo ảnh hưởng deadline/OT.
- Không login SharePoint, không dùng Graph API, không lưu username/password.
- Không sửa file tracking gốc. Tool luôn copy Excel sang `temp/` rồi mới analyze.
- Ollama không bắt buộc. Khuyến nghị máy common chạy `--no-ollama` cho nhẹ.

## File Quan Trọng

```text
config.yaml
requirements.txt
main.py
urgent_tasks.xlsx
tracking_commands.xlsx
RUN_DAILY_WITH_OLLAMA.bat
RUN_URGENT_IMPACT.bat
RUN_COMMAND_INBOX.bat
scripts/register_windows_task.ps1
scripts/register_command_inbox_task.ps1
```

## Setup Nhanh Trên Máy Công Ty

Giả sử code nằm ở:

```text
D:\Tool_xam\BlackSlave\daily_tracking_agent
```

Mở PowerShell:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
python --version
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip check
```

Nếu thấy:

```text
No broken requirements found.
```

là Python package OK.

## Config Cần Sửa

Mở:

```text
D:\Tool_xam\BlackSlave\daily_tracking_agent\config.yaml
```

Sửa các phần này:

```yaml
sync:
  folder_path: "C:/Users/HuyTQ136/.../02_Project_Plan"
  tracking_file: "TEN_FILE_TRACKING.xlsx"
  allow_snapshot_when_locked: true
  snapshot_folder: "D:/Tool_xam/BlackSlave/daily_tracking_agent/temp/source_snapshots"

report:
  output_folder: "C:/Users/HuyTQ136/.../02_Project_Plan/Reports"

urgent:
  external_file: "C:/Users/HuyTQ136/.../02_Project_Plan/urgent_tasks.xlsx"

command_inbox:
  file: "C:/Users/HuyTQ136/.../02_Project_Plan/tracking_commands.xlsx"

teams:
  enabled: true
  webhook_url: "PASTE_POWER_AUTOMATE_HTTP_POST_URL_CO_SIG"

ollama:
  enabled: false
```

Lưu ý:

- Dùng dấu `/` trong YAML path.
- Không paste SharePoint URL. Chỉ dùng folder local OneDrive.
- `ollama.enabled: false` là setup khuyến nghị cho máy common.

## File Excel Intake

Copy 2 file này vào folder OneDrive project nếu muốn Power Automate ghi vào đó:

```text
urgent_tasks.xlsx
tracking_commands.xlsx
```

`urgent_tasks.xlsx` cần có:

```text
Sheet: UrgentTasks
Table: UrgentTasksTable
```

`tracking_commands.xlsx` cần có:

```text
Sheet: Commands
Table: TrackingCommandsTable
```

## Test Tool

Test không gửi Teams:

```powershell
python main.py --config config.yaml --dry-run --no-ollama
```

Test gửi Teams thật:

```powershell
python main.py --config config.yaml --no-ollama
```

Test hỏi nhanh:

```powershell
python main.py --config config.yaml --ask "check Lion" --no-ollama
```

Xem tool đang đọc được PIC nào trong file thật:

```powershell
python main.py --config config.yaml --list-pics --dry-run --no-ollama
```

Test command inbox:

```powershell
python main.py --config config.yaml --process-command-inbox --dry-run --no-ollama
```

## Auto 08:00 Sáng

Register Windows Task Scheduler:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_windows_task.ps1 -StartTime "08:00"
```

Sau đó mở Task Scheduler, tìm:

```text
Daily Tracking Control Report
```

Right click -> `Run` để test.

## Teams Command Trong Ngày

Member nhắn trong Teams:

```text
check Lion
report Cat
Tiger hôm nay làm gì
check Lion Cat
```

Luồng chạy:

```text
Teams message
-> Power Automate ghi 1 row vào tracking_commands.xlsx
-> Máy common check mỗi 1 phút
-> Nếu có command pending thì tool analyze tracking
-> Tool gửi câu trả lời ngắn lên Teams
-> Tool mark command done/error
```

Register command inbox checker:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
powershell.exe -ExecutionPolicy Bypass -File .\scripts\register_command_inbox_task.ps1 -StartTime "07:30" -EndTime "19:30" -IntervalMinutes 1
```

Không có command pending thì script thoát nhanh, không đọc tracking sheet, không gọi Ollama.

## Power Automate 1: Gửi Message Lên Teams

Flow này dùng để tool gửi report/answer vào group chat.

### Bước 1

Vào:

```text
https://make.powerautomate.com
```

Create -> Instant cloud flow.

Trigger chọn:

```text
When an HTTP request is received
```

Nếu flow báo premium thì dùng account công ty có premium.

### Bước 2

Trong trigger, paste JSON schema:

```json
{
  "type": "object",
  "properties": {
    "text": {
      "type": "string"
    }
  },
  "required": ["text"]
}
```

### Bước 3

Bấm `+ New step`.

Chọn:

```text
Microsoft Teams -> Post message in a chat or channel
```

Set như sau:

```text
Post as: Flow bot
Post in: Group chat
Group chat: chọn group chat của team
Message: @{triggerBody()?['text']}
```

Nếu gửi vào channel thì chọn:

```text
Post in: Channel
Team: chọn team
Channel: chọn channel
Message: @{triggerBody()?['text']}
```

Trong ô Message, nếu đang ở editor thường thì bấm icon code/expression rồi nhập:

```text
@{triggerBody()?['text']}
```

Không để lại dòng HTML rác kiểu:

```html
<p class="editor-paragraph"><br></p>
```

### Bước 4

Save flow.

Bấm lại trigger `When an HTTP request is received`.

Copy field:

```text
HTTP POST URL
```

URL đúng thường có:

```text
/triggers/manual/paths/invoke
sig=
```

Không copy URL trên thanh địa chỉ browser.

### Bước 5: Test bằng PowerShell

```powershell
$url = "PASTE_HTTP_POST_URL_CO_SIG"

$body = @{
  text = "Test Daily Tracking webhook"
} | ConvertTo-Json

Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
```

Nếu Teams group nhận được message, paste URL đó vào:

```yaml
teams:
  enabled: true
  webhook_url: "PASTE_HTTP_POST_URL_CO_SIG"
```

Nếu lỗi:

```text
OAuth authorization scheme required
```

nghĩa là copy sai URL. Phải copy `HTTP POST URL` trong trigger, URL phải có `sig=`.

## Power Automate 2: Member Hỏi Nhanh

Flow này ghi command Teams vào `tracking_commands.xlsx`.

### Bước 1

Create flow mới.

Trigger chọn Teams trigger mà tenant cho phép, ví dụ:

```text
When a new message is added in a chat or channel
```

Chọn group chat/channel đang dùng.

### Bước 2

Thêm Condition:

```text
Message starts with check
OR
Message starts with report
```

Nếu muốn đơn giản, chỉ dùng format:

```text
check Lion
check Cat
report Tiger
```

### Bước 3

Trong nhánh `Yes`, add action:

```text
Excel Online (Business) -> Add a row into a table
```

Chọn:

```text
Location: OneDrive for Business
Document Library: OneDrive
File: tracking_commands.xlsx
Table: TrackingCommandsTable
```

Map column:

```text
ID           = concat('CMD-', formatDateTime(utcNow(),'yyyyMMdd-HHmmss'))
Date         = formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd')
Command      = message body/content
RequestedBy  = sender display name
Status       = pending
CreatedAt    = formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd HH:mm')
TeamsMessage = message body/content
```

Máy common sẽ đọc row `Status = pending`, trả lời xong thì đổi thành `done`.

## Power Automate 3: Urgent Task

Flow này ghi urgent task vào `urgent_tasks.xlsx`.

Member nhắn:

```text
urgent|Cat|3|support customer issue ABC
urgent|Tiger|2|hotfix integration build
```

Nên dùng format có dấu `|` cho dễ parse.

Flow:

```text
Trigger: new Teams message
Condition: message starts with urgent|
Action: Excel Online (Business) -> Add a row into a table
File: urgent_tasks.xlsx
Table: UrgentTasksTable
```

Map column:

```text
ID         = concat('U-', formatDateTime(utcNow(),'yyyyMMdd-HHmmss'))
Date       = formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd')
PIC        = phần thứ 2 sau khi split bằng |
EstimateMH = phần thứ 3 sau khi split bằng |
Item       = phần thứ 4 sau khi split bằng |
Due        = today
Reason     = message body/content
Status     = open
Source     = teams
CreatedAt  = formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd HH:mm')
```

Khi muốn check impact:

```powershell
python main.py --config config.yaml --urgent-impact-only --no-ollama
```

Hoặc double-click:

```text
RUN_URGENT_IMPACT.bat
```

## Ollama Có Cần Không?

Không bắt buộc.

Khuyến nghị máy common:

```yaml
ollama:
  enabled: false
```

Lý do:

- Rule-based đủ cho daily control.
- Command inbox chạy mỗi phút nên không nên gọi LLM.
- Không có pending command thì script thoát nhanh.
- Ollama có thể tốn RAM/CPU nếu chạy model lớn.

Chỉ bật Ollama khi cần review sâu:

```powershell
python main.py --config config.yaml --with-ollama
```

## Khi Excel Tracking Đang Bị Người Khác Mở

Tool xử lý như sau:

```text
1. Check folder OneDrive.
2. Check file tracking tồn tại.
3. Check lock file ~$...
4. Copy source Excel sang temp.
5. Nếu file bị lock, retry.
6. Nếu vẫn bị lock, dùng last-good snapshot.
```

Snapshot nằm ở:

```text
temp/source_snapshots
```

Lần chạy đầu tiên nên chạy lúc file Excel không bị lock để tạo snapshot đầu tiên.

## Command Hay Dùng

Daily report, không gửi Teams:

```powershell
python main.py --config config.yaml --dry-run --no-ollama
```

Daily report, gửi Teams:

```powershell
python main.py --config config.yaml --no-ollama
```

Hỏi nhanh 1 member:

```powershell
python main.py --config config.yaml --ask "check Lion" --no-ollama
```

Nếu tên bạn trong cột PIC là `huytq136`, config cần có:

```yaml
user:
  my_pic_names:
    - "huytq136"
    - "HuyTQ136"
```

Xử lý command inbox:

```powershell
python main.py --config config.yaml --process-command-inbox --no-ollama
```

Urgent impact:

```powershell
python main.py --config config.yaml --urgent-impact-only --no-ollama
```

## Chỉnh Report Ở Đâu

Teams summary và full report:

```text
modules/report_builder.py
```

Member quick answer:

```text
modules/query_engine.py
```

Urgent impact:

```text
modules/urgent_impact_analyzer.py
```

Rule check:

```text
modules/rule_checker.py
modules/workload_analyzer.py
modules/estimate_analyzer.py
```

Ollama prompt:

```text
modules/ollama_reviewer.py
```
