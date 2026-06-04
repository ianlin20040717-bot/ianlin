# ⏳ Taiwan Stock Time Machine (台股時光機)

一個基於 Python 與 Streamlit 打造的台股盤後「逐筆行情重播系統」。旨在完美還原盤中每一筆成交明細與走勢型態，協助量化交易者、短線客在盤後精準復盤，捕捉主力洗盤與敲單的蛛絲馬跡。

## 🚀 功能特點
- **完美逐筆還原**：對接 FinMind API 獲取 `TaiwanStockPriceTick` 級別精細數據。
- **動態走勢重播**：即時動態渲染動態 K 線與分時走勢，流暢還原當日盤勢。
- **速度自由掌控**：支援滑桿即時調整重播間隔時間（最快可達 0.01 秒/筆）。
- **夜間作戰裝甲**：內建防呆與偵錯機制，自動防範半夜證交所/API 數據庫結算維護時的格式突變。

## 🛠️ 快速安裝與啟動

### 1. 複製本專案
```bash
git clone [https://github.com/你的帳號名稱/taiwan-stock-time-machine.git](https://github.com/你的帳號名稱/taiwan-stock-time-machine.git)
cd taiwan-stock-time-machine
