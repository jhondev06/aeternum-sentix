import json
import logging
import os
from typing import Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

class AlertLogger:
    def __init__(self, log_dir: str = 'logs/alerts'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_log_file = self._get_current_log_file()

        # Setup logging
        self.logger = logging.getLogger('alerts')
        self.logger.setLevel(logging.INFO)

        # File handler for detailed logs
        fh = logging.FileHandler(self.current_log_file)
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def _get_current_log_file(self) -> Path:
        """Get current log file path (daily rotation)"""
        today = datetime.now().strftime('%Y-%m-%d')
        return self.log_dir / f'alerts_{today}.log'

    def log_alert_triggered(self, rule_id: str, rule_name: str, ticker: str,
                           conditions: List[Dict], actions: List[Dict],
                           trigger_data: Dict[str, Any]) -> None:
        """Log when an alert is triggered"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event': 'alert_triggered',
            'rule_id': rule_id,
            'rule_name': rule_name,
            'ticker': ticker,
            'conditions': conditions,
            'actions': actions,
            'trigger_data': trigger_data
        }

        self.logger.info(f"ALERT_TRIGGERED: {json.dumps(log_entry)}")

    def log_webhook_sent(self, rule_id: str, webhook_url: str, success: bool,
                        response_time: float = None, error: str = None) -> None:
        """Log webhook delivery"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event': 'webhook_sent',
            'rule_id': rule_id,
            'webhook_url': webhook_url,
            'success': success,
            'response_time': response_time,
            'error': error
        }

        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"WEBHOOK_SENT: {json.dumps(log_entry)}")

    def log_telegram_sent(self, rule_id: str, chat_id: str, success: bool,
                         message_length: int = None, error: str = None) -> None:
        """Log telegram message delivery"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event': 'telegram_sent',
            'rule_id': rule_id,
            'chat_id': chat_id,
            'success': success,
            'message_length': message_length,
            'error': error
        }

        level = logging.INFO if success else logging.WARNING
        self.logger.log(level, f"TELEGRAM_SENT: {json.dumps(log_entry)}")

    def log_rule_error(self, rule_id: str, error: str, context: Dict = None) -> None:
        """Log rule evaluation errors"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'event': 'rule_error',
            'rule_id': rule_id,
            'error': error,
            'context': context or {}
        }

        self.logger.error(f"RULE_ERROR: {json.dumps(log_entry)}")

    def get_alert_history(self, rule_id: str = None, days: int = 7) -> pd.DataFrame:
        """Get alert history for analysis"""
        start_date = datetime.now() - timedelta(days=days)
        all_logs = []

        # Read log files for the period
        for log_file in self.log_dir.glob('alerts_*.log'):
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if 'ALERT_TRIGGERED' in line:
                            # Parse the JSON part
                            json_part = line.split('ALERT_TRIGGERED: ', 1)[1].strip()
                            log_entry = json.loads(json_part)

                            entry_time = datetime.fromisoformat(log_entry['timestamp'])
                            if entry_time >= start_date:
                                if rule_id is None or log_entry['rule_id'] == rule_id:
                                    all_logs.append(log_entry)
            except Exception as e:
                self.logger.warning(f"Error reading log file {log_file}: {e}")

        return pd.DataFrame(all_logs)

    def get_delivery_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get delivery statistics"""
        df = self.get_alert_history(days=days)

        if df.empty:
            return {'total_alerts': 0, 'successful_deliveries': 0, 'failed_deliveries': 0}

        total_alerts = len(df)

        # Count successful vs failed deliveries (simplified - would need webhook logs too)
        successful_deliveries = total_alerts  # Assume success for now
        failed_deliveries = 0

        return {
            'total_alerts': total_alerts,
            'successful_deliveries': successful_deliveries,
            'failed_deliveries': failed_deliveries,
            'success_rate': successful_deliveries / total_alerts if total_alerts > 0 else 0
        }

    def cleanup_old_logs(self, days_to_keep: int = 30) -> None:
        """Clean up old log files"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        for log_file in self.log_dir.glob('alerts_*.log'):
            try:
                file_date_str = log_file.stem.split('_', 1)[1]
                file_date = datetime.strptime(file_date_str, '%Y-%m-%d')

                if file_date < cutoff_date:
                    log_file.unlink()
                    self.logger.info(f"Deleted old log file: {log_file}")
            except Exception as e:
                self.logger.warning(f"Error cleaning up log file {log_file}: {e}")