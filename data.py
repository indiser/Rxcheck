"""
data.py — RxCheck business data store.

This module is the authoritative source of truth for all catalog and rule data.
It is the Python translation of the former static/data.js file.

SECURITY NOTE: INTERACTION_RULES are intentionally NOT served to the client.
They are evaluated exclusively server-side via /api/check-interactions.
BRAND_HINTS, PRICE_CATALOG, and BRAND_SAVINGS_LOOKUP are safe display data
served via /api/local-data.
"""

# ---------------------------------------------------------------------------
# Brand → Generic name mappings
# Used by the /api/normalize-drug endpoint for server-side Levenshtein matching.
# ---------------------------------------------------------------------------
# BRAND_HINTS = {
#     "aldactone": "spironolactone",
#     "amlong": "amlodipine",
#     "atorva": "atorvastatin",
#     "augmentin": "amoxicillin clavulanate",
#     "azithral": "azithromycin",
#     "calpol": "paracetamol",
#     "cetzine": "cetirizine",
#     "ciplox": "ciprofloxacin",
#     "clopitab": "clopidogrel",
#     "clopilet": "clopidogrel",
#     "combiflam": "ibuprofen paracetamol",
#     "crocin": "paracetamol",
#     "deriphyllin": "etofylline theophylline",
#     "dolo": "paracetamol",
#     "emeset": "ondansetron",
#     "ecosprin": "aspirin",
#     "allegra": "fexofenadine",
#     "glycomet": "metformin",
#     "glucophage": "metformin",
#     "januvia": "sitagliptin",
#     "janumet": "sitagliptin metformin",
#     "lasix": "furosemide",
#     "montair": "montelukast levocetirizine",
#     "pan": "pantoprazole",
#     "pantocid": "pantoprazole",
#     "razo": "rabeprazole",
#     "rozavel": "rosuvastatin",
#     "shelcal": "calcium carbonate",
#     "telma": "telmisartan",
#     "thyronorm": "levothyroxine",
#     "udiliv": "ursodeoxycholic acid",
# }

