import pandas as pd
import yaml
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading
import time
from pathlib import Path

from .rule import AlertRule
from .webhook import WebhookManager, WebhookConfig
from .logger import AlertLogger
try:
    from ..notify.telegram import send_alert as send_telegram_alert
except ImportError:
    # Fallback for when running as standalone module
    def send_telegram_alert(token, chat_id, message):
        print(f"TELEGRAM: {message}")
        return True

class AlertEngine:
    def __init__(self, config_path: str = 'config.yml'):
        self.config_path = config_path
        self.rules: Dict[str, AlertRule] = {}
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.webhook_manager = WebhookManager()
        self.logger = AlertLogger()
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Load configuration
        self._load_config()

        # Load existing rules and webhooks
        self._load_rules()
        self._load_webhooks()

    def _load_config(self) -> None:
        """Load main configuration"""
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def _load_rules(self) -> None:
        """Load alert rules from storage"""
        rules_file = Path('data/alert_rules.json')
        if rules_file.exists():
            try:
                with open(rules_file, 'r') as f:
                    rules_data = json.load(f)
                    for rule_data in rules_data:
                        rule = AlertRule.from_dict(rule_data)
                        self.rules[rule.rule_id] = rule
            except Exception as e:
                self.logger.logger.error(f"Error loading alert rules: {e}")

    def _save_rules(self) -> None:
        """Save alert rules to storage"""
        rules_file = Path('data/alert_rules.json')
        rules_file.parent.mkdir(exist_ok=True)

        rules_data = [rule.to_dict() for rule in self.rules.values()]
        with open(rules_file, 'w') as f:
            json.dump(rules_data, f, indent=2)

    def _load_webhooks(self) -> None:
        """Load webhook configurations"""
        webhooks_file = Path('data/webhooks.json')
        if webhooks_file.exists():
            try:
                with open(webhooks_file, 'r') as f:
                    webhooks_data = json.load(f)
                    for webhook_data in webhooks_data:
                        webhook = WebhookConfig.from_dict(webhook_data)
                        self.webhooks[webhook.url] = webhook
            except Exception as e:
                self.logger.logger.error(f"Error loading webhooks: {e}")

    def _save_webhooks(self) -> None:
        """Save webhook configurations"""
        webhooks_file = Path('data/webhooks.json')
        webhooks_file.parent.mkdir(exist_ok=True)

        webhooks_data = [webhook.to_dict() for webhook in self.webhooks.values()]
        with open(webhooks_file, 'w') as f:
            json.dump(webhooks_data, f, indent=2)

    def add_rule(self, rule: AlertRule) -> None:
        """Add a new alert rule"""
        self.rules[rule.rule_id] = rule
        self._save_rules()

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self._save_rules()
            return True
        return False

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get a specific rule"""
        return self.rules.get(rule_id)

    def list_rules(self) -> List[Dict]:
        """List all rules"""
        return [rule.to_dict() for rule in self.rules.values()]

    def add_webhook(self, webhook: WebhookConfig) -> None:
        """Add a webhook configuration"""
        self.webhooks[webhook.url] = webhook
        self._save_webhooks()

    def remove_webhook(self, url: str) -> bool:
        """Remove a webhook configuration"""
        if url in self.webhooks:
            del self.webhooks[url]
            self._save_webhooks()
            return True
        return False

    def list_webhooks(self) -> List[Dict]:
        """List all webhooks"""
        return [webhook.to_dict() for webhook in self.webhooks.values()]

    def process_alerts(self, sentiment_data: pd.DataFrame, volatility_data: Optional[Dict] = None) -> List[Dict]:
        """Process all alert rules and return triggered alerts"""
        triggered_alerts = []

        for rule in self.rules.values():
            try:
                if rule.evaluate(sentiment_data, volatility_data):
                    actions = rule.trigger()
                    triggered_alerts.append({
                        'rule': rule,
                        'actions': actions,
                        'timestamp': datetime.now()
                    })

                    # Log the trigger
                    trigger_data = {
                        'sentiment_data': sentiment_data[sentiment_data['ticker'] == rule.ticker].to_dict('records')[-1] if not sentiment_data.empty else {},
                        'volatility': volatility_data.get(rule.ticker) if volatility_data else None
                    }
                    self.logger.log_alert_triggered(
                        rule.rule_id, rule.name, rule.ticker,
                        rule.conditions, actions, trigger_data
                    )

            except Exception as e:
                self.logger.log_rule_error(rule.rule_id, str(e))

        return triggered_alerts

    def execute_actions(self, triggered_alerts: List[Dict]) -> None:
        """Execute actions for triggered alerts"""
        for alert in triggered_alerts:
            rule = alert['rule']
            actions = alert['actions']

            for action in actions:
                action_type = action.get('type')

                if action_type == 'webhook':
                    self._execute_webhook_action(rule, action)
                elif action_type == 'telegram':
                    self._execute_telegram_action(rule, action)
                elif action_type == 'log':
                    self._execute_log_action(rule, action)

    def _execute_webhook_action(self, rule: AlertRule, action: Dict) -> None:
        """Execute webhook action"""
        webhook_url = action.get('url')
        if not webhook_url or webhook_url not in self.webhooks:
            return

        webhook_config = self.webhooks[webhook_url]
        if not webhook_config.enabled:
            return

        # Prepare signal data
        signal_type = action.get('signal_type', 'alert')
        # Map signal types for external system compatibility
        if signal_type == 'long_signal':
            signal_type = 'long'
        elif signal_type == 'short_signal':
            signal_type = 'short'

        signal_data = {
            'rule_id': rule.rule_id,
            'rule_name': rule.name,
            'ticker': rule.ticker,
            'signal_type': signal_type,
            'message': action.get('message', f'Alert triggered for {rule.ticker}'),
            'timestamp': datetime.now().isoformat()
        }

        # Send webhook
        success = self.webhook_manager.send_trading_signal(webhook_url, signal_data)

        # Log delivery
        self.logger.log_webhook_sent(rule.rule_id, webhook_url, success)

    def _execute_telegram_action(self, rule: AlertRule, action: Dict) -> None:
        """Execute telegram action"""
        if not self.config.get('telegram', {}).get('enabled', False):
            return

        token = self.config['telegram']['token']
        chat_id = self.config['telegram']['chat_id']

        message = action.get('message', f'🚨 Alert: {rule.name} triggered for {rule.ticker}')

        try:
            send_telegram_alert(token, chat_id, message)
            self.logger.log_telegram_sent(rule.rule_id, chat_id, True, len(message))
        except Exception as e:
            self.logger.log_telegram_sent(rule.rule_id, chat_id, False, len(message), str(e))

    def _execute_log_action(self, rule: AlertRule, action: Dict) -> None:
        """Execute log action (already logged in process_alerts)"""
        pass

    def start_monitoring(self, check_interval: int = 60) -> None:
        """Start background monitoring"""
        if self.is_running:
            return

        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(check_interval,))
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop background monitoring"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join()

    def _monitor_loop(self, check_interval: int) -> None:
        """Background monitoring loop"""
        while self.is_running:
            try:
                # Load latest sentiment data
                if os.path.exists('data/sentiment_bars.csv'):
                    sentiment_data = pd.read_csv('data/sentiment_bars.csv')
                    sentiment_data['bucket_start'] = pd.to_datetime(sentiment_data['bucket_start'])

                    # Process alerts
                    triggered_alerts = self.process_alerts(sentiment_data)
                    if triggered_alerts:
                        self.execute_actions(triggered_alerts)

            except Exception as e:
                self.logger.logger.error(f"Error in monitoring loop: {e}")

            time.sleep(check_interval)

    def get_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            'total_rules': len(self.rules),
            'active_rules': len([r for r in self.rules.values() if r.enabled]),
            'total_webhooks': len(self.webhooks),
            'active_webhooks': len([w for w in self.webhooks.values() if w.enabled]),
            'delivery_stats': self.logger.get_delivery_stats(),
            'is_monitoring': self.is_running
        }