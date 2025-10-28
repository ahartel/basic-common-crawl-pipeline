import yaml
import json
from filters.language import LanguageFilter
from filters.line_wise import LineWiseFilter
from filters.abc_filters import CompositeFilter
from filters.document_length import DocumentLengthFilter

def load_config():
    with open('pipelines/config.yaml', 'r') as f:
        config = yaml.safe_load(f)['pipeline']
        return config

def create_full_pipeline():
    config = load_config()
    lang_filter = LanguageFilter(target_lang=config['lang'])
    line_wise_filter = LineWiseFilter()
    document_length_filter = DocumentLengthFilter(config['document_length']['min_chars'], config['document_length']['max_chars'])
    return CompositeFilter([document_length_filter,lang_filter, line_wise_filter])

def run_pipeline(data, pipeline):
    filtered_data = pipeline.apply(data)
    return filtered_data