# # ---------------------------------------------------------------------------
# # Generic drug price catalog
# # Keyed by lowercase generic INN name.
# # ---------------------------------------------------------------------------
# PRICE_CATALOG = {
#     "acetaminophen": {
#         "display": "Paracetamol / Acetaminophen",
#         "alternatives": ["Paracetamol tablet", "Paracetamol suspension"],
#         "range": "Rs. 12-45 per strip of 10 tablets",
#     },
#     "amlodipine": {
#         "display": "Amlodipine",
#         "alternatives": ["Amlodipine 2.5 mg", "Amlodipine 5 mg", "Amlodipine 10 mg"],
#         "range": "Rs. 12-60 per strip of 10 tablets",
#     },
#     "amoxicillin": {
#         "display": "Amoxicillin",
#         "alternatives": ["Amoxicillin capsule", "Amoxicillin + clavulanate tablet"],
#         "range": "Rs. 45-220 per strip",
#     },
#     "aspirin": {
#         "display": "Aspirin",
#         "alternatives": ["Aspirin gastro-resistant tablet", "Low-dose aspirin tablet"],
#         "range": "Rs. 5-45 per strip of 14 tablets",
#     },
#     "atorvastatin": {
#         "display": "Atorvastatin",
#         "alternatives": ["Atorvastatin 10 mg", "Atorvastatin 20 mg", "Atorvastatin 40 mg"],
#         "range": "Rs. 35-190 per strip of 10 tablets",
#     },
#     "azithromycin": {
#         "display": "Azithromycin",
#         "alternatives": ["Azithromycin 250 mg", "Azithromycin 500 mg"],
#         "range": "Rs. 55-150 per strip of 3 tablets",
#     },
#     "calcium": {
#         "display": "Calcium carbonate",
#         "alternatives": ["Calcium carbonate", "Calcium + vitamin D3"],
#         "range": "Rs. 60-220 per strip",
#     },
#     "carbamazepine": {
#         "display": "Carbamazepine",
#         "alternatives": ["Carbamazepine immediate-release", "Carbamazepine controlled-release"],
#         "range": "Rs. 18-95 per strip of 10 tablets",
#     },
#     "ciprofloxacin": {
#         "display": "Ciprofloxacin",
#         "alternatives": ["Ciprofloxacin 250 mg", "Ciprofloxacin 500 mg"],
#         "range": "Rs. 25-95 per strip of 10 tablets",
#     },
#     "clarithromycin": {
#         "display": "Clarithromycin",
#         "alternatives": ["Clarithromycin 250 mg", "Clarithromycin 500 mg"],
#         "range": "Rs. 120-420 per strip",
#     },
#     "clopidogrel": {
#         "display": "Clopidogrel",
#         "alternatives": ["Clopidogrel 75 mg", "Clopidogrel + aspirin fixed dose"],
#         "range": "Rs. 35-170 per strip of 10 tablets",
#     },
#     "diclofenac": {
#         "display": "Diclofenac",
#         "alternatives": ["Diclofenac tablet", "Diclofenac gel", "Diclofenac injection"],
#         "range": "Rs. 12-120 per pack",
#     },
#     "digoxin": {
#         "display": "Digoxin",
#         "alternatives": ["Digoxin 0.25 mg tablet", "Digoxin elixir"],
#         "range": "Rs. 10-70 per strip",
#     },
#     "escitalopram": {
#         "display": "Escitalopram",
#         "alternatives": ["Escitalopram 5 mg", "Escitalopram 10 mg", "Escitalopram 20 mg"],
#         "range": "Rs. 35-180 per strip of 10 tablets",
#     },
#     "fluconazole": {
#         "display": "Fluconazole",
#         "alternatives": ["Fluconazole 150 mg", "Fluconazole 200 mg"],
#         "range": "Rs. 15-120 per strip",
#     },
#     "fluoxetine": {
#         "display": "Fluoxetine",
#         "alternatives": ["Fluoxetine 20 mg capsule", "Fluoxetine dispersible tablet"],
#         "range": "Rs. 25-125 per strip",
#     },
#     "furosemide": {
#         "display": "Furosemide",
#         "alternatives": ["Furosemide tablet", "Furosemide injection"],
#         "range": "Rs. 8-60 per strip",
#     },
#     "glimepiride": {
#         "display": "Glimepiride",
#         "alternatives": ["Glimepiride 1 mg", "Glimepiride 2 mg", "Glimepiride + metformin"],
#         "range": "Rs. 18-140 per strip",
#     },
#     "ibuprofen": {
#         "display": "Ibuprofen",
#         "alternatives": ["Ibuprofen tablet", "Ibuprofen + paracetamol tablet"],
#         "range": "Rs. 12-85 per strip",
#     },
#     "insulin": {
#         "display": "Insulin",
#         "alternatives": ["Regular insulin", "NPH insulin", "Premix insulin"],
#         "range": "Rs. 140-900 per vial or cartridge",
#     },
#     "levothyroxine": {
#         "display": "Levothyroxine",
#         "alternatives": ["Levothyroxine 25 mcg", "Levothyroxine 50 mcg", "Levothyroxine 100 mcg"],
#         "range": "Rs. 95-190 per bottle of 100 tablets",
#     },
#     "linezolid": {
#         "display": "Linezolid",
#         "alternatives": ["Linezolid 600 mg tablet", "Linezolid suspension"],
#         "range": "Rs. 250-850 per strip",
#     },
#     "losartan": {
#         "display": "Losartan",
#         "alternatives": ["Losartan 25 mg", "Losartan 50 mg", "Losartan + hydrochlorothiazide"],
#         "range": "Rs. 25-120 per strip",
#     },
#     "metformin": {
#         "display": "Metformin",
#         "alternatives": ["Metformin immediate-release", "Metformin sustained-release"],
#         "range": "Rs. 18-110 per strip of 10 tablets",
#     },
#     "methotrexate": {
#         "display": "Methotrexate",
#         "alternatives": ["Methotrexate tablet", "Methotrexate injection"],
#         "range": "Rs. 40-220 per pack",
#     },
#     "omeprazole": {
#         "display": "Omeprazole",
#         "alternatives": ["Omeprazole capsule", "Omeprazole + domperidone capsule"],
#         "range": "Rs. 18-110 per strip",
#     },
#     "pantoprazole": {
#         "display": "Pantoprazole",
#         "alternatives": ["Pantoprazole 40 mg", "Pantoprazole + domperidone capsule"],
#         "range": "Rs. 25-160 per strip",
#     },
#     "phenytoin": {
#         "display": "Phenytoin",
#         "alternatives": ["Phenytoin tablet", "Phenytoin suspension"],
#         "range": "Rs. 12-80 per strip",
#     },
#     "ramipril": {
#         "display": "Ramipril",
#         "alternatives": ["Ramipril 2.5 mg", "Ramipril 5 mg"],
#         "range": "Rs. 30-140 per strip",
#     },
#     "rivaroxaban": {
#         "display": "Rivaroxaban",
#         "alternatives": ["Rivaroxaban 10 mg", "Rivaroxaban 15 mg", "Rivaroxaban 20 mg"],
#         "range": "Rs. 120-620 per strip",
#     },
#     "rosuvastatin": {
#         "display": "Rosuvastatin",
#         "alternatives": ["Rosuvastatin 5 mg", "Rosuvastatin 10 mg", "Rosuvastatin 20 mg"],
#         "range": "Rs. 45-220 per strip",
#     },
#     "sertraline": {
#         "display": "Sertraline",
#         "alternatives": ["Sertraline 25 mg", "Sertraline 50 mg", "Sertraline 100 mg"],
#         "range": "Rs. 45-210 per strip",
#     },
#     "simvastatin": {
#         "display": "Simvastatin",
#         "alternatives": ["Simvastatin 10 mg", "Simvastatin 20 mg", "Simvastatin 40 mg"],
#         "range": "Rs. 30-170 per strip",
#     },
#     "sitagliptin": {
#         "display": "Sitagliptin",
#         "alternatives": ["Sitagliptin tablet", "Sitagliptin + metformin tablet"],
#         "range": "Rs. 80-360 per strip",
#     },
#     "spironolactone": {
#         "display": "Spironolactone",
#         "alternatives": ["Spironolactone 25 mg", "Spironolactone 50 mg"],
#         "range": "Rs. 20-130 per strip",
#     },
#     "telmisartan": {
#         "display": "Telmisartan",
#         "alternatives": ["Telmisartan 40 mg", "Telmisartan 80 mg", "Telmisartan + amlodipine"],
#         "range": "Rs. 45-190 per strip",
#     },
#     "tramadol": {
#         "display": "Tramadol",
#         "alternatives": ["Tramadol capsule", "Tramadol + paracetamol tablet"],
#         "range": "Rs. 20-120 per strip",
#     },
#     "warfarin": {
#         "display": "Warfarin",
#         "alternatives": ["Warfarin 1 mg", "Warfarin 2 mg", "Warfarin 5 mg"],
#         "range": "Rs. 18-80 per strip",
#     },
# }

