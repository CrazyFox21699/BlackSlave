# Daily Tracking Agent

Tool local-first để đọc tracking Excel từ folder OneDrive local, tạo daily report ngắn và gửi vào Microsoft Teams qua Power Automate webhook.

Không dùng SharePoint login, Graph API, username/password hay cloud LLM.

## 1. Setup Folder

Khuyến nghị đặt project ở:

```text
D:\Tool_xam\BlackSlave\daily_tracking_agent
```

Nếu khác folder thì thay path tương ứng trong các lệnh bên dưới.

## 2. Cài Python Package

Double-click:

```text
SETUP_FIRST_TIME.bat
```

Hoặc chạy PowerShell:

```powershell
cd D:\Tool_xam\BlackSlave\daily_tracking_agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip check
```

`pip check` nên ra:

```text
No broken requirements found.
```

## 3. Sửa Đường Dẫn Trong config.yaml

Mở:

```text
D:\Tool_xam\BlackSlave\daily_tracking_agent\config.yaml
```

Sửa các dòng này:

```yaml
sync:
  folder_path: "C:/Users/HuyTQ136/.../02_Project_Plan"
  tracking_file: "TEN_FILE_TRACKING.xlsx"
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
```

Muốn mở nhanh config bằng Notepad:

```text
EDIT_CONFIG.bat
```

Lưu ý:

- Dùng dấu `/` trong YAML path.
- Không paste SharePoint URL.
- `folder_path` là folder local do OneDrive sync về máy.
- Máy common nên để:

```yaml
user:
  my_pic_names: []
```

## 4. Copy File Intake

Copy 2 file này vào folder OneDrive project nếu muốn Power Automate ghi dữ liệu vào đó:

```text
urgent_tasks.xlsx
tracking_commands.xlsx
```

`urgent_tasks.xlsx`:

```text
Sheet: UrgentTasks
Table: UrgentTasksTable
```

`tracking_commands.xlsx`:

```text
Sheet: Commands
Table: TrackingCommandsTable
```

## 5. Test Config

Double-click:

```text
TEST_CONFIG.bat
```

Nó sẽ in ra các PIC tool đọc được từ file tracking thật.

Nếu muốn chạy bằng PowerShell:

```powershell
python main.py --config config.yaml --list-pics --dry-run
```

## 6. Chạy Daily Report

Test không gửi Teams:

```text
TEST_DAILY_REPORT_NO_TEAMS.bat
```

Chạy thật, có gửi Teams nếu `teams.enabled: true`:

```text
RUN_DAILY_REPORT.bat
```

Mở folder report:

```text
OPEN_REPORTS_FOLDER.bat
```

Report sẽ tập trung vào:

- hôm nay mỗi người có bao nhiêu task,
- tổng effort hôm nay so với 8h,
- ai đang bị assign quá tải,
- task due/overdue,
- urgent/OT nếu có,
- data quality đưa xuống cuối.

## 7. Auto 08:00 Sáng

Double-click:

```text
REGISTER_DAILY_8H_TASK.bat
```

Nó tạo Windows Task Scheduler task:

```text
Daily Tracking Control Report
```

Muốn test ngay:

```text
Task Scheduler -> Daily Tracking Control Report -> Right click -> Run
```

## 8. Member Hỏi Nhanh Trong Ngày

Member nhắn trong Teams:

```text
check Lion
check Cat
check huytq136
report Tiger
```

Flow:

```text
Teams message
-> Power Automate ghi 1 row pending vào tracking_commands.xlsx
-> Máy common check mỗi 1 phút
-> Tool trả lời ngắn lên Teams
-> Tool mark row done/error
```

Register checker:

```text
REGISTER_COMMAND_INBOX_TASK.bat
```

Chạy thử 1 lần:

```text
RUN_COMMAND_INBOX.bat
```

Không có command pending thì script thoát nhanh, không đọc tracking sheet.

## 9. Urgent Task

Format nhắn Teams khuyến nghị:

```text
urgent|Cat|3|support customer issue ABC
urgent|Tiger|2|hotfix integration build
```

