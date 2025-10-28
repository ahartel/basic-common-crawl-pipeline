from filters.abc_filters import Filter
from prometheus_client import Counter
import pycld2 as cld2

valid_language_counter = Counter("language_filter_documents", "Number of documents filtered by language")
invalid_language_counter = Counter("language_filter_documents_invalid", "Number of documents not in the target language")

class LanguageFilter(Filter):
    def __init__(self, target_lang: str):
        self.target_lang = target_lang

    def apply(self, data: str) -> bool:
        
        filtered_data = []
        try:
            isReliable, textBytesFound, details = cld2.detect(data)
            
            top_lang_name, top_lang_code, top_lang_percent, top_lang_score = details[0]

            if isReliable and top_lang_code == self.target_lang and top_lang_percent > 90:
                
                filtered_data.append(data)
                valid_language_counter.inc()
            else:
                invalid_language_counter.inc()
                
        except Exception:
            invalid_language_counter.inc()
            
        return filtered_data
