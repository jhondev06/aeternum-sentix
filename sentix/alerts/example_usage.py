#!/usr/bin/env python3
"""
Example usage of the custom alerts system for external webhooks (monitoring/analytics).

This script demonstrates how to:
1. Create alert rules with conditional logic
2. Configure webhooks for notifications
3. Process alerts manually or in monitoring mode
"""

import json
from alerts.engine import AlertEngine
from alerts.rule import AlertRule
from alerts.webhook import WebhookConfig

def create_example_rules():
    """Create example alert rules"""

    # Rule 1: Alert when IPCA sentiment crosses threshold AND volatility is high
    rule1 = AlertRule(
        rule_id="ipca_volatility_alert",
        name="IPCA High Sentiment + High Volatility",
        ticker="IPCA",
        conditions=[
            {
                "field": "mean_sent",
                "operator": ">",
                "value": 0.7
            },
            {
                "field": "volatility",
                "operator": ">",
                "value": 0.8
            }
        ],
        actions=[
            {
                "type": "webhook",
                "url": "https://your-hft-system.com/webhook",
                "signal_type": "long_signal",
                "message": "IPCA sentiment bullish with high volatility - consider long position"
            },
            {
                "type": "telegram",
                "message": "🚀 IPCA Alert: High sentiment + volatility detected"
            }
        ],
        enabled=True,
        cooldown_minutes=30
    )

    # Rule 2: Alert when PETR4 sentiment drops below threshold
    rule2 = AlertRule(
        rule_id="petr4_bearish_alert",
        name="PETR4 Bearish Sentiment Alert",
        ticker="PETR4.SA",
        conditions=[
            {
                "field": "time_decay_mean",
                "operator": "<",
                "value": -0.3
            }
        ],
        actions=[
            {
                "type": "webhook",
                "url": "https://your-hft-system.com/webhook",
                "signal_type": "short_signal",
                "message": "PETR4 sentiment turned bearish - consider short position"
            }
        ],
        enabled=True,
        cooldown_minutes=15
    )

    # Rule 3: Alert when any ticker has extreme sentiment movement
    rule3 = AlertRule(
        rule_id="extreme_sentiment_alert",
        name="Extreme Sentiment Movement",
        ticker="PETR4.SA",  # Can be configured for multiple tickers
        conditions=[
            {
                "field": "std_sent",
                "operator": ">",
                "value": 0.5
            },
            {
                "field": "count",
                "operator": ">",
                "value": 10
            }
        ],
        actions=[
            {
                "type": "webhook",
                "url": "https://your-hft-system.com/webhook",
                "signal_type": "volatility_alert",
                "message": "Extreme sentiment volatility detected - monitor closely"
            }
        ],
        enabled=True,
        cooldown_minutes=60
    )

    return [rule1, rule2, rule3]

def setup_example_webhooks():
    """Setup example webhook configurations"""

    webhook1 = WebhookConfig(
        url="https://your-hft-system.com/trading-signals",
        headers={
            "Authorization": "Bearer your-api-key",
            "Content-Type": "application/json"
        },
        enabled=True
    )

    webhook2 = WebhookConfig(
        url="https://your-monitoring-system.com/alerts",
        headers={"Content-Type": "application/json"},
        enabled=True
    )

    return [webhook1, webhook2]

def main():
    """Main example function"""
    print("🚀 Custom Alerts System (External Webhooks)")
    print("=" * 50)

    # Initialize alert engine
    engine = AlertEngine()

    # Create and add example rules
    print("\n📝 Creating example alert rules...")
    rules = create_example_rules()
    for rule in rules:
        engine.add_rule(rule)
        print(f"✓ Added rule: {rule.name}")

    # Setup webhooks
    print("\n🔗 Configuring webhooks...")
    webhooks = setup_example_webhooks()
    for webhook in webhooks:
        engine.add_webhook(webhook)
        print(f"✓ Added webhook: {webhook.url}")

    # Display current configuration
    print("\n📊 Current Configuration:")
    stats = engine.get_stats()
    print(f"Total Rules: {stats['total_rules']}")
    print(f"Active Rules: {stats['active_rules']}")
    print(f"Total Webhooks: {stats['total_webhooks']}")
    print(f"Active Webhooks: {stats['active_webhooks']}")

    print("\n📋 Alert Rules:")
    for rule in engine.list_rules():
        print(f"  - {rule['name']} ({rule['ticker']}) - {'Enabled' if rule['enabled'] else 'Disabled'}")

    print("\n🌐 Webhooks:")
    for webhook in engine.list_webhooks():
        print(f"  - {webhook['url']} - {'Enabled' if webhook['enabled'] else 'Disabled'}")

    # Example of manual processing (if sentiment data exists)
    print("\n⚡ Testing alert processing...")
    try:
        import pandas as pd
        import os

        if os.path.exists('data/sentiment_bars.csv'):
            df = pd.read_csv('data/sentiment_bars.csv')
            df['bucket_start'] = pd.to_datetime(df['bucket_start'])

            triggered = engine.process_alerts(df)
            if triggered:
                print(f"🎯 {len(triggered)} alerts were triggered!")
                engine.execute_actions(triggered)
            else:
                print("ℹ️  No alerts triggered with current data")
        else:
            print("⚠️  No sentiment data found. Run data ingestion first.")

    except Exception as e:
        print(f"❌ Error during testing: {e}")

    print("\n✅ Alerts system setup complete!")
    print("\n📖 Usage Tips:")
    print("  - Use the API endpoints to manage rules and webhooks")
    print("  - Monitor logs in logs/alerts/ directory")
    print("  - Configure your monitoring system to receive webhook notifications")
    print("  - Adjust thresholds and conditions based on your strategy")

if __name__ == "__main__":
    main()