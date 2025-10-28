from filters.abc_filters import Filter

class DocumentLengthFilter(Filter):
    
    def __init__(self, min_chars=500, max_chars=1000000):
        self.min_chars = min_chars
        self.max_chars = max_chars

    def apply(self, data):
        doc_length = len(data)

        if not (self.min_chars <= doc_length <= self.max_chars):
            print(f"Document length {doc_length} is outside the valid range [{self.min_chars}, {self.max_chars}]. Filtering document.")
            return []
        
        return data
