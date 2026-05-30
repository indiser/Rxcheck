import csv
import json
import re
import os

def normalize_pmbjp_name(raw_name):
    text = str(raw_name).lower()
    # Strip forms and pharmacopeia markers
    text = re.sub(r'\b(tablets|tablet|capsules|capsule|injection|gel|syrup|suspension|ip|bp|usp|opthalmic|nasal|drops|cream|ointment|solution|dt|sr|er|mr|pr|cr)\b.*', '', text)
    # Strip strengths and dosages
    text = re.sub(r'\d+(\.\d+)?\s*(mg|mcg|g|gm|ml|%|w/w|v/v|iu)', '', text)
    # Standardize conjunctions
    text = text.replace(' and ', ' + ')
    # Clean up stray characters
    text = re.sub(r'[^\w\s\+]', ' ', text)
    text = ' '.join(text.split())
    
    # Normalize spacing around the '+' separator and sort alphabetically to prevent 
    # "amlodipine + atenolol" and "atenolol + amlodipine" from becoming two different keys.
    if '+' in text:
        salts = [parts.strip() for parts in text.split('+') if parts.strip()]
        salts.sort()
        text = ' + '.join(salts)
        
    return text.strip()

def compile_dataset():
    # Update this to exactly match the CSV filename you downloaded
    input_csv = 'janausadhi.csv'
    output_json = 'jan_aushadhi_catalog.json'

    if not os.path.exists(input_csv):
        print(f"[FATAL] Could not find {input_csv}. Check the filename.")
        return

    jan_aushadhi_db = {}
    row_count = 0
    success_count = 0

    print("Initiating PMBJP Data Sanitization Pipeline...")

    # Using utf-8-sig to handle Windows BOMs that often corrupt government CSVs
    with open(input_csv, mode='r', encoding='utf-8-sig', errors='replace') as file:
        reader = csv.DictReader(file)
        
        # Strip invisible whitespace from headers (Common Govt CSV error)
        reader.fieldnames = [header.strip() for header in reader.fieldnames]

        # Map to the actual column names in your CSV. Adjust these if the government changes their header format.
        col_name = 'Generic Name' if 'Generic Name' in reader.fieldnames else reader.fieldnames[1]
        col_price = 'MRP' if 'MRP' in reader.fieldnames else 'Unit Price'
        col_unit = 'Unit Size' if 'Unit Size' in reader.fieldnames else reader.fieldnames[2]
        col_code = 'Drug Code' if 'Drug Code' in reader.fieldnames else reader.fieldnames[0]

        for row in reader:
            row_count += 1
            raw_name = row.get(col_name, "")
            if not raw_name:
                continue
                
            clean_key = normalize_pmbjp_name(raw_name)
            if not clean_key:
                continue
                
            # Create the data payload for this specific dosage/form
            try:
                price_val = float(row.get(col_price, 0).replace(',', ''))
            except ValueError:
                price_val = row.get(col_price, "N/A")

            payload = {
                "drug_code": row.get(col_code, "N/A"),
                "display": raw_name.strip(),
                "price": price_val,
                "unit": row.get(col_unit, "N/A").strip()
            }

            # Group by generic salt to handle multiple dosages
            if clean_key not in jan_aushadhi_db:
                jan_aushadhi_db[clean_key] = []
            
            jan_aushadhi_db[clean_key].append(payload)
            success_count += 1

    # Write the compiled memory map to disk
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(jan_aushadhi_db, f, indent=4, ensure_ascii=False)

    print(f"[SUCCESS] Parsed {row_count} rows.")
    print(f"[SUCCESS] Compiled {len(jan_aushadhi_db)} unique generic chemical keys.")
    print(f"[SUCCESS] Output saved to {output_json}.")

if __name__ == "__main__":
    compile_dataset()