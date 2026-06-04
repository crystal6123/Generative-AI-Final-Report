# Thailand AI Travel Planner

泰國 AI 智慧旅遊規劃系統。使用者可以在 Streamlit 前端輸入目的地、天數、人數、預算與旅遊偏好，系統會透過 member A 的行程規劃 API、member C 的 SQLite 旅遊資料庫，以及 Gemini AI 產生每日行程、地圖路線、費用估算與聊天式旅遊建議。

## 專案特色

- 依照城市、天數、人數、預算與偏好產生泰國旅遊行程
- 支援 Bangkok、Chiang Mai、Phuket、Pattaya 四個目的地
- 使用 SQLite 資料庫查詢景點、餐廳、活動、費用與停留時間
- member A 提供 API，整合規則式排程、LLM 行程生成與 Reviewer 流程
- member B 提供 Streamlit 視覺化介面，包含行程卡片、互動地圖與 PDF 匯出
- 內建 AI 旅遊助手，可詢問附近美食、交通方式、景點介紹與預算分析
- 支援 Gemini 作為行程生成與聊天回覆模型

## 專案分工

```text
member_a/   行程生成核心、Multi-Agent 工作流、Gemini/Local LLM client、API JSON 格式轉換
member_b/   Streamlit 前端、表單輸入、行程視覺化、地圖、PDF 匯出、AI 聊天介面
member_c/   SQLite 資料庫、原始旅遊資料與資料整理 notebook
```

## 專案結構

```text
Generative-AI-Final-Report/
├── member_a/
│   ├── agents.py
│   ├── api.py
│   ├── gemini_client.py
│   ├── llm_planner.py
│   ├── models.py
│   ├── sqlite_data_gateway.py
│   └── workflow.py
│
├── member_b/
│   ├── app.py
│   ├── api_client.py
│   └── *.jpg / *.png
│
├── member_c/
│   ├── data/
│   │   └── 生成式DATA_FINAL.xlsx
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

- Python 3.10 或以上
- Windows PowerShell、VS Code Terminal 或其他可執行 Python 的終端機
- Gemini API Key

## 安裝方式

### 1. 建立虛擬環境

```powershell
python -m venv .venv
```

### 2. 啟動虛擬環境

```powershell
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 阻擋執行，先執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

再重新啟動虛擬環境。

### 3. 安裝套件

本專案需要安裝的 Python 套件如下：

| 套件 | 是否必要 | 用途 |
| --- | --- | --- |
| `streamlit` | 必要 | 啟動 member B 前端網頁 |
| `requests` | 必要 | member B 呼叫 member A API |
| `folium` | 必要 | 產生互動式行程地圖 |
| `streamlit-folium` | 必要 | 在 Streamlit 中顯示 Folium 地圖 |
| `google-generativeai` | 必要 | 呼叫 Gemini 產生行程與 AI 助手回覆 |
| `python-dotenv` | 建議 | 管理 `.env` 環境變數 |
| `pillow` | 建議 | 產生支援中文的圖片式 PDF |
| `fpdf2` | 建議 | PDF 匯出備援 |
| `qrcode` | 選用 | 若後續需要產生行程 QR Code 可使用 |

先安裝 `requirements.txt` 內的核心套件：

```powershell
python -m pip install -r requirements.txt
```

再安裝 PDF / 圖片匯出相關套件：

```powershell
python -m pip install pillow fpdf2 qrcode
```

也可以一次安裝全部套件：

```powershell
python -m pip install streamlit requests folium streamlit-folium google-generativeai python-dotenv pillow fpdf2 qrcode
```

## Gemini 設定

在專案根目錄建立 `.env`：

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

`.env` 含有 API Key，請不要上傳到 GitHub。

目前 member B 前端送出行程時會使用：

```json
{
  "use_llm": true,
  "llm_provider": "gemini"
}
```

因此若沒有設定 `GEMINI_API_KEY`，行程生成或 AI 助手可能會無法回覆。

## 執行方式

本系統需要開兩個 Terminal。

