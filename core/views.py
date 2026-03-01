from django.shortcuts import render
from django.contrib import messages
from .analysis import get_analysis_data
import json

def index(request):
    symbol = request.POST.get('symbol', '').strip().upper()
    analysis = None
    
    # Store history in session
    history = request.session.get('analysis_history', [])
    
    if request.method == 'POST' and symbol:
        data, error = get_analysis_data(symbol)
        if error:
            messages.error(request, f"Error: {error}")
        else:
            analysis = data
            # Update history
            if symbol not in history:
                history.insert(0, symbol)
                request.session['analysis_history'] = history[:10] # Keep last 10
                
    # Prepare chart JSON if analysis exists
    chart_json = None
    if analysis:
        chart_json = json.dumps(analysis['chart_data'])
        
    return render(request, 'core/index.html', {
        'analysis': analysis,
        'symbol': symbol,
        'history': history,
        'chart_json': chart_json
    })