# TaskFlow - 專業委託接案平台 (TaskFlow Work Platform)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95%2B-009688)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-336791)
![License](https://img.shields.io/badge/License-MIT-green)

TaskFlow 是一個採用現代化「液態玻璃擬態 (Glassmorphism)」設計風格的接案媒合平台。專為接案者 (Contractors) 與委託人 (Clients) 打造，提供從專案發布、即時競標、即時通訊到完案評價的一站式解決方案。

## ✨ 主要功能 (Features)

### 🎨 極致 UI/UX 體驗
* **液態玻璃介面**：全站採用半透明磨砂玻璃風格，搭配動態背景動畫。
* **互動式儀表板**：直觀顯示專案狀態、統計數據與未讀訊息。
* **視覺化能力分析**：個人檔案頁面整合 **雷達圖 (Radar Chart)**，多維度展示接案者能力（品質、效率、溝通）。

### 🛠️ 核心業務邏輯
* **雙向角色系統**：支援「委託人」與「接案者」兩種角色切換。
* **完整接案流程**：發布需求 -> 接案報價 -> 選擇合作 -> 交付驗收 -> 雙向評價。
* **即時通訊系統**：專案專屬聊天室，支援已讀/未讀狀態追蹤。
* **檔案交付管理**：支援多版本檔案上傳與下載。

### 🔒 企業級架構與資安
* **環境變數管理**：敏感資訊 (Database URL, Secret Key) 完全分離，符合現代資安標準。
* **SQLAlchemy ORM**：採用 `JoinedLoad` 優化查詢效能，避免 N+1 問題。
* **安全性雜湊**：使用者密碼採用強雜湊演算法加密儲存。

## 🚀 快速開始 (Quick Start)

### 1. 環境需求
* Python 3.10+
* PostgreSQL 資料庫

### 2. 安裝依賴
```bash
git clone [https://github.com/your-username/work-platform-fastapi.git](https://github.com/your-username/work-platform-fastapi.git)
cd work-platform-fastapi
pip install -r requirements.txt
