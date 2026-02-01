import pandas as pd
import numpy as np
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import io
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1MLUHCUmui1N9LHU28uINTOP0HEu6prQX776Tk4hxgaY/export?format=csv"

def fetch_data():
    try:
        logger.info("Fetching data from Google Sheets...")
        response = requests.get(SHEET_URL, timeout=10)
        response.raise_for_status()
        df = pd.read_csv(io.StringIO(response.text))
        # Standardize columns
        df.columns = [c.strip() for c in df.columns]
        df['Date'] = pd.to_datetime(df['Date'])
        # Sort and clean
        df = df.sort_values(['Symbol', 'Date']).dropna(subset=['Symbol', 'Close', 'Open', 'Volume'])
        logger.info(f"Fetched {len(df)} rows across {df['Symbol'].nunique()} symbols")
        return df
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        raise

def get_signals_for_row(row, hist_df):
    signals = []
    
    # 1. Aggressive Buyers/Sellers
    if row['AbsBody'] > 1.5 * row['AvgBody'] and row['Volume'] > 1.2 * row['AvgVol']:
        if row['Body'] > 0: signals.append("Aggressive Buyer")
        elif row['Body'] < 0: signals.append("Aggressive Seller")
            
    # 2. POI
    if not hist_df.empty:
        poi_idx = hist_df['Volume'].idxmax()
        poi_price = hist_df.loc[poi_idx, 'Close']
        if abs(row['Close'] - poi_price) / (poi_price if poi_price != 0 else 1) < 0.01:
            signals.append("Near POI")

    # 3. POR
    if row['AbsBody'] > 2 * row['Range_Std'] and row['Range_Std'] < 0.5 * row['Avg_Range_Std']:
        signals.append("Point of Release")

    # 4. Absorption
    if row['Volume'] > 1.5 * row['AvgVol'] and row['AbsBody'] < 0.3 * row['AvgBody']:
        signals.append("Sellers Absorption" if row['Body'] > 0 else "Buyers Absorption")
    
    if row['Volume'] > 1.2 * row['AvgVol']:
        if row['LowerShadow'] > 2 * row['AbsBody']: signals.append("Absorption (L-Shadow)")
        if row['UpperShadow'] > 2 * row['AbsBody']: signals.append("Absorption (U-Shadow)")

    return ", ".join(list(set(signals))) if signals else ""

def prepare_sdf(sdf):
    if len(sdf) < 20: return sdf
    sdf = sdf.copy()
    # Pre-calculate vectorized features
    sdf['Body'] = sdf['Close'] - sdf['Open']
    sdf['AbsBody'] = sdf['Body'].abs()
    sdf['AvgBody'] = sdf['AbsBody'].rolling(20).mean()
    sdf['AvgVol'] = sdf['Volume'].rolling(20).mean()
    sdf['Range_Std'] = sdf['Close'].rolling(10).std()
    sdf['Avg_Range_Std'] = sdf['Close'].rolling(50).std()
    sdf['LowerShadow'] = sdf[['Open', 'Close']].min(axis=1) - sdf['Low']
    sdf['UpperShadow'] = sdf['High'] - sdf[['Open', 'Close']].max(axis=1)
    return sdf.fillna(0)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/signals')
def get_latest_signals():
    try:
        df = fetch_data()
        results = []
        for symbol in df['Symbol'].unique():
            sdf = df[df['Symbol'] == symbol]
            if len(sdf) < 20: continue
            
            # Only process the last few rows for performance
            sdf_prep = prepare_sdf(sdf.tail(60)) # Last 60 bars for POI context
            latest_row = sdf_prep.iloc[-1]
            hist_context = sdf_prep.iloc[:-1]
            
            sig_str = get_signals_for_row(latest_row, hist_context)
            if sig_str:
                results.append({
                    "Symbol": symbol,
                    "Date": latest_row['Date'].strftime('%Y-%m-%d'),
                    "Close": float(latest_row['Close']),
                    "Volume": int(latest_row['Volume']),
                    "Signals": sig_str
                })
        return jsonify(results)
    except Exception as e:
        logger.error(f"API /signals error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/historical/<symbol>')
def get_historical(symbol):
    try:
        df = fetch_data()
        sdf = df[df['Symbol'] == symbol.upper()].reset_index(drop=True)
        if sdf.empty:
            return jsonify({"error": "Symbol not found"}), 404
        
        sdf_prep = prepare_sdf(sdf)
        history = []
        
        # Only start from where we have full rolling context (index 20)
        for i in range(20, len(sdf_prep)):
            row = sdf_prep.iloc[i]
            hist_context = sdf_prep.iloc[max(0, i-50):i]
            sig_str = get_signals_for_row(row, hist_context)
            
            history.append({
                "Date": row['Date'].strftime('%Y-%m-%d'),
                "Close": float(row['Close']),
                "Volume": int(row['Volume']),
                "Signals": sig_str
            })
            
        return jsonify(history)
    except Exception as e:
        logger.error(f"API /historical error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
