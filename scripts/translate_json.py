import json
from google.cloud import translate_v2 as translate
import os

def translate_text(text, target_language='en'):
    """Translates text into the target language, handling None or non-string inputs."""
    if not text or not isinstance(text, str):
        return text
    
    # Simple check to avoid translating what looks like data/identifiers
    if text.strip().replace('.','',1).isdigit():
        return text
    if '%' in text and any(char.isdigit() for char in text):
        return text
    if text.startswith('S') and text[1:].isdigit(): # for S4 etc
        return text
        
    translate_client = translate.Client()
    result = translate_client.translate(text, target_language=target_language)
    return result['translatedText']

def translate_list(data_list):
    """Translates a list of strings."""
    if not isinstance(data_list, list):
        return data_list
    return [translate_text(item) for item in data_list]

def main():
    """Main function to perform a targeted translation of the comparison_tables field."""
    input_file = 'frontend/fixtures/comparison_report_new_2.json'
    output_file = 'frontend/fixtures/comparison_report_new_2.en.json'

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
            
    # --- Translate 'comparison_tables' section based on the provided schema ---
    if 'comparison_tables' in data and isinstance(data['comparison_tables'], list):
        for table in data['comparison_tables']:
            if 'template_row' in table and isinstance(table['template_row'], list):
                table['template_row'] = translate_list(table['template_row'])

            if 'metadata' in table and 'category' in table['metadata']:
                table['metadata']['category'] = translate_text(table['metadata']['category'])
            
            if 'rows' in table and isinstance(table['rows'], list):
                for row in table['rows']:
                    if 'leaf_path' in row and isinstance(row['leaf_path'], list):
                        row['leaf_path'] = translate_list(row['leaf_path'])
                    
                    if 'leaf_description' in row:
                        row['leaf_description'] = translate_text(row['leaf_description'])
                    
                    if 'rationale' in row:
                        row['rationale'] = translate_text(row['rationale'])

                    if 'probtp_advantage' in row:
                        row['probtp_advantage'] = translate_text(row['probtp_advantage'])

                    if 'cells' in row and isinstance(row['cells'], list):
                        for cell in row['cells']:
                            # For header rows, the 'value' is a header
                            if row.get('row_number') == 1 and 'value' in cell:
                                cell['value'] = translate_text(cell['value'])
                            
                            # For data rows, only translate 'value' if it's a dimension
                            if cell.get('type') == 'dimension' and 'value' in cell:
                                cell['value'] = translate_text(cell['value'])
                                
                            if 'display_value' in cell:
                                cell['display_value'] = translate_text(cell['display_value'])

                            if 'notes' in cell:
                                cell['notes'] = translate_text(cell['notes'])
                            
                            if 'metadata' in cell and 'conditions' in cell.get('metadata', {}):
                                cell['metadata']['conditions'] = translate_text(cell['metadata']['conditions'])

                            if 'vendor_conditions' in cell and isinstance(cell.get('vendor_conditions'), list):
                                for condition in cell['vendor_conditions']:
                                    if 'description' in condition:
                                        condition['description'] = translate_text(condition['description'])
                                    if 'coverage_modifier' in condition:
                                        condition['coverage_modifier'] = translate_text(condition['coverage_modifier'])
                                        
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Comparison tables translation complete. Translated file saved as {output_file}")

if __name__ == "__main__":
    main()
