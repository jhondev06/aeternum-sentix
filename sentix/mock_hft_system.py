#!/usr/bin/env python3
"""
Mock HFT System for Sentix Demo
Simulates a high-frequency trading system that receives signals from Sentix.
"""

from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime
import time
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

class MockHFTSystem:
    def __init__(self):
        self.trades = []
        self.positions = {}
        self.portfolio_value = 1000000.0  # Starting with $1M
        self.commission_rate = 0.0005  # 5 bps
        self.is_running = True

    def process_signal(self, signal_data):
        """Process incoming trading signal"""
        ticker = signal_data['ticker']
        signal_type = signal_data['signal_type']
        rule_name = signal_data['rule_name']
        timestamp = signal_data['timestamp']

        # Simulate position sizing (2% of portfolio per trade)
        position_size = self.portfolio_value * 0.02

        # Mock current price (simplified)
        current_price = self._get_mock_price(ticker)

        # Execute trade
        if signal_type == 'long':
            quantity = int(position_size / current_price)
            cost = quantity * current_price * (1 + self.commission_rate)
            self.positions[ticker] = self.positions.get(ticker, 0) + quantity
            trade_type = 'BUY'
        elif signal_type == 'short':
            quantity = int(position_size / current_price)
            cost = quantity * current_price * (1 + self.commission_rate)
            self.positions[ticker] = self.positions.get(ticker, 0) - quantity
            trade_type = 'SELL'
        else:
            return {"status": "ignored", "reason": "neutral signal"}

        # Record trade
        trade = {
            'timestamp': timestamp,
            'ticker': ticker,
            'signal_type': signal_type,
            'rule_name': rule_name,
            'trade_type': trade_type,
            'quantity': quantity,
            'price': current_price,
            'cost': cost,
            'portfolio_value': self.portfolio_value
        }

        self.trades.append(trade)
        self.portfolio_value -= cost

        logger.info(f"Executed {trade_type} {quantity} {ticker} @ ${current_price:.2f}")

        return {
            "status": "executed",
            "trade": trade,
            "current_positions": self.positions.copy(),
            "portfolio_value": self.portfolio_value
        }

    def _get_mock_price(self, ticker):
        """Get mock current price for ticker"""
        # Simplified price simulation
        base_prices = {
            'PETR4.SA': 25.0,
            'VALE3.SA': 60.0,
            'ITUB4.SA': 30.0,
            'BBDC4.SA': 15.0,
            'WEGE3.SA': 35.0
        }

        base_price = base_prices.get(ticker, 50.0)

        # Add some random variation
        import random
        variation = random.uniform(-0.02, 0.02)  # ±2%
        return base_price * (1 + variation)

    def get_stats(self):
        """Get system statistics"""
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t['trade_type'] == 'BUY')  # Simplified
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'portfolio_value': self.portfolio_value,
            'positions': self.positions.copy(),
            'recent_trades': self.trades[-5:] if self.trades else []
        }

# Global HFT system instance
hft_system = MockHFTSystem()

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "system": "Mock HFT System v1.0"
    })

@app.route('/trade', methods=['POST'])
def receive_signal():
    """Receive trading signal from Sentix"""
    try:
        data = request.get_json()

        if not data or 'signal' not in data:
            return jsonify({"error": "Invalid signal format"}), 400

        signal_data = data['signal']

        # Process the signal
        result = hft_system.process_signal(signal_data)

        logger.info(f"Received signal: {signal_data}")
        logger.info(f"Trade result: {result}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error processing signal: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get HFT system statistics"""
    return jsonify(hft_system.get_stats())

@app.route('/reset', methods=['POST'])
def reset_system():
    """Reset the HFT system for demo purposes"""
    global hft_system
    hft_system = MockHFTSystem()
    return jsonify({"status": "reset", "message": "HFT system reset successfully"})

@app.route('/positions', methods=['GET'])
def get_positions():
    """Get current positions"""
    return jsonify({
        "positions": hft_system.positions,
        "portfolio_value": hft_system.portfolio_value,
        "total_trades": len(hft_system.trades)
    })

def start_mock_server(host='0.0.0.0', port=8080):
    """Start the mock HFT server"""
    logger.info(f"Starting Mock HFT System on {host}:{port}")
    logger.info("Endpoints:")
    logger.info("  GET  /health     - Health check")
    logger.info("  POST /trade      - Receive trading signals")
    logger.info("  GET  /stats      - Get system statistics")
    logger.info("  POST /reset      - Reset system")
    logger.info("  GET  /positions  - Get current positions")

    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    start_mock_server()