Power Automate ghi vào `urgent_tasks.xlsx`.

Khi muốn xem impact:

```text
RUN_URGENT_IMPACT.bat
```

Tool sẽ báo urgent work ảnh hưởng task nào và có cần OT không.

## 10. Power Automate Flow Gửi Message Lên Teams

Flow này nhận HTTP POST từ tool rồi post vào group chat/channel.

1. Vào `https://make.powerautomate.com`.
2. Create -> Instant cloud flow.
3. Trigger: `When an HTTP request is received`.
4. Paste JSON schema:

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

5. Add action:

```text
Microsoft Teams -> Post message in a chat or channel
```

6. Set:

```text
Post as: Flow bot
Post in: Group chat
Group chat: chọn group chat
Message: @{triggerBody()?['text']}
```

Nếu dùng channel:

```text
Post in: Channel
Team: chọn team
Channel: chọn channel
Message: @{triggerBody()?['text']}
```

Trong ô Message, nên bấm icon code/expression và nhập đúng:

```text
@{triggerBody()?['text']}
```

Xoá dòng HTML rác nếu có:

```html
<p class="editor-paragraph"><br></p>
```

7. Save flow.
8. Mở lại trigger và copy `HTTP POST URL`.

URL đúng thường có:

```text
/triggers/manual/paths/invoke
sig=
```

Không copy URL trên thanh địa chỉ browser.

Test bằng PowerShell:

```powershell
$url = "PASTE_HTTP_POST_URL_CO_SIG"
$body = @{ text = "Test Daily Tracking webhook" } | ConvertTo-Json
Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
```

Nếu lỗi:

```text
OAuth authorization scheme required
```

thì bạn copy sai URL. Phải dùng `HTTP POST URL` trong trigger, URL phải có `sig=`.

## 11. Power Automate Flow Member Hỏi Nhanh

Flow này ghi command vào `tracking_commands.xlsx`.

1. Trigger Teams: `When a new message is added in a chat or channel`.
2. Chọn group chat/channel.
3. Condition:

```text
Message starts with check
OR
Message starts with report
```

4. Nhánh Yes -> action:

```text
Excel Online (Business) -> Add a row into a table
```

5. Chọn:

```text
Location: OneDrive for Business
Document Library: OneDrive
File: tracking_commands.xlsx
Table: TrackingCommandsTable
```

6. Map column:

```text
ID           = concat('CMD-', formatDateTime(utcNow(),'yyyyMMdd-HHmmss'))
Date         = formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd')
Command      = message body/content
RequestedBy  = sender display name
Status       = pending
CreatedAt    = formatDateTime(convertTimeZone(utcNow(),'UTC','SE Asia Standard Time'),'yyyy-MM-dd HH:mm')
TeamsMessage = message body/content
```

## 12. Power Automate Flow Urgent

Flow này ghi urgent task vào `urgent_tasks.xlsx`.

1. Trigger Teams: `When a new message is added in a chat or channel`.
2. Condition:

```text
Message starts with urgent|
```

3. Nhánh Yes -> action:

```text
Excel Online (Business) -> Add a row into a table
File: urgent_tasks.xlsx
Table: UrgentTasksTable
```

4. Map column:

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

## 13. Khi File Tracking Đang Bị Mở

Tool không đọc trực tiếp file gốc. Luồng xử lý:

```text
1. Check folder OneDrive.
2. Check file tracking tồn tại.
3. Check lock file ~$...
4. Copy file tracking sang temp.
5. Nếu file bị lock, retry.
6. Nếu vẫn lock, dùng last-good snapshot.
```

Lần đầu nên chạy lúc Excel không bị lock để tạo snapshot.

## 14. Define Rule Report

Tool đang dùng rule-based. Muốn đổi cách đánh giá report thì sửa các file dưới đây.

### 14.1. Thế Nào Là Trễ

File:

```text
modules/rule_checker.py
```

Rule hiện tại:

```python
if EndDatePlan < today and CurrentProgress < 100:
    issue = "Overdue"

if EndDatePlan == today and CurrentProgress < 100:
    issue = "Due today not completed"
```