# ---------------------------------------------------------------------------
# Brand savings lookup — display data for the "Save Money" table.
# Safe to serve to the client; contains no interaction logic.
# ---------------------------------------------------------------------------
BRAND_SAVINGS_LOOKUP = [
    {
        "brand": "Generic Telmisartan (PMBJP)",
        "generic": "Telmisartan 40 mg",
        "mrp": "Rs. 12 per strip of 10",
        "cue": "Jan Aushadhi stores offer high-quality generic telmisartan at deeply subsidized rates.",
    },
    {
        "brand": "Generic Paracetamol (PMBJP)",
        "generic": "Paracetamol 500 mg",
        "mrp": "Rs. 5 per strip of 10",
        "cue": "Jan Aushadhi stores offer generic paracetamol at extremely low prices.",
    },
    {
        "brand": "Generic Metformin (PMBJP)",
        "generic": "Metformin 500 mg",
        "mrp": "Rs. 15 per strip of 10",
        "cue": "Consider PMBJP generic metformin for chronic diabetes savings.",
    },
    {
        "brand": "Generic Atorvastatin (PMBJP)",
        "generic": "Atorvastatin 10 mg",
        "mrp": "Rs. 12 per strip of 10",
        "cue": "Jan Aushadhi generic atorvastatin provides substantial monthly savings.",
    },
    {
        "brand": "Dolo 650",
        "generic": "Paracetamol 650 mg",
        "mrp": "Rs. 34 per strip of 15",
        "cue": "Ask for paracetamol 650 mg tablets.",
    },
    {
        "brand": "Crocin Advance",
        "generic": "Paracetamol 500 mg",
        "mrp": "Rs. 20 per strip of 15",
        "cue": "Compare with plain paracetamol 500 mg.",
    },
    {
        "brand": "Calpol 500",
        "generic": "Paracetamol 500 mg",
        "mrp": "Rs. 15 per strip of 15",
        "cue": "Plain paracetamol alternatives are widely available.",
    },
    {
        "brand": "Combiflam",
        "generic": "Ibuprofen 400 mg + Paracetamol 325 mg",
        "mrp": "Rs. 42 per strip of 20",
        "cue": "Confirm if a combination painkiller is needed.",
    },
    {
        "brand": "Ecosprin 75",
        "generic": "Aspirin 75 mg",
        "mrp": "Rs. 5 per strip of 14",
        "cue": "Ask for low-dose aspirin 75 mg.",
    },
    {
        "brand": "Clopitab 75",
        "generic": "Clopidogrel 75 mg",
        "mrp": "Rs. 115 per strip of 15",
        "cue": "Compare with clopidogrel 75 mg generics.",
    },
    {
        "brand": "Clopilet 75",
        "generic": "Clopidogrel 75 mg",
        "mrp": "Rs. 107 per strip of 15",
        "cue": "Look for the same strength and tablet count.",
    },
    {
        "brand": "Glycomet 500",
        "generic": "Metformin 500 mg",
        "mrp": "Rs. 20 per strip of 20",
        "cue": "Immediate-release and SR forms are not interchangeable.",
    },
    {
        "brand": "Janumet 50/500",
        "generic": "Sitagliptin 50 mg + Metformin 500 mg",
        "mrp": "Rs. 430 per strip of 15",
        "cue": "Ask if separate generic tablets are appropriate.",
    },
    {
        "brand": "Januvia 100",
        "generic": "Sitagliptin 100 mg",
        "mrp": "Rs. 430 per strip of 7",
        "cue": "Compare sitagliptin generics of the same strength.",
    },
    {
        "brand": "Amaryl 1",
        "generic": "Glimepiride 1 mg",
        "mrp": "Rs. 115 per strip of 30",
        "cue": "Do not swap diabetes medicines without dose review.",
    },
    {
        "brand": "Telma 40",
        "generic": "Telmisartan 40 mg",
        "mrp": "Rs. 160 per strip of 15",
        "cue": "Ask for telmisartan 40 mg tablets.",
    },
    {
        "brand": "Amlong 5",
        "generic": "Amlodipine 5 mg",
        "mrp": "Rs. 32 per strip of 15",
        "cue": "Compare with amlodipine 5 mg generics.",
    },
    {
        "brand": "Lasix 40",
        "generic": "Furosemide 40 mg",
        "mrp": "Rs. 15 per strip of 15",
        "cue": "Check dose timing and potassium advice.",
    },
    {
        "brand": "Aldactone 25",
        "generic": "Spironolactone 25 mg",
        "mrp": "Rs. 37 per strip of 15",
        "cue": "Confirm potassium monitoring with the prescriber.",
    },
    {
        "brand": "Atorva 10",
        "generic": "Atorvastatin 10 mg",
        "mrp": "Rs. 80 per strip of 10",
        "cue": "Compare with atorvastatin 10 mg generics.",
    },
    {
        "brand": "Rozavel 10",
        "generic": "Rosuvastatin 10 mg",
        "mrp": "Rs. 155 per strip of 10",
        "cue": "Rosuvastatin and atorvastatin are not direct swaps.",
    },
    {
        "brand": "Thyronorm 50",
        "generic": "Levothyroxine 50 mcg",
        "mrp": "Rs. 180 per bottle of 120",
        "cue": "Keep the same brand unless the doctor advises a switch.",
    },
    {
        "brand": "Pan 40",
        "generic": "Pantoprazole 40 mg",
        "mrp": "Rs. 140 per strip of 15",
        "cue": "Ask for pantoprazole 40 mg tablets.",
    },
    {
        "brand": "Pantocid 40",
        "generic": "Pantoprazole 40 mg",
        "mrp": "Rs. 182 per strip of 15",
        "cue": "Compare with same-strength pantoprazole generics.",
    },
    {
        "brand": "Razo 20",
        "generic": "Rabeprazole 20 mg",
        "mrp": "Rs. 125 per strip of 15",
        "cue": "Ask for rabeprazole 20 mg tablets.",
    },
    {
        "brand": "Augmentin 625 Duo",
        "generic": "Amoxicillin 500 mg + Clavulanic acid 125 mg",
        "mrp": "Rs. 220 per strip of 10",
        "cue": "Finish antibiotics only as prescribed.",
    },
    {
        "brand": "Azithral 500",
        "generic": "Azithromycin 500 mg",
        "mrp": "Rs. 132 per strip of 3",
        "cue": "Confirm the exact course length.",
    },
    {
        "brand": "Ciplox 500",
        "generic": "Ciprofloxacin 500 mg",
        "mrp": "Rs. 55 per strip of 10",
        "cue": "Avoid substituting antibiotics without approval.",
    },
    {
        "brand": "Cetzine 10",
        "generic": "Cetirizine 10 mg",
        "mrp": "Rs. 30 per strip of 15",
        "cue": "Compare with cetirizine 10 mg generics.",
    },
    {
        "brand": "Allegra 120",
        "generic": "Fexofenadine 120 mg",
        "mrp": "Rs. 230 per strip of 10",
        "cue": "Ask for fexofenadine 120 mg tablets.",
    },
    {
        "brand": "Montair LC",
        "generic": "Montelukast 10 mg + Levocetirizine 5 mg",
        "mrp": "Rs. 250 per strip of 15",
        "cue": "Confirm if combination therapy is needed.",
    },
    {
        "brand": "Shelcal 500",
        "generic": "Calcium carbonate 500 mg + Vitamin D3",
        "mrp": "Rs. 145 per strip of 15",
        "cue": "Compare calcium + vitamin D3 combinations.",
    },
    {
        "brand": "Emeset 4",
        "generic": "Ondansetron 4 mg",
        "mrp": "Rs. 58 per strip of 10",
        "cue": "Ask for ondansetron 4 mg tablets.",
    },
    {
        "brand": "Udiliv 300",
        "generic": "Ursodeoxycholic acid 300 mg",
        "mrp": "Rs. 570 per strip of 15",
        "cue": "Compare same-strength UDCA generics.",
    },
]

