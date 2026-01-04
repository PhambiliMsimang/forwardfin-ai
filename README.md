# ForwardFin: AI-Powered JSE Trading Assistant

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-MVP-orange)

## 🚀 Overview
**ForwardFin** is a quantitative finance platform designed specifically for the **Johannesburg Stock Exchange (JSE)**. It leverages machine learning to solve a critical problem for retail investors: separating long-term **dividend yield accumulation** strategies from short-term **swing trading** volatility.

Unlike generic screeners, ForwardFin uses a decoupled microservices architecture to ingest live market data via the **Yahoo Finance API**, process it through a Scikit-Learn predictive model, and visualize actionable insights for the user.

## ⚡ Key Features

* **JSE Market Data Ingestion:** Real-time and historical data fetching for JSE-listed tickers using `yfinance`.
* **Smart Dividend Filter:** Automated calculation of yield-consistency scores to identify stable, high-yield ETFs and blue-chip stocks.
* **AI Swing Signal Detector:** A classification model (Scikit-Learn) that analyzes volatility markers (RSI, MACD, Bollinger Bands) to flag short-term entry/exit points.
* **Strategy Decoupling:** Distinct analytical pipelines for "Hold" vs. "Trade" portfolios to prevent strategy drift.

## 🏗️ Architecture

ForwardFin follows a modular architecture to ensure scalability and separation of concerns:

1.  **Data Service (Ingestion Layer):** Handles API rate limiting and raw data normalization from Yahoo Finance.
2.  **Analysis Engine (Compute Layer):**
    * *Dividend Module:* Calculates trailing yields and payout ratios.
    * *Volatility Module:* Computes technical indicators.
    * *ML Classifier:* Predicts short-term price direction probability.
3.  **Presentation Layer:** A clean dashboard interface for visualization (currently in development).

## 🛠️ Tech Stack

* **Language:** Python 3.10+
* **Data Processing:** Pandas, NumPy
* **Machine Learning:** Scikit-Learn (Random Forest Classifier)
* **Market Data:** Yahoo Finance API (`yfinance`)
* **Visualization:** Matplotlib / Plotly
* **Version Control:** Git

## 📦 Installation & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/PhambiliMsimang/forwardfin-ai.git
   cd ForwardFin