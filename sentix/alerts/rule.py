from typing import Dict, Any, List, Callable, Optional
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import re

class AlertCondition(Enum):
    GREATER_THAN = ">"
    LESS_THAN = "<"
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    BETWEEN = "between"
    OUTSIDE = "outside"

class AlertRule:
    def __init__(self, rule_id: str, name: str, ticker: str, conditions: List[Dict], actions: List[Dict],
                 enabled: bool = True, cooldown_minutes: int = 30):
        self.rule_id = rule_id
        self.name = name
        self.ticker = ticker
        self.conditions = conditions
        self.actions = actions
        self.enabled = enabled
        self.cooldown_minutes = cooldown_minutes
        self.last_triggered: Optional[datetime] = None

    def evaluate(self, data: pd.DataFrame, volatility_data: Optional[Dict] = None) -> bool:
        """Evaluate if all conditions are met"""
        if not self.enabled:
            return False

        # Check cooldown
        if self.last_triggered and (datetime.now() - self.last_triggered) < timedelta(minutes=self.cooldown_minutes):
            return False

        # Get latest data for ticker
        if self.ticker not in data['ticker'].values:
            return False

        latest_data = data[data['ticker'] == self.ticker].sort_values('bucket_start').iloc[-1]

        # Evaluate all conditions
        for condition in self.conditions:
            if not self._evaluate_condition(condition, latest_data, volatility_data):
                return False

        return True

    def _evaluate_condition(self, condition: Dict, data: pd.Series, volatility_data: Optional[Dict]) -> bool:
        """Evaluate a single condition"""
        field = condition['field']
        operator = condition['operator']
        value = condition['value']

        # Get field value
        if field == 'volatility' and volatility_data:
            field_value = volatility_data.get(self.ticker, 0)
        elif field in data.index:
            field_value = data[field]
        else:
            return False

        # Handle NaN values
        if pd.isna(field_value):
            return False

        # Evaluate based on operator
        if operator == AlertCondition.GREATER_THAN.value:
            return field_value > value
        elif operator == AlertCondition.LESS_THAN.value:
            return field_value < value
        elif operator == AlertCondition.GREATER_EQUAL.value:
            return field_value >= value
        elif operator == AlertCondition.LESS_EQUAL.value:
            return field_value <= value
        elif operator == AlertCondition.EQUAL.value:
            return field_value == value
        elif operator == AlertCondition.NOT_EQUAL.value:
            return field_value != value
        elif operator == AlertCondition.BETWEEN.value:
            return value[0] <= field_value <= value[1]
        elif operator == AlertCondition.OUTSIDE.value:
            return field_value < value[0] or field_value > value[1]
        elif operator in [AlertCondition.CROSS_ABOVE.value, AlertCondition.CROSS_BELOW.value]:
            # For cross conditions, we need historical data - simplified for now
            return field_value > value if operator == AlertCondition.CROSS_ABOVE.value else field_value < value

        return False

    def trigger(self) -> List[Dict]:
        """Trigger the alert and return actions to execute"""
        self.last_triggered = datetime.now()
        return self.actions

    def to_dict(self) -> Dict:
        """Convert rule to dictionary for serialization"""
        return {
            'rule_id': self.rule_id,
            'name': self.name,
            'ticker': self.ticker,
            'conditions': self.conditions,
            'actions': self.actions,
            'enabled': self.enabled,
            'cooldown_minutes': self.cooldown_minutes,
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'AlertRule':
        """Create rule from dictionary"""
        rule = cls(
            rule_id=data['rule_id'],
            name=data['name'],
            ticker=data['ticker'],
            conditions=data['conditions'],
            actions=data['actions'],
            enabled=data.get('enabled', True),
            cooldown_minutes=data.get('cooldown_minutes', 30)
        )
        if data.get('last_triggered'):
            rule.last_triggered = datetime.fromisoformat(data['last_triggered'])
        return rule