# TDCC Helper Tool

This repository provides tools to assist shareholders with the TDCC electronic voting process, including automated voting and screenshot features(currently only support Edge browser).

---

- [TDCC Helper Tool](#tdcc-helper-tool)
  - [English Manual](#english-manual)
    - [Build Command](#build-command)
    - [Usage](#usage)
      - [1. rename\_tool](#1-rename_tool)
      - [2. TDCC\_helper\_tool](#2-tdcc_helper_tool)
    - [Screenshot File Format Selection (Screenshot Mode)](#screenshot-file-format-selection-screenshot-mode)
    - [Feedback, Suggestions, and Bug Reports](#feedback-suggestions-and-bug-reports)
    - [Contributing](#contributing)
    - [License and Development Notice](#license-and-development-notice)
    - [Environment Information](#environment-information)
  - [中文說明（繁體）](#中文說明繁體)
    - [建置指令](#建置指令)
    - [使用說明](#使用說明)
      - [1. rename\_tool](#1-rename_tool-1)
      - [2. TDCC\_helper\_tool](#2-tdcc_helper_tool-1)
    - [截圖檔案格式選擇（Screenshot Mode）](#截圖檔案格式選擇screenshot-mode)
    - [意見回饋、建議與問題回報](#意見回饋建議與問題回報)
    - [參與開發說明](#參與開發說明)
    - [授權與開發注意事項](#授權與開發注意事項)
    - [環境資訊](#環境資訊)


---

## English Manual

### Build Command

```
pyinstaller -F ./TDCC_helper_tool.py
pyinstaller -F ./rename_tool.py

we introduce github workflow to build the executable files for the tools(commit 0c3b30577), so you can get the executable files directly from "Actions" tab in this repository.
```

---

### Usage

#### 1. rename_tool

**How to use:**
- Double-click the executable or run the script with Python.

**What it does:**
- Moves and renames all PNG files from `./screenshots/{user_id}/*.png` to `./screenshots/all/*_{user_id}.png`.
- This helps consolidate screenshots from different shareholder IDs into a single folder, with filenames indicating their original ID.

---

#### 2. TDCC_helper_tool
This program assists shareholders in the TDCC voting process, including automated voting and screenshot features. It helps minority shareholders receive shareholder meeting souvenirs.
**Step-by-step usage:**

1. **Start the program**
   - Double-click the executable or run the script with Python.

2. **If unfinished screenshots are detected**
   - The tool will display:  
     `Last time have unfinished screenshot, do you want to continue? (Y/N) :`
   - If you enter `Y`, it will guide you through completing those screenshots first.

3. **Main menu**
   - The tool will display:
     ```
     (1) all accounts vote+take screenshot
     (2) take screenshot of specific stocks
     (3) exit
     please select:
     ```
   - Enter `1`, `2`, or `3`.

4. **If you select (1) all accounts vote + take screenshot**
   - The tool will check for existing settings. If not found or you choose to reconfigure, you will be prompted:
     - `please enter the run speed (default is 2):`  
       (Enter a number between 1~30; smaller is faster)
     - `please enter the shareholder ID(台灣的身分證字號), one ID per line, end with 'end' :`  
       (Enter each ID, then type `end` to finish)
     - `please enter the default vote option (accept/opposite/abstain):`  
       (Choose one: `accept`, `opposite`, or `abstain`)
     - For manual voting keywords:
       - `please enter the keyword to accept, one keyword per line, end with 'end' :`
       - `please enter the keyword to opposite, one keyword per line, end with 'end' :`
       - `please enter the keyword to abstain, one keyword per line, end with 'end' :`
     - After each section, you will be asked to confirm:
       - `do you want to save the setting?(y/n)?`
       - `do you want to use the above setting?(y/n)?`
   - For each shareholder ID:
     - The tool will automatically log in, vote according to your settings, and take screenshots for each stock.
     - All screenshots are saved in `./screenshots/{id}/`.
   - After all accounts are processed, the tool logs out and closes the browser.

5. **If you select (2) Take screenshot of specific stocks**
   - The tool will prompt:
     - `Please enter the ID number to take screenshots:(-1 to exit)`
     - `Please enter the stock ID to take screenshots, multiple stock IDs should be separated by ",":(-1 to exit)`
   - The tool will log in and take screenshots for the specified stocks.

6. **Exit**
   - Select (3) to exit the program.

**Notes:**
- You can modify voting content at any time; it will not affect your actual voting intent.
- The script is for assistance only and does not take responsibility for any consequences.

---

### Screenshot File Format Selection (Screenshot Mode)

During the initial setup or when reconfiguring, you will be prompted to select a screenshot file format (screenshot mode). This determines how your screenshots are organized and named.

**Step-by-step selection:**
1. When prompted:
   ```
   Choose screenshot file structure:
   1. Current structure (screenshots per user ID folder)
   2. All screenshots in one folder, filename {stock_id}_{stock_name}_{stock_account_id}.png
   3. All screenshots in one folder, filename {stock_id}_{stock_name}_{user_id}.png
   Please enter 1, 2, or 3:
   ```
2. Enter the number for your preferred mode and press Enter.
   - Mode 1: Each user ID has its own folder (default)
   - Mode 2: All screenshots in one folder, filename includes stock account ID
   - Mode 3: All screenshots in one folder, filename includes user ID
3. The tool will use this mode for all future screenshots until you change it again.

---

### Feedback, Suggestions, and Bug Reports

We highly welcome your feedback, opinions, suggestions, and bug reports! You can:
- Open an issue or start a discussion in this repository on GitHub
- Contact me directly (see my GitHub profile for contact information)
- Discuss in the Line community chat

Your input helps make this tool better for everyone.

---

### Contributing

Contributions are welcome! If you are a developer and want to help improve this project:
1. Fork this repository on GitHub
2. Create a new branch for your feature or fix
3. Commit your changes and push to your fork
4. Open a Pull Request (PR) to this repository

For a step-by-step guide, see: https://docs.github.com/en/get-started/quickstart/contributing-to-projects

---

### License and Development Notice

- Anyone is welcome to further develop or modify this program, **as long as**:
  1. There is **no direct or indirect commercial use** (unless you have my explicit permission).
  2. If you distribute a modified version elsewhere (without contributing back to this repository), you **must include a statement** that your version is based on this repository.

Thank you for respecting these terms and for supporting open-source collaboration!

---

### Environment Information

If you encounter issues running this program, here's environment versions. The following versions are known to work and recommended:

- **Python:** 3.13.3
- **PyInstaller:** 6.13.0
- **pip:** 25.1.1
- **selenium:** 4.32.0

You can use `pip` to install the following dependencies.

```shell
python3 -m pip install -r requirements.txt
```

---

## 中文說明（繁體）

### 建置指令

```
pyinstaller -F ./TDCC_helper_tool.py
pyinstaller -F ./rename_tool.py

我們在 commit 0c3b30577 中引入了 GitHub 工作流程來建置工具的可執行檔，您可以直接從本專案的 "Actions" 標籤頁下載可執行檔。
```

---

### 使用說明

#### 1. rename_tool

**使用方式：**
- 直接雙擊執行檔或用 Python 執行腳本。

**功能說明：**
- 將 `./screenshots/{user_id}/*.png` 目錄下所有 PNG 檔案，移動並重新命名到 `./screenshots/all/` 資料夾，檔名格式為 `*_{user_id}.png`。
- 方便將不同股東 ID 的截圖集中管理，並保留來源 ID 資訊於檔名。

---

#### 2. TDCC_helper_tool
此程式用於協助股東進行 TDCC 投票，包含自動投票及截圖功能。以幫助零股股東領取股東會紀念品
**操作步驟說明：**

1. **啟動程式**
   - 直接雙擊執行檔或用 Python 執行腳本。

2. **若偵測到上次未完成的截圖**
   - 程式會顯示：  
     `Last time have unfinished screenshot, do you want to continue? (Y/N) :`  
     （上次有未完成的截圖，是否繼續？輸入 Y 繼續）
   - 若輸入 `Y`，會先引導你完成這些截圖。

3. **主選單**
   - 程式會顯示：
     ```
     (1) all accounts vote+take screenshot（所有帳號自動投票並截圖）
     (2) take screenshot of specific stocks（指定股票截圖）
     (3) exit（離開）
     please select:（請選擇）
     ```
   - 輸入 `1`、`2` 或 `3`。

4. **選擇 (1) 所有帳號自動投票並截圖**
   - 程式會檢查設定，若無設定或選擇重新設定，會依序詢問：
     - `please enter the run speed (default is 2):`  
       投票速度（輸入 1~30，數字越小越快）
     - `please enter the shareholder ID(台灣的身分證字號), one ID per line, end with 'end' :`  
       股東身分證字號（每行一個，輸入 end 結束）
     - `please enter the default vote option (accept/opposite/abstain):`  
       預設投票方式（accept=贊成，opposite=反對，abstain=棄權）
     - 關鍵字設定（可選，依序輸入，每行一個，輸入 end 結束）：
       - `please enter the keyword to accept, one keyword per line, end with 'end' :`（贊成關鍵字）
       - `please enter the keyword to opposite, one keyword per line, end with 'end' :`（反對關鍵字）
       - `please enter the keyword to abstain, one keyword per line, end with 'end' :`（棄權關鍵字）
     - 設定完成後會請你確認：
       - `do you want to save the setting?(y/n)?`（是否儲存設定）
       - `do you want to use the above setting?(y/n)?`（是否使用上述設定）
   - 每個股東帳號會自動登入、依設定自動投票，並為每檔股票截圖。
   - 所有截圖會儲存於 `./screenshots/{id}/` 資料夾。
   - 全部完成後會自動登出並關閉瀏覽器。

5. **選擇 (2) 指定股票截圖**
   - 程式會詢問：
     - `Please enter the ID number to take screenshots:(-1 to exit)`  
       輸入股東身分證字號（-1 離開）
     - `Please enter the stock ID to take screenshots, multiple stock IDs should be separated by ",":(-1 to exit)`  
       輸入股票代號（多個用逗號分隔，如 2330,2317，(-1 離開)）
   - 程式會自動登入並為指定股票截圖。

6. **離開程式**
   - 選擇 (3) 離開。

**注意事項：**
- 投票內容可隨時修改，不影響實際投票意願。
- 本工具僅供輔助，使用造成的任何後果請自行負責。

---

### 截圖檔案格式選擇（Screenshot Mode）

首次設定或重新設定時，程式會詢問您選擇截圖檔案格式（screenshot mode），決定截圖的儲存方式與檔名。

**選擇步驟：**
1. 當程式詢問：
   ```
   Choose screenshot file structure:
   1. Current structure (screenshots per user ID folder)
   2. All screenshots in one folder, filename {stock_id}_{stock_name}_{stock_account_id}.png
   3. All screenshots in one folder, filename {stock_id}_{stock_name}_{user_id}.png
   Please enter 1, 2, or 3:
   ```
2. 輸入對應數字並按 Enter。
   - 模式1：每個股東ID一個資料夾（預設）
   - 模式2：所有截圖集中一個資料夾，檔名含股東帳號
   - 模式3：所有截圖集中一個資料夾，檔名含身分證字號
3. 之後所有截圖將依此模式儲存，除非重新設定。

---

### 意見回饋、建議與問題回報

非常歡迎您提供任何意見、建議或回報問題！您可以：
- 在本專案的 GitHub issue 或 discussion 區留言
- 直接聯絡我（請參考我的 GitHub 個人頁面聯絡方式）
- 在Line社群中討論

您的回饋將有助於讓這個工具變得更好。

---

### 參與開發說明

歡迎任何開發者參與本專案！如果您想貢獻程式碼：
1. 先 fork 本專案到您的 GitHub 帳號
2. 建立新分支進行開發或修正
3. commit 並 push 到您的 fork
4. 透過 Pull Request (PR) 回報到本專案

詳細教學可參考：https://docs.github.com/zh-tw/get-started/quickstart/contributing-to-projects

---

### 授權與開發注意事項

- 歡迎任何人進行二次開發或修改本程式，**但必須遵守以下條件**：
  1. 不得直接或間接用於商業用途（除非明確取得本人同意）。
  2. 若有其他分發（未回饋本專案），**必須明確標示**本程式是基於本專案開發。

感謝您的尊重與支持，也歡迎大家共同推動開源合作！

---
### 環境資訊
若您在執行程式時遇到問題，以下是已知可正常運作的環境版本：
- **Python:** 3.13.3
- **PyInstaller:** 6.13.0
- **pip:** 25.1.1
- **selenium:** 4.32.0
- 
你可以使用`pip`安裝這些依賴項：
```shell
python3 -m pip install -r requirements.txt
```