Nghĩa là:

- quá ngày plan end mà progress chưa 100% -> trễ,
- hôm nay là due date mà chưa 100% -> cần follow hôm nay.

Muốn nới rule, ví dụ chỉ xem là trễ nếu quá hạn hơn 1 ngày:

```python
if EndDatePlan < today - 1 day and CurrentProgress < 100:
```

Trong code thực tế dùng `pd.Timedelta(days=1)`.

### 14.2. Near Deadline

File:

```text
modules/rule_checker.py
```

Rule hiện tại:

```python
if 0 <= DaysToDue <= 2 and CurrentProgress < 50:
    issue = "Near deadline with low progress"
```

Muốn chỉ cảnh báo sát hơn:

```python
0 <= DaysToDue <= 1
```

Muốn cảnh báo sớm hơn:

```python
0 <= DaysToDue <= 3
```

Muốn progress dưới 70% mới cảnh báo:

```python
CurrentProgress < 70
```

### 14.3. Quá Tải Trong Ngày

File:

```text
config.yaml
modules/workload_analyzer.py
modules/report_builder.py
```

Ngưỡng mặc định:

```yaml
capacity:
  daily_mh: 8
  weekly_mh: 40
```

Nếu muốn ngày chỉ tính 7h productive:

```yaml
capacity:
  daily_mh: 7
```

Report sẽ báo `OVER` nếu effort hôm nay của PIC vượt `daily_mh`.

### 14.4. Nhiều Task Song Song

File:

```text
modules/workload_analyzer.py
```

Rule hiện tại:

```python
if ActiveTasks >= 5:
    issue = "Too many parallel tasks"
```

Nếu team bạn thấy 4 task/người đã quá nhiều:

```python
if ActiveTasks >= 4:
```

### 14.5. Estimate Quá Nhỏ / Quá Lớn

File:

```text
config.yaml
modules/estimate_analyzer.py
modules/rule_checker.py
```

Baseline nằm trong `config.yaml`:

```yaml
estimate_baseline:
  Code:
    min_mh: 4
    max_mh: 40
    keywords: ["code", "implementation", "implement", "feature"]
```

Nghĩa là task có keyword `code/implementation/...`:

- Est < 4h -> possible underestimate,
- Est > 40h -> possible overestimate / aggregated scope.

Muốn phù hợp project hơn thì sửa `min_mh`, `max_mh`, `keywords`.

### 14.6. Task Quá Lớn Nên Split

File:

```text
modules/rule_checker.py
```

Rule hiện tại:

```python
if Est >= 16:
    issue = "Task too large"

if Est >= 40:
    Severity = High
```

Nếu tracking của bạn thường dùng task lớn hơn, có thể đổi `16` thành `24`.

### 14.7. Data Quality Để Cuối Report

File:

```text
modules/report_builder.py
```

Các issue như:

```text
Missing PIC
Invalid planning date
Delta mismatch
```

đang được đưa xuống section:

```text
Data Quality Backlog
```

Nếu muốn ẩn bớt data quality khỏi Teams summary, chỉnh hàm:

```python
build_teams_summary()
```

và bỏ block:

```python
Data quality later
```

### 14.8. Thứ Tự Hiển Thị Report

File:

```text
modules/report_builder.py
```

Teams summary nằm ở:

```python
build_teams_summary()
```

Full `.md` nằm ở:

```python
_full_markdown()
```

Thứ tự hiện tại:

```text
Team load today
Today focus
PM load check
Delay
Urgent/OT
Data quality later
```

Muốn đổi thứ tự thì đổi list `lines` trong `build_teams_summary()`.

## 15. Chỉnh Report Ở Đâu

```text
modules/report_builder.py          Daily Teams summary + Markdown/Excel report
modules/query_engine.py            Câu trả lời check Lion/check Cat
modules/urgent_impact_analyzer.py  Urgent/OT impact
modules/rule_checker.py            Rule schedule/progress/data quality
modules/workload_analyzer.py       Workload >8h/>40h
modules/estimate_analyzer.py       Estimate sanity
```
