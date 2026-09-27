# 🐲 dragonpilot (Custom Fork)

> 🤖 本專案客製化功能與系統架構全程使用 **Gemini 3.8 Flash** 協同開發。

本專案為基於 openpilot / dragonpilot (`v0.11.1`) 的客製化分支，專為 Comma 3 / 3X 裝置設計，重點針對實際駕駛環境進行了方向盤手動與 GPS 智慧定位、繁體中文多國語言在地化、字型點陣圖修復與介面穩定性強化。

---

## 📦 安裝步驟 (Installation Guide)

本分支專為 **Comma 3** 與 **Comma 3X** 裝置設計。

---

### 方法一：Comma 裝置螢幕直接安裝（最推薦、最簡單）

若裝置剛重灌還原（AGNOS Setup Wizard）或在軟體設定中點擊「解除安裝軟體」後重新安裝：

1. 在開機設定畫面點選 **「自訂軟體安裝 (Custom Software)」**。
2. 在網址欄位直接輸入以下任一網址即可自動下載安裝：
   * **簡易格式（官方推薦）**：
     ```text
     timtai1/0.11.1
     ```
   * **完整 URL 格式**：
     ```text
     https://installer.comma.ai/timtai1/0.11.1
     ```
3. 點擊確認後，裝置即會自動連線至 `github.com/timtai1/openpilot` 下載 `0.11.1` 分支，完成後自動編譯啟動！

---

### 方法二：透過 SSH 指令安裝（進階 / 除錯）

#### 1. 全新安裝 (Fresh Install via SSH)
若要清除既有軟體並乾淨安裝本專案：
```bash
# 1. SSH 連線進入 Comma 裝置
ssh comma@<你的裝置IP>

# 2. 清除舊目錄並下載本專案分支
cd /data
rm -rf openpilot
git clone -b 0.11.1 --depth 1 https://github.com/timtai1/openpilot.git openpilot

# 3. 重新開機以編譯載入
reboot
```

#### 2. 既有系統直接切換分支 (In-Place Branch Switch)
若裝置上已有正常運作的 openpilot / dragonpilot 目錄，想直接切換至本專案：
```bash
cd /data/openpilot
git remote set-url origin https://github.com/timtai1/openpilot.git
git fetch origin 0.11.1
git checkout -B 0.11.1 origin/0.11.1
reboot
```

---

## 🚀 本專案客製功能與更新重點

### 1. 🛰️ 方向盤左右位置：首次 GPS 離線國家自動判斷 ＋ 手動自訂永久鎖定（重點置頂）
* **首次啟用 GPS 離線判定國家**：
  * 當 Comma 剛安裝啟用、且使用者**尚未手動設定過**時，開機首次取得 GPS 衛星定位（`hasFix`）後，立即透過輕量離線地理邊界比對所在國家。
  * 若身處**右駕國家**（如日本、香港、澳門、英國、愛爾蘭、澳洲、紐西蘭、新加坡、泰國、馬來西亞、印尼、南非等），系統**自動將方向盤預設為右駕（`Right`）**。
  * 若身處**左駕國家**（如台灣、美國、加拿大、歐洲大陸、中國等），系統**自動預設為左駕（`Left`）**。
  * 100% 本地離線運算，無需任何連網或 SIM 卡，無隱私外洩或離線失效風險。
* **使用者手動修改後永久鎖定**：
  * 只要使用者在螢幕 dp 選單手動點擊切換過（選了 `Left` 或 `Right`），系統立即寫入永久標記（`dp_dev_wheel_position_manually_set = True`）。
  * **從此 GPS 永久不再干預**，無論跨國駕駛、經過隧道或 GPS 訊號漂移，都 100% 以使用者的手動選擇為最高準則！
* **徹底移除動態誤判**：
  * 原版 `policy.py` 透過車內駕駛鏡頭持續動態猜測左右駕的統計演算法已被徹底拔除，駕駛監控狀態不再因夜間逆光、駕駛坐姿或視角造成判定跳動。

### 2. 🎡 方向盤手動選單開關 (Wheel on Left or Right?)
* **自訂設定項目**：
  * 於裝置端 dp 設定選單最後一項，新增「方向盤在左或在右？（Wheel on Left or Right?）」開關。
  * 提供 `Left` 與 `Right` 切換（預設為 `Left`）。
  * 說明：*Wheel on left, such as US, TW. Wheel on right like HK, JP.*
  * 設定永久儲存（`PERSISTENT`），開機重啟均維持設定。

