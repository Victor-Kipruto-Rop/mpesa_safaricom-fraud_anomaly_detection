from __future__ import annotations
from typing import Type, Dict, Any, List
from .base import FraudCheck


class CheckRegistry:
    _registry: Dict[str, Type[FraudCheck]] = {}

    @classmethod
    def register(cls, check_class: Type[FraudCheck]) -> Type[FraudCheck]:
        if not hasattr(check_class, 'name') or not check_class.name:
            raise ValueError('Check classes must define a `name` attribute')
        cls._registry[check_class.name] = check_class
        return check_class

    @classmethod
    def get(cls, name: str) -> Type[FraudCheck]:
        return cls._registry[name]

    @classmethod
    def all(cls) -> List[Type[FraudCheck]]:
        return list(cls._registry.values())

    @classmethod
    def names(cls) -> List[str]:
        return list(cls._registry.keys())
