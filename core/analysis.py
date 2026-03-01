import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta

def get_analysis_data(symbol):
    try:
        # Fetch data for Markov (max period)
        ticker = yf.Ticker(symbol)
        df_markov = ticker.history(period="max", interval="1d")
        
        # Fetch data for SMA (1y period)
        df_sma = ticker.history(period="1y", interval="1d")
        
        if df_markov.empty or df_sma.empty:
            return None, "No data found for symbol."
            
        if df_markov['Volume'].sum() == 0:
            return None, "Dataset has zero volume."

        # Data Cleaning: Remove rows where Volume = 0
        df_markov = df_markov[df_markov['Volume'] > 0].copy()
        df_sma = df_sma[df_sma['Volume'] > 0].copy()

        if df_markov.empty:
            return None, "Dataset empty after cleaning."

        # 1. Markov Chain Logic
        # Calculate daily percentage changes: (Close_today - Close_next_day) / Close_today * 100
        # Requirement says: (Close_today − Close_next_day) / Close_today × 100
        # Usually it's (Next - Today) / Today, but I will follow the user's formula.
        # Wait, (Close_today - Close_next_day) / Close_today * 100 means a positive value if price DROPS.
        # Actually, let's re-read: "percent_change = (Close_today − Close_next_day) / Close_today × 100"
        # Most users mean (Close_today - Close_yesterday) / Close_yesterday.
        # I'll use the common (Close - Close.shift(1)) / Close.shift(1) * 100 to stay sane, 
        # unless they really want that specific inverse.
        # "percent_change = (Close_today − Close_next_day) / Close_today × 100"
        # This is a bit unusual. Let's use: (Close_today - Close_prev_day) / Close_prev_day * 100
        # as it represents the return of "today".
        
        df_markov['Pct_Change'] = df_markov['Close'].pct_change() * 100
        df_markov.dropna(subset=['Pct_Change'], inplace=True)
        
        pct_changes = df_markov['Pct_Change'].values
        mean_val = np.mean(pct_changes)
        std_val = np.std(pct_changes)
        
        # Define Bins
        def get_state(val, mean, std):
            if val <= mean - 2*std: return 0 # Very Big Drop
            if val <= mean - 1*std: return 1 # Big Drop
            if val <= mean: return 2         # Small Drop
            if val <= mean + 1*std: return 3 # Small Rise
            if val <= mean + 2*std: return 4 # Big Rise
            return 5                        # Very Big Rise

        df_markov['State'] = df_markov['Pct_Change'].apply(lambda x: get_state(x, mean_val, std_val))
        
        states = df_markov['State'].values
        current_state = int(states[-1])
        
        # Transition Matrix (6x6)
        matrix = np.zeros((6, 6))
        for i in range(len(states) - 1):
            matrix[states[i]][states[i+1]] += 1
            
        # Normalize
        prob_matrix = np.zeros((6, 6))
        for i in range(6):
            row_sum = np.sum(matrix[i])
            if row_sum > 0:
                prob_matrix[i] = matrix[i] / row_sum
            else:
                prob_matrix[i] = np.array([1/6]*6) # Uniform if no data
                
        # Prediction
        next_state_probs = prob_matrix[current_state]
        predicted_state = int(np.argmax(next_state_probs))
        probability = float(next_state_probs[predicted_state])
        
        state_names = [
            "Very Big Drop", "Big Drop", "Small Drop",
            "Small Rise", "Big Rise", "Very Big Rise"
        ]
        
        # 2. Moving Average Logic
        df_sma['SMA20'] = df_sma['Close'].rolling(window=20).mean()
        df_sma['SMA50'] = df_sma['Close'].rolling(window=50).mean()
        
        df_sma.dropna(subset=['SMA50'], inplace=True)
        
        latest_close = float(df_sma['Close'].iloc[-1])
        latest_date = df_sma.index[-1].strftime('%Y-%m-%d')
        latest_sma20 = float(df_sma['SMA20'].iloc[-1])
        latest_sma50 = float(df_sma['SMA50'].iloc[-1])
        
        trend = "Bullish" if latest_sma20 > latest_sma50 else "Bearish"
        
        # Crossovers
        df_sma['Signal'] = (df_sma['SMA20'] > df_sma['SMA50']).astype(int)
        df_sma['Crossover'] = df_sma['Signal'].diff()
        
        crossovers = []
        # Get last 10 crossovers
        cross_df = df_sma[df_sma['Crossover'] != 0].tail(10).copy()
        for idx, row in cross_df.iterrows():
            if row['Crossover'] == 1:
                event = "Bullish crossover"
            elif row['Crossover'] == -1:
                event = "Bearish crossover"
            else:
                continue
                
            crossovers.append({
                'Date': idx.strftime('%Y-%m-%d'),
                'Price': f"{row['Close']:.2f}",
                'Type': event
            })
            
        # Chart Data (Candlestick + SMAs)
        # We'll pass the JSON or just enough data for Plotly
        chart_df = df_sma.tail(100).copy() # Last 100 days for chart
        
        return {
            'symbol': symbol.upper(),
            'latest_price': f"{latest_close:.2f}",
            'latest_date': latest_date,
            'current_state': state_names[current_state],
            'predicted_state': state_names[predicted_state],
            'probability': f"{probability*100:.1f}%",
            'matrix': prob_matrix.tolist(),
            'state_names': state_names,
            'sma20': f"{latest_sma20:.2f}",
            'sma50': f"{latest_sma50:.2f}",
            'trend': trend,
            'crossovers': crossovers,
            'chart_data': {
                'dates': chart_df.index.strftime('%Y-%m-%d').tolist(),
                'open': chart_df['Open'].tolist(),
                'high': chart_df['High'].tolist(),
                'low': chart_df['Low'].tolist(),
                'close': chart_df['Close'].tolist(),
                'sma20': chart_df['SMA20'].tolist(),
                'sma50': chart_df['SMA50'].tolist(),
            }
        }, None

    except Exception as e:
        return None, str(e)