### 3. 🍃 縱向加速與煞車舒緩優化 (Gentle Acceleration & Gentle Braking)
* **溫和加速選單 (Gentle Acceleration)**：
  * 於 dp 縱向控制 (Longitudinal) 選單新增「溫和加速」設定。
  * 提供六段全速域最大加速力道倍數：`0.5x`、`0.6x`、`0.7x`、`0.8x`、`0.9x`、`1.0x`（預設為 **`0.5x`**）。
  * **起步與行駛全速域適用**：解決不只 0 km/h 起步推力過猛，更徹底解決行進間前車變道切離或加速遠離時，原廠演算法急欲追趕目標時速而「猛踩油門、暴衝拉轉」的痛點。
  * **按比例全車種通用**：將全速域加速度上限曲線與 MPC 虛擬巡航目標加速度同步乘上設定倍數（例如 0.5x 下，0 km/h 上限為 $0.80\text{ m/s}^2$、36 km/h 為 $0.60\text{ m/s}^2$、90 km/h 為 $0.40\text{ m/s}^2$），油電車、電車或燃油車皆能呈現細膩沉穩的老司機加速體感。
  * 修復字型單位顯示為 `?` 的問題。
* **溫和煞車選單 (Gentle Braking)**：
  * 位於「溫和加速」正下方，新增「溫和煞車」選單項目。
  * 提供三段提前煞車倍數距離：`1.5x`、`2.0x`、`2.5x`（預設為 **`2.0x`**）。
  * 解決接近慢速前車或前方等紅燈車陣時「快貼近才急煞」的痛點；依選定倍數提前平順收油與減速，減速度力道依倍數成比例舒緩減弱（約 `1.0 ~ 1.67 m/s^2`，預設 2.0x 為 ~`1.25 m/s^2`，原廠為急踩等級的 `2.5 m/s^2`）。
  * **兼顧極致安全性**：完全不影響 AEB、前向碰撞預警（FCW）或緊急閃避煞車；當前車急煞時，底層 MPC 與安全約束依然維持完整最大煞車制動力（可達 `-3.5 ~ -4.0 m/s^2`）。

### 4. 🇹🇼 完整繁體中文在地化與多語系系統支援
* **翻譯引擎重構**：
  * 重寫 `multilang.py`，支援直接解析與載入 `dragonpilot_{lang}.po` 語言檔，無需預編譯為二進位 `.mo`。
* **100% 繁體中文支援**：
  * 完整補齊 `dragonpilot_zh-CHT.po` 中所有 dp 設定字串的在地化翻譯。
  * 徹底解決系統語言切換至繁體中文時，dp 設定選單依然顯示英文的問題。

### 5. 🔤 點陣字型圖集烘焙 (解決問號 `?` 缺字問題)
* **字型處理工具升級**：
  * 更新 `selfdrive/assets/fonts/process.py`，能自動抽取所有翻譯檔中的漢字字集。
* **CJK Bitmap Font Atlas 重新烘焙**：
  * 在裝置端使用 Raylib 重新烘焙高解析度點陣字型圖檔（`OpFont-*.fnt` / `OpFont-*.png`）。
  * 徹底解決介面上中文繁體字元顯示為問號 `?` 的缺字渲染問題。

### 6. ⚡ 介面穩定性修復 (UI Crash Fix)
* **防止選單崩潰**：
  * 修復 `dragonpilot.py` 在解析布林參數時引發 `ValueError`（`int("False")`），導致點擊進入 dp 選單閃退（畫面跳回逗號 Logo）的問題。

### 7. 🔄 快速部署與熱重載工作流 (Fast Hot Reload)
* **免等 10-15 分鐘重新開機**：
  * 針對 Python 程式碼、翻譯檔與字型圖檔更新，建立快速熱重載流程。
  * 透過背景重新啟動 `selfdrive.ui`，在 1 秒內無縫套用最新變更。

### 8. 🤖 AI 協同開發 (AI-Assisted Development)
* 本專案包含離線 GPS 國家地理邊界演算法、方向盤設定永久鎖定、全速域溫和加速線性縮放、提前兩倍距離平順煞車運動學推導、純 Python 翻譯檔解析引擎、Raylib 點陣字型圖集烘焙工具鏈，以及裝置端熱重載與即時除錯工作流，全程使用 **Gemini 3.8 Flash** 進行對話式引導開發與實作驗證。