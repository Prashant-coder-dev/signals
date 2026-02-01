import pandas as pd
import numpy as np
from flask import Flask, jsonify, render_template
from flask_cors import CORS
import requests
import io

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1MLUHCUmui1N9LHU28uINTOP0HEu6prQX776Tk4hxgaY/export?format=csv"

def fetch_data():
    try:
        response = requests.get(SHEET_URL)
        df = pd.read_csv(io.StringIO(response.text))
        # Standardize columns
        df.columns = [c.strip() for c in df.columns]
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(['Symbol', 'Date'])
        return df
    except Exception as e:
        print(f"Error fetching data: {e}")
        raise

def detect_signals_history(sdf):
    if len(sdf) < 20: return []
    
    # Calculations
    sdf['Body'] = sdf['Close'] - sdf['Open']
    sdf['AbsBody'] = sdf['Body'].abs()
    sdf['Range'] = sdf['High'] - sdf['Low']
    sdf['AvgBody'] = sdf['AbsBody'].rolling(20).mean()
    sdf['AvgVol'] = sdf['Volume'].rolling(20).mean()
    
    # Fill NaNs to avoid issues
    sdf = sdf.fillna(0)
    
    all_signals = []
    
    for i in range(20, len(sdf)):
        curr = sdf.iloc[i]
        prev = sdf.iloc[i-1]
        
        signals = []
        
        # 1. Aggressive Buyers
        if curr['Body'] > 0 and curr['AbsBody'] > 1.5 * curr['AvgBody'] and curr['Volume'] > 1.2 * curr['AvgVol']:
            signals.append("Aggressive Buyer")
            
        # 2. Aggressive Sellers
        if curr['Body'] < 0 and curr['AbsBody'] > 1.5 * curr['AvgBody'] and curr['Volume'] > 1.2 * curr['AvgVol']:
            signals.append("Aggressive Seller")
            
        # 3. POI
        hist_df = sdf.iloc[max(0, i-50):i]
        if not hist_df.empty:
            poi_idx = hist_df['Volume'].idxmax()
            poi_price = hist_df.loc[poi_idx, 'Close']
            if abs(curr['Close'] - poi_price) / poi_price < 0.01:
                signals.append("Near POI")

        # 4. POR
        range_std = sdf['Close'].iloc[max(0, i-10):i+1].std()
        avg_range_std = sdf['Close'].rolling(50).std().iloc[i]
        if curr['AbsBody'] > 2 * range_std and range_std < 0.5 * avg_range_std:
            signals.append("Point of Release")

        # 5. Absorption
        if curr['Volume'] > 1.5 * curr['AvgVol'] and curr['AbsBody'] < 0.3 * curr['AvgBody']:
            if curr['Close'] > curr['Open']:
                signals.append("Sellers Absorption")
            else:
                signals.append("Buyers Absorption")
        
        lower_shadow = min(curr['Open'], curr['Close']) - curr['Low']
        upper_shadow = curr['High'] - max(curr['Open'], curr['Close'])
        if curr['Volume'] > 1.2 * curr['AvgVol']:
            if lower_shadow > 2 * curr['AbsBody']:
                signals.append("Absorption (L-Shadow)")
            if upper_shadow > 2 * curr['AbsBody']:
                signals.append("Absorption (U-Shadow)")

        all_signals.append({
            "Date": curr['Date'].strftime('%Y-%m-%d'),
            "Close": float(curr['Close']),
            "Volume": int(curr['Volume']),
            "Signals": ", ".join(list(set(signals))) if signals else ""
        })
            
    return all_signals

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/signals')
def get_latest_signals():
    try:
        df = fetch_data()
        results = []
        for symbol in df['Symbol'].unique():
            sdf = df[df['Symbol'] == symbol].copy().reset_index(drop=True)
            history = detect_signals_history(sdf)
            if history:
                latest = history[-1]
                if latest['Signals']:
                    results.append({
                        "Symbol": symbol,
                        **latest
                    })
        return jsonify(results)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/historical/<symbol>')
def get_historical(symbol):
    try:
        df = fetch_data()
        sdf = df[df['Symbol'] == symbol.upper()].copy().reset_index(drop=True)
        if sdf.empty:
            return jsonify({"error": "Symbol not found"}), 404
        history = detect_signals_history(sdf)
        return jsonify(history)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
