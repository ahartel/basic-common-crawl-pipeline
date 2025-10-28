# src/filters/line_wise.py
import re
from filters.abc_filters import Filter

class LineWiseFilter(Filter):
    def __init__(self, min_words=3, max_upper_ratio=0.5):
        self.min_words = min_words
        self.max_upper_ratio = max_upper_ratio
    
    def _is_noisy(self, line):
        if len(line.split()) < self.min_words:
            return True
        uppercase_count = sum(1 for char in line if char.isupper())
        alphabetic_count = sum(1 for char in line if char.isalpha())
        if alphabetic_count > 0 and (uppercase_count / alphabetic_count) > self.max_upper_ratio:
            return True
        return False

    def apply(self, data):
        return [line for line in data if not self._is_noisy(line)]
