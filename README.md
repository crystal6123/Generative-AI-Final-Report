# Generative AI Final Report - Thailand AI Travel Planner

本專案是一個泰國旅遊 AI Agent 行程規劃系統，使用者可以輸入旅遊天數、人數、預算與偏好，系統會透過 Multi-Agent 流程產生旅遊行程，並結合 SQLite 資料庫進行景點、餐廳、交通與費用查詢。

## 專案分工

```text
member_a/   Multi-Agent 流程、行程產生、預算檢查、Reviewer Agent
member_b/林珮瑜   Streamlit 前端介面、API 串接、結果顯示
member_c/   SQLite 資料庫、資料整理、查詢工具、RAG / MCP 支援
```

## 專案結構

```text
Generative-AI-Final-Report/
├── member_a/
│   ├── agents.py
│   ├── api.py
│   ├── workflow.py
│   ├── models.py
│   ├── sqlite_data_gateway.py
│   └── ...
│
├── member_b/
│   ├── app.py
│   ├── api_client.py
│   └── ui_components.py
│
├── member_c/
│   ├── data/
│   ├── database/
│   │   └── thailand_trip_full.db
│   └── notebooks/
│
├── run_member_a_api.py
├── run_member_a_sqlite_demo.py
├── run_member_a_gemini_demo.py
├── run_member_a_local_llm_demo.py
├── validate_all_preferences.py
├── requirements.txt
└── README.md
```

## 環境需求

建議使用：

```text
Python 3.10 或以上
Windows PowerShell / VS Code Terminal
```

## 安裝方式

### 1. 建立虛擬環境

在專案根目錄執行：

```powershell
python -m venv .venv
```

### 2. 啟動虛擬環境

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 不允許執行，先執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

再重新啟動：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. 安裝套件

```powershell
python -m pip install -r requirements.txt
```

如果沒有 `requirements.txt`，可以先手動安裝：

```powershell
python -m pip install streamlit requests pandas openpyxl numpy google-generativeai python-dotenv
```



## 執行方式

本系統需要開兩個 Terminal。

---

### Terminal 1：啟動 member A API

```powershell
cd C:\github\Generative-AI-Final-Report
.\.venv\Scripts\Activate.ps1
python run_member_a_api.py
```

成功後會看到：

```text
成員 A API 已啟動：http://127.0.0.1:8765/member-a/plan
停止服務請按 Ctrl+C
```

這個 Terminal 不要關閉。

---

### Terminal 2：啟動 member B Streamlit 前端

```powershell
cd C:\github\Generative-AI-Final-Report
.\.venv\Scripts\Activate.ps1
streamlit run member_b/app.py
```

啟動後瀏覽器會開啟 Streamlit 網頁。

## 使用方式

1. 在網頁輸入旅遊天數
2. 輸入人數
3. 輸入總預算
4. 選擇旅遊城市
5. 選擇旅遊偏好
6. 按下「生成行程」
7. 系統會呼叫 member A API，並從 member C 的 SQLite 資料庫查詢資料
8. 前端顯示每日行程、費用估算與 Agent 執行紀錄


```

## Gemini / LLM 設定

如果要使用 Gemini，需要在專案根目錄建立 `.env`：

```env
GEMINI_API_KEY=你的 Gemini API Key
GEMINI_MODEL=gemini-2.5-flash
```

`.env` 不要上傳到 GitHub。

可以提供 `.env.example`：

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```


## 常見問題

### 1. B 顯示 API 連線失敗

錯誤類似：

```text
Failed to establish a new connection: [WinError 10061]
```

代表 member A API 沒有啟動。

請先在 Terminal 1 執行：

```powershell
python run_member_a_api.py
```

確認看到：

```text
成員 A API 已啟動：http://127.0.0.1:8765/member-a/plan
```

再執行 Streamlit。

### 2. 找不到 thailand_trip_full.db

請確認資料庫放在：

```text
member_c/database/thailand_trip_full.db
```

或至少放在專案資料夾底下，因為程式會自動搜尋：

```text
**/thailand_trip_full.db
```

### 3. PowerShell 無法啟動虛擬環境

執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

再執行：

```powershell
.\.venv\Scripts\Activate.ps1
```

