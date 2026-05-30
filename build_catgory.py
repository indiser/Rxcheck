import pandas as pd
import re
import json

def clean_salt(comp1, comp2):
    comp1 = str(comp1) if pd.notnull(comp1) else ""
    comp2 = str(comp2) if pd.notnull(comp2) else ""
    full = comp1 + (" + " + comp2 if comp2 else "")
    cleaned = re.sub(r'\(.*?\)', '', full)
    return re.sub(r'\s+', ' ', cleaned).strip().lower()

def extract_brand_family(raw_name):
    name = str(raw_name).lower()
    # Strip dosage forms and raw numbers, but KEEP letters like AT, LS, CV
    name = re.sub(r'\b(tablet|syrup|injection|suspension|capsule|drop|drops|cream|gel|ointment|solution|dt|sr|er|mr|pr|cr)\b', '', name)
    name = re.sub(r'\b\d+(\.\d+)?\b', '', name)
    name = re.sub(r'[^\w\s-]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()

print("Loading dataset...")
df = pd.read_csv('updated_indian_medicine_data.csv', usecols=['name', 'short_composition1', 'short_composition2', 'price', 'pack_size_label'])

brand_hints = {}
price_catalog = {}

for _, row in df.iterrows():
    raw_name = str(row['name'])
    generic = clean_salt(row['short_composition1'], row['short_composition2'])

    if not generic or generic == "nan":
        continue

    brand_family = extract_brand_family(raw_name)

    if brand_family:
        # Save the exact multi-word brand (e.g., "ascoril ls")
        brand_hints[brand_family] = generic
        
        # Save the base word (e.g., "ascoril") ONLY if it's not already mapped, preventing blind overwrites
        base_word = brand_family.split()[0]
        if base_word not in brand_hints:
            brand_hints[base_word] = generic

    if generic not in price_catalog:
        price_catalog[generic] = {
            "display": generic.title(),
            "alternatives": [raw_name.strip()],
            "range": f"Rs. {row['price']} ({str(row['pack_size_label'])})"
        }

with open('brand_hints.json', 'w', encoding='utf-8') as f:
    json.dump(brand_hints, f, indent=4, ensure_ascii=False)

with open('price_catalog.json', 'w', encoding='utf-8') as f:
    json.dump(price_catalog, f, indent=4, ensure_ascii=False)

print(f"Success! Built high-precision catalog.")