### Terminal 1：啟動 member A API

```powershell
cd C:\github\Generative-AI-Final-Report
.\.venv\Scripts\Activate.ps1
python run_member_a_api.py
```

成功後會看到：

```text
成員 A API 已啟動：http://127.0.0.1:8765/member-a/plan
AI 聊天 API：http://127.0.0.1:8765/member-a/chat
健康檢查：http://127.0.0.1:8765/health
```

這個 Terminal 需要保持開啟。

### Terminal 2：啟動 member B Streamlit 前端

```powershell
cd C:\github\Generative-AI-Final-Report
.\.venv\Scripts\Activate.ps1
streamlit run member_b/app.py
```

啟動後瀏覽器會開啟 Streamlit 網頁。若沒有自動開啟，可到終端機顯示的 local URL，例如：

```text
http://localhost:8501
```

## 使用流程

1. 選擇目的地：Bangkok、Chiang Mai、Phuket 或 Pattaya
2. 調整天數、人數與預算
3. 選擇旅行偏好，例如文化古蹟、在地美食、夜市、海島沙灘等
4. 按下「產生 AI 行程」
5. 系統呼叫 member A API，讀取 member C SQLite 資料庫並產生行程
6. 前端顯示每日行程、景點費用、互動地圖與總預算
7. 可使用右側 AI 助手詢問：
   - 推薦附近美食
   - 交通方式建議
   - 景點詳細介紹
   - 預算分析
8. 可下載 PDF 行程檔

## API 端點

member A API 預設在 `127.0.0.1:8765`。

```text
GET  /health
POST /member-a/plan
POST /member-a/chat
```

### `/member-a/plan`

用於產生旅遊行程。主要 payload 欄位：

```json
{
  "days": 4,
  "nights": 3,
  "people": 2,
  "budget_amount": 20000,
  "budget_currency": "TWD",
  "cities": ["Chiang Mai"],
  "preferences": ["culture", "local_food"],
  "daily_start_time": "10:00",
  "daily_end_time": "22:00",
  "use_llm": true,
  "llm_provider": "gemini"
}
```

### `/member-a/chat`

用於 AI 旅遊助手聊天。主要 payload 欄位：

```json
{
  "message": "請推薦目前行程附近的在地美食",
  "history": [],
  "current_itinerary": {}
}
```

## 資料庫

主要資料庫位置：

```text
member_c/database/thailand_trip_full.db
```

若此路徑不存在，程式會在專案資料夾下搜尋：

```text
**/thailand_trip_full.db
```

## Demo / 測試腳本

可單獨測試 member A 行程生成：

```powershell
python run_member_a_sqlite_demo.py
```

使用 Gemini 測試：

```powershell
python run_member_a_gemini_demo.py
```

使用 local / Ollama-compatible LLM 測試：

```powershell
python run_member_a_local_llm_demo.py
```

驗證偏好組合：

```powershell
python validate_all_preferences.py
```

## 常見問題

### 1. Streamlit 顯示 API 連線失敗

可能錯誤：

```text
Failed to establish a new connection: [WinError 10061]
```

代表 member A API 尚未啟動。請先執行：

```powershell
python run_member_a_api.py
```

### 2. 找不到 `GEMINI_API_KEY`

請確認專案根目錄有 `.env`，且內容包含：

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

修改 `.env` 後需要重啟 `run_member_a_api.py`。

### 3. 找不到 `thailand_trip_full.db`

請確認資料庫存在：

```text
member_c/database/thailand_trip_full.db
```

### 4. PowerShell 無法啟動虛擬環境

執行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

再執行：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 5. AI 回覆或行程生成仍是舊版本

若有修改 `member_a/` 或 `run_member_a_api.py`，需要重啟 member A API；若修改 `member_b/app.py`，Streamlit 通常會自動重新載入。

## 注意事項

- AI 產生的營業時間、票價與交通費可能需要再次確認
- `.env`、API Key 與個人憑證不應提交到版本控制
- Streamlit 前端與 member A API 需要同時啟動才能完整使用