# ---------------------------------------------------------------------------
# Drug interaction rules — SERVER-SIDE ONLY.
# These are never serialised and sent to the client.
# Evaluated exclusively in /api/check-interactions.
# ---------------------------------------------------------------------------
INTERACTION_RULES = [
    # --- High severity ---
    {
        "level": "high",
        "a": ["ibuprofen", "diclofenac", "naproxen"],
        "b": ["ibuprofen", "diclofenac", "naproxen"],
        "message": "Duplicate NSAID therapy strongly increases risk of GI bleeding and renal injury.",
        "action": "Discontinue one NSAID. Do not combine multiple NSAIDs.",
    },
    {
        "level": "high",
        "a": ["azithromycin", "clarithromycin", "ciprofloxacin"],
        "b": ["ondansetron", "amiodarone"],
        "message": "Additive risk of QT prolongation and potentially fatal arrhythmias (Torsades de Pointes).",
        "action": "Avoid combination if possible, or monitor ECG if clinically necessary.",
    },
    {
        "level": "high",
        "a": ["fluoxetine", "sertraline", "escitalopram", "citalopram", "paroxetine", "duloxetine"],
        "b": ["tramadol"],
        "message": "Significant risk of Serotonin Syndrome and increased seizure risk.",
        "action": "Avoid combination. Review pain management plan with a clinician.",
    },
    {
        "level": "high",
        "a": ["ibuprofen", "diclofenac", "naproxen"],
        "b": ["telmisartan", "losartan", "ramipril", "furosemide"],
        "message": "Nephrotoxic stacking. Combining NSAIDs with ACEi/ARBs or diuretics can precipitate acute kidney injury (the 'Triple Whammy').",
        "action": "Avoid NSAIDs in patients on blood pressure medications unless closely monitored.",
    },
    {
        "level": "high",
        "a": ["warfarin"],
        "b": ["aspirin", "ibuprofen", "diclofenac", "naproxen"],
        "message": "Higher bleeding risk when warfarin is combined with antiplatelet drugs or NSAIDs.",
        "action": "Avoid casual co-use and check INR/bleeding plan with the prescriber.",
    },
    {
        "level": "high",
        "a": ["warfarin"],
        "b": ["fluconazole", "metronidazole", "trimethoprim"],
        "message": "Can raise anticoagulant effect and INR.",
        "action": "Needs clinician review, INR monitoring, or an alternative antimicrobial.",
    },
    {
        "level": "high",
        "a": ["simvastatin", "atorvastatin"],
        "b": ["clarithromycin", "erythromycin"],
        "message": "Macrolides can increase statin exposure and muscle toxicity risk.",
        "action": "Consider holding or changing the statin/antibiotic under medical advice.",
    },
    {
        "level": "high",
        "a": ["sildenafil", "tadalafil"],
        "b": ["nitroglycerin", "isosorbide"],
        "message": "PDE5 inhibitors with nitrates can cause dangerous hypotension.",
        "action": "Do not combine without emergency-level clinician direction.",
    },
    {
        "level": "high",
        "a": ["linezolid"],
        "b": ["sertraline", "fluoxetine", "escitalopram", "tramadol", "duloxetine"],
        "message": "Serotonergic toxicity risk may increase.",
        "action": "Needs prescriber review and monitoring for serotonin syndrome.",
    },
    {
        "level": "high",
        "a": ["methotrexate"],
        "b": ["trimethoprim", "sulfamethoxazole"],
        "message": "Additive antifolate effects can cause severe marrow toxicity.",
        "action": "Avoid unless specifically supervised.",
    },
    # --- Medium severity ---
    {
        "level": "medium",
        "a": ["aspirin"],
        "b": ["clopidogrel", "rivaroxaban", "apixaban"],
        "message": "Bleeding risk rises with combined antiplatelet or anticoagulant therapy.",
        "action": "May be intentional after cardiac events, but confirm duration and warning signs.",
    },
    {
        "level": "medium",
        "a": ["ibuprofen", "diclofenac", "naproxen"],
        "b": ["aspirin"],
        "message": "NSAIDs can increase bleeding risk and may reduce aspirin cardioprotection.",
        "action": "Separate timing or choose an alternative only with pharmacist advice.",
    },
    {
        "level": "medium",
        "a": ["spironolactone"],
        "b": ["telmisartan", "losartan", "ramipril", "enalapril", "lisinopril"],
        "message": "Potassium can rise when spironolactone is combined with ACE inhibitors or ARBs.",
        "action": "Check renal function and potassium monitoring plan.",
    },
    {
        "level": "medium",
        "a": ["digoxin"],
        "b": ["amiodarone", "verapamil", "clarithromycin"],
        "message": "Digoxin levels may rise, increasing toxicity risk.",
        "action": "Review dose and monitor pulse, nausea, vision changes, and serum levels.",
    },
    {
        "level": "medium",
        "a": ["ciprofloxacin"],
        "b": ["glimepiride", "insulin"],
        "message": "Fluoroquinolones can disturb glucose control.",
        "action": "Monitor glucose closely and review hypoglycemia symptoms.",
    },
    {
        "level": "medium",
        "a": ["levothyroxine"],
        "b": ["calcium", "calcium carbonate", "iron", "ferrous"],
        "message": "Minerals can reduce levothyroxine absorption.",
        "action": "Separate administration by at least 4 hours unless advised otherwise.",
    },
    {
        "level": "medium",
        "a": ["phenytoin", "carbamazepine"],
        "b": ["warfarin", "rivaroxaban", "apixaban"],
        "message": "Enzyme-inducing antiepileptics can alter anticoagulant exposure.",
        "action": "Requires clinician review of anticoagulant choice and monitoring.",
    },
]
