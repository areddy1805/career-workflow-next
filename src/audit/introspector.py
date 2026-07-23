import inspect
from typing import Any, Dict, List, Set, Type

def extract_class_attributes(cls: Type) -> Dict[str, Any]:
    """Extract all non-callable, non-private class attributes."""
    attributes = {}
    for name, value in inspect.getmembers(cls):
        if not name.startswith("_") and not callable(value):
            attributes[name] = value
    return attributes

def get_class_methods(cls: Type) -> List[Dict[str, Any]]:
    """Extract all non-private methods from a class."""
    methods = []
    for name, func in inspect.getmembers(cls, predicate=inspect.isroutine):
        if not name.startswith("_"):
            sig = inspect.signature(func)
            doc = inspect.getdoc(func) or ""
            methods.append({
                "name": name,
                "signature": str(sig),
                "doc": doc
            })
    return methods
