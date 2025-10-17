import requests
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import aiohttp

logger = logging.getLogger(__name__)

class WebhookManager:
    def __init__(self, timeout: int = 10, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.executor = ThreadPoolExecutor(max_workers=10)

    async def send_webhook_async(self, url: str, payload: Dict[str, Any], headers: Optional[Dict] = None) -> bool:
        """Send webhook asynchronously"""
        headers = headers or {'Content-Type': 'application/json'}

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                    async with session.post(url, json=payload, headers=headers) as response:
                        if response.status in [200, 201, 202]:
                            logger.info(f"Webhook sent successfully to {url}: {response.status}")
                            return True
                        else:
                            logger.warning(f"Webhook failed to {url}: {response.status} - {await response.text()}")
            except Exception as e:
                logger.error(f"Webhook error to {url} (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff

        return False

    def send_webhook_sync(self, url: str, payload: Dict[str, Any], headers: Optional[Dict] = None) -> bool:
        """Send webhook synchronously"""
        headers = headers or {'Content-Type': 'application/json'}

        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if response.status_code in [200, 201, 202]:
                    logger.info(f"Webhook sent successfully to {url}: {response.status_code}")
                    return True
                else:
                    logger.warning(f"Webhook failed to {url}: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Webhook error to {url} (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries - 1:
                    import time
                    time.sleep(1 * (attempt + 1))  # Exponential backoff

        return False

    def send_trading_signal(self, webhook_url: str, signal_data: Dict[str, Any]) -> bool:
        """Send trading signal to external system"""
        payload = {
            'timestamp': datetime.now().isoformat(),
            'type': 'trading_signal',
            'signal': signal_data
        }

        return self.send_webhook_sync(webhook_url, payload)

    def send_alert_notification(self, webhook_url: str, alert_data: Dict[str, Any]) -> bool:
        """Send alert notification"""
        payload = {
            'timestamp': datetime.now().isoformat(),
            'type': 'alert',
            'alert': alert_data
        }

        return self.send_webhook_sync(webhook_url, payload)

    async def send_batch_webhooks(self, webhooks: List[Dict[str, Any]]) -> List[bool]:
        """Send multiple webhooks asynchronously"""
        tasks = []
        for webhook in webhooks:
            url = webhook['url']
            payload = webhook['payload']
            headers = webhook.get('headers')

            tasks.append(self.send_webhook_async(url, payload, headers))

        return await asyncio.gather(*tasks, return_exceptions=True)

class WebhookConfig:
    def __init__(self, url: str, headers: Optional[Dict] = None, enabled: bool = True):
        self.url = url
        self.headers = headers or {'Content-Type': 'application/json'}
        self.enabled = enabled

    def to_dict(self) -> Dict:
        return {
            'url': self.url,
            'headers': self.headers,
            'enabled': self.enabled
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'WebhookConfig':
        return cls(
            url=data['url'],
            headers=data.get('headers'),
            enabled=data.get('enabled', True)
        )