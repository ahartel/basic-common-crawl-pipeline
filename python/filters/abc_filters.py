from abc import ABC, abstractmethod


class Filter(ABC):
    @abstractmethod
    def apply(self, text: str) -> bool:
        pass

class CompositeFilter(Filter):
    def __init__(self, filters: list):
        if not all(isinstance(f, Filter) for f in filters):
            raise TypeError("All components must be instances of Filter")
        self._filters = filters

    def apply(self, data):
        for filter_obj in self._filters:
            data = filter_obj.apply(data)
            
            if not data:
                return data
        
        return data