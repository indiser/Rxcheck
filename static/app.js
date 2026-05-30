"use strict";

const RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST";

const state = {
  mode: "manual",
  selectedDrugs: [],
  lastInputSignature: "",
  photoPreviewUrl: "",
  lastFindings: [],
  lastResolved: [],
  lastSummary: null,
  checkController: null,
};

const dom = {
  manualInput: document.querySelector("#manual-input"),
  prescriptionInput: document.querySelector("#prescription-input"),
  photoInput: document.querySelector("#prescription-photo"),
  photoPreview: document.querySelector("#photo-preview"),
  photoPreviewImage: document.querySelector("#photo-preview-image"),
  photoStatus: document.querySelector("#photo-status"),
  photoRemoveBtn: document.querySelector("#remove-photo-btn"),
  chatgptText: document.querySelector("#chatgpt-text"),
  extractionStatus: document.querySelector("#extraction-status"),
  modeTabs: document.querySelectorAll(".mode-tab"),
  entryPanels: document.querySelectorAll(".entry-panel"),
  checkBtn: document.querySelector("#check-btn"),
  extractBtn: document.querySelector("#extract-btn"),
  sampleBtn: document.querySelector("#sample-btn"),
  clearBtn: document.querySelector("#clear-btn"),
  chipList: document.querySelector("#chip-list"),
  drugCount: document.querySelector("#drug-count"),
  dashboardTitle: document.querySelector("#dashboard-title"),
  apiState: document.querySelector("#api-state"),
  greenCount: document.querySelector("#green-count"),
  yellowCount: document.querySelector("#yellow-count"),
  redCount: document.querySelector("#red-count"),
  alertBanner: document.querySelector("#alert-banner"),
  interactionSource: document.querySelector("#interaction-source"),
  interactionResults: document.querySelector("#interaction-results"),
  saveMoneySummary: document.querySelector("#save-money-summary"),
  saveMoneyResults: document.querySelector("#save-money-results"),
  drugResults: document.querySelector("#drug-results"),
  chipTemplate: document.querySelector("#chip-template"),
  dashboard: document.querySelector(".dashboard"),
  copySummaryBtn: document.querySelector("#copy-summary-btn"),
  whatsappShareBtn: document.querySelector("#whatsapp-share-btn"),
  shareToolbar: document.querySelector("#share-toolbar"),
  disclaimerModal: document.querySelector("#disclaimer-modal"),
  acceptDisclaimerBtn: document.querySelector("#accept-disclaimer-btn"),
};

dom.modeTabs.forEach((tab) => {
  tab.addEventListener("click", () => setMode(tab.dataset.mode));
});

function debounce(func, wait) {
  let timeout;
  return function(...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

dom.manualInput.addEventListener("input", debounce(() => {
  if (state.mode === "manual") {
    setSelectedDrugs(parseManualInput(dom.manualInput.value));
  }
}, 300));

dom.prescriptionInput.addEventListener("input", debounce(() => {
  if (state.mode === "paste") {
    const drugs = extractPrescriptionDrugs(dom.prescriptionInput.value);
    dom.manualInput.value = drugs.join(", ");
    setSelectedDrugs(drugs);
  }
}, 300));

dom.photoInput.addEventListener("change", handlePhotoUpload);
dom.photoRemoveBtn.addEventListener("click", () => clearPhoto());

dom.chatgptText.addEventListener("input", debounce(() => {
  applyExtractedText(dom.chatgptText.value);
}, 300));

dom.extractBtn.addEventListener("click", () => {
  const source = state.mode === "paste" ? dom.prescriptionInput.value : dom.manualInput.value;
  const drugs = state.mode === "paste" ? extractPrescriptionDrugs(source) : parseManualInput(source);
  setSelectedDrugs(drugs);
  showBanner(`Found ${drugs.length} possible medicine ${drugs.length === 1 ? "name" : "names"} for review.`);
});

dom.sampleBtn.addEventListener("click", () => {
  const sample = [
    "Tab Ecosprin 75 mg OD",
    "Tab Warfarin 5 mg once daily",
    "Tab Atorvastatin 20 mg HS",
    "Tab Clarithromycin 500 mg BD x 5 days",
    "Tab Glycomet 500 mg BD",
  ].join("\n");
  setMode("paste");
  dom.prescriptionInput.value = sample;
  dom.chatgptText.value = sample;
  setSelectedDrugs(extractPrescriptionDrugs(sample));
  dom.manualInput.value = state.selectedDrugs.join(", ");
  updateExtractionStatus(state.selectedDrugs.length, true);
  resetDashboard("Sample loaded. Review the detected names, then run the check.");
});

dom.clearBtn.addEventListener("click", () => {
  dom.manualInput.value = "";
  dom.prescriptionInput.value = "";
  dom.chatgptText.value = "";
  clearPhoto({ silent: true });
  setSelectedDrugs([]);
  updateExtractionStatus(0, false);
  resetDashboard("Cleared. Add drug names to begin.");
});

dom.checkBtn.addEventListener("click", runCheck);
dom.copySummaryBtn.addEventListener("click", copyVisitSummary);
dom.whatsappShareBtn.addEventListener("click", shareWhatsApp);

setSelectedDrugs([]);
resetDashboard("Add drug names or paste prescription text to begin.");

// Disclaimer Modal logic
if (!localStorage.getItem("rxcheck_disclaimer_accepted")) {
  dom.disclaimerModal.showModal();
}
dom.acceptDisclaimerBtn.addEventListener("click", () => {
  localStorage.setItem("rxcheck_disclaimer_accepted", "true");
  dom.disclaimerModal.close();
});

function setMode(mode) {
  state.mode = mode;
  dom.modeTabs.forEach((tab) => {
    const active = tab.dataset.mode === mode;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });
  dom.entryPanels.forEach((panel) => panel.classList.toggle("active", panel.id.startsWith(mode)));

  const source = mode === "paste" ? dom.prescriptionInput.value : dom.manualInput.value;
  setSelectedDrugs(mode === "paste" ? extractPrescriptionDrugs(source) : parseManualInput(source));
}

function handlePhotoUpload(event) {
  const file = event.target.files?.[0];

  if (!file) {
    clearPhoto({ silent: true });
    return;
  }

  if (!file.type.startsWith("image/")) {
    dom.photoInput.value = "";
    showBanner("Choose an image file of the prescription.");
    return;
  }

  if (state.photoPreviewUrl) {
    URL.revokeObjectURL(state.photoPreviewUrl);
  }

  state.photoPreviewUrl = URL.createObjectURL(file);
  dom.photoPreviewImage.src = state.photoPreviewUrl;
  dom.photoPreview.classList.add("has-image");
  dom.photoStatus.textContent = file.name;
  dom.photoRemoveBtn.disabled = false;

  runOCR(file);
}

function clearPhoto(options = {}) {
  if (state.photoPreviewUrl) {
    URL.revokeObjectURL(state.photoPreviewUrl);
  }

  state.photoPreviewUrl = "";
  dom.photoInput.value = "";
  dom.photoPreviewImage.removeAttribute("src");
  dom.photoPreview.classList.remove("has-image");
  dom.photoStatus.textContent = "No image selected";
  dom.photoRemoveBtn.disabled = true;

  if (!options.silent) {
    hideBanner();
  }
}

function applyExtractedText(text) {
  const drugs = extractPrescriptionDrugs(text);
  dom.prescriptionInput.value = text;
  dom.manualInput.value = drugs.join(", ");

  if (state.mode !== "paste") {
    setMode("paste");
  } else {
    setSelectedDrugs(drugs);
  }

  updateExtractionStatus(drugs.length, Boolean(text.trim()));
}

async function preprocessImageForOCR(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      const ctx = canvas.getContext("2d");
      
      // Scale up small images for better OCR
      let scale = 1;
      if (img.width < 1000 || img.height < 1000) {
        scale = 2;
      }
      
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      
      // Draw and scale
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      
      // Grayscale & Thresholding (Contrast)
      const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;
      
      for (let i = 0; i < data.length; i += 4) {
        const r = data[i];
        const g = data[i + 1];
        const b = data[i + 2];
        
        // Grayscale (Luminance)
        const gray = 0.299 * r + 0.587 * g + 0.114 * b;
        
        // Simple contrast/threshold
        const threshold = 140; // Tuned for typical prescription photos
        const v = gray > threshold ? 255 : 0;
        
        data[i] = data[i + 1] = data[i + 2] = v;
      }
      
      ctx.putImageData(imageData, 0, 0);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => reject(new Error("Image load failed"));
    img.src = URL.createObjectURL(file);
  });
}

async function runOCR(file) {
  dom.photoStatus.textContent = "OCR: initializing...";
  try {
    const processedUrl = await preprocessImageForOCR(file);
    dom.photoStatus.textContent = "OCR: processing...";
    
    const worker = await Tesseract.createWorker("eng", 1, {
      logger: (info) => {
        if (info.status === "recognizing text") {
          const pct = Math.round((info.progress || 0) * 100);
          dom.photoStatus.textContent = `OCR: ${pct}%`;
        }
      },
    });
    const { data } = await worker.recognize(processedUrl);
    await worker.terminate();
    URL.revokeObjectURL(processedUrl); // Clean up if it was a blob URL, but it's data URI so this is a no-op but safe.

    const text = (data.text || "").trim();
    const confidence = data.confidence || 0;
    
    if (text) {
      dom.chatgptText.value = text;
      dom.photoStatus.textContent = "OCR complete";
      applyExtractedText(text);
      dom.extractBtn.click();
      
      if (confidence < 60) {
        showBanner("Low OCR confidence. Verify medicine names manually.");
      }
    } else {
      dom.photoStatus.textContent = "OCR: no text found";
    }
  } catch (err) {
    console.error("OCR failed", err);
    dom.photoStatus.textContent = "OCR failed";
    showBanner("Automatic text extraction failed. Paste the text manually.");
  }
}

function updateExtractionStatus(count, hasText) {
  if (!hasText) {
    dom.extractionStatus.textContent = "Paste extracted text to auto-fill the drug names below.";
    return;
  }

  dom.extractionStatus.textContent = `Detected ${count} possible medicine ${
    count === 1 ? "name" : "names"
  } and filled the drug list.`;
}

function parseManualInput(value) {
  const candidates = [];
  value.split(/[\n,+;]+/).forEach((item) => {
    const { cleaned } = cleanPrescriptionLine(item);
    if (cleaned) candidates.push(cleaned);
  });
  return uniqueDrugs(candidates);
}

function extractPrescriptionDrugs(value) {
  const candidates = [];
  let hasLowConfidence = false;
  
  // 1. Insert spaces between letters and numbers (e.g., Telmisartan40mg -> Telmisartan 40mg)
  let text = value.replace(/([a-zA-Z])(\d)/g, "$1 $2");
  
  // 2. Line grouping for broken OCR
  let rawLines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  let groupedLines = [];
  
  for (let line of rawLines) {
    if (groupedLines.length > 0) {
      const prev = groupedLines[groupedLines.length - 1];
      // Merge if current line starts with a number, or is a common continuation (dosage/shorthand),
      // or if previous line ended with a continuation character
      if (/^\d/.test(line) || /^(mg|mcg|g|ml|bd|od|tds|sos)\b/i.test(line) || /[+\-&]$/.test(prev)) {
        groupedLines[groupedLines.length - 1] += " " + line;
        continue;
      }
    }
    groupedLines.push(line);
  }

  // 3. Safe segment splitting using word boundaries
  groupedLines.forEach(line => {
    line.split(/\.|\band\b|\+|&/i)
      .map(seg => seg.trim())
      .filter(Boolean)
      .forEach(seg => {
        const { cleaned, confidence } = cleanPrescriptionLine(seg);
        if (cleaned) {
          candidates.push(cleaned);
          if (confidence === "low") {
            hasLowConfidence = true;
          }
        }
      });
  });
  
  if (hasLowConfidence && candidates.length > 0) {
    showBanner("Some medicine names may need manual correction.");
  }
  
  return uniqueDrugs(candidates);
}

function cleanPrescriptionLine(line) {
  const normalized = line
    .replace(/\([^)]*\)/g, " ")
    .replace(/\b\d+(\.\d+)?\s*(mg|mcg|g|gm|ml|iu|units?|%|tabs?|tablets?|caps?)\b/gi, " ")
    .replace(/\b(sr|xr|cr|er|pr|mr|xl)\b/gi, " ")
    .replace(/\b\d+\s*-\s*\d+\s*-\s*\d+\b/g, " ")
    .replace(/\b\d+\/\d+(\/\d+)?\b/g, " ")
    .replace(/\b\d+\b/g, " ")
    .replace(/[^\w\s-]/g, " ") // keep hyphens
    .replace(/\s+/g, " ")
    .trim();

  // Extract Indian prescription shorthand before stop words remove it
  let shorthand = "";
  const shorthandMap = {
    od: "Once daily",
    bd: "Twice daily",
    bid: "Twice daily",
    tds: "Three times daily",
    tid: "Three times daily",
    qid: "Four times daily",
    sos: "As needed",
    hs: "At bedtime",
    mane: "In the morning",
    nocte: "At night",
    stat: "Immediately"
  };
  const rawWords = normalized.split(/\s+/);
  for (const w of rawWords) {
    const lw = w.toLowerCase().replace(/[^\w]/g, "");
    if (shorthandMap[lw]) {
      shorthand = shorthandMap[lw];
      break; // Just take the first valid frequency
    }
  }

  const words = rawWords
    .filter((word) => word.length > 1)
    .filter((word) => !PRESCRIPTION_STOP_WORDS.has(word.toLowerCase()));

  if (!words.length) {
    return { cleaned: "", confidence: "none" };
  }

  const formatCleaned = (name) => shorthand ? `${name} (${shorthand})` : name;

  // Exact brand match
  const knownBrand = words.find((word) => BRAND_HINTS[word.toLowerCase()]);
  if (knownBrand) {
    return { cleaned: formatCleaned(titleCase(knownBrand)), confidence: "high" };
  }
  
  // Fuzzy brand / generic match
  const match = words.find(w => {
     const lw = w.toLowerCase();
     return BRAND_HINTS[lw] || PRICE_CATALOG[lw] || 
       Object.values(BRAND_HINTS).some(v => v.includes(lw));
  });
  if (match) {
    const lw = match.toLowerCase();
    const resolved = BRAND_HINTS[lw] || match;
    return { cleaned: formatCleaned(titleCase(resolved)), confidence: "high" };
  }

  // Fallback guess
  return { cleaned: formatCleaned(titleCase(words.slice(0, 2).join(" "))), confidence: "low" };
}

function cleanDrugText(text) {
  return text
    .replace(/\([^)]*\)/g, " ")
    .replace(/\b\d+(\.\d+)?\s*(mg|mcg|g|gm|ml|iu|units?|%)\b/gi, " ")
    .replace(/[^\w\s+-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function uniqueDrugs(items) {
  const seen = new Set();
  const drugs = [];
  items.forEach((item) => {
    const key = item.toLowerCase();
    if (key && !seen.has(key)) {
      seen.add(key);
      drugs.push(titleCase(item));
    }
  });
  return drugs.slice(0, 14);
}

function setSelectedDrugs(drugs) {
  state.selectedDrugs = drugs;
  renderChips();
  renderSaveMoneyTable(drugs);
}

function renderChips() {
  dom.chipList.innerHTML = "";
  dom.drugCount.textContent = `${state.selectedDrugs.length} selected`;

  if (!state.selectedDrugs.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No medicines detected yet.";
    dom.chipList.append(empty);
    return;
  }

  state.selectedDrugs.forEach((drug) => {
    const chip = dom.chipTemplate.content.firstElementChild.cloneNode(true);
    chip.querySelector(".chip-name").textContent = drug;
    chip.setAttribute("aria-label", `Remove ${drug}`);
    chip.addEventListener("click", () => {
      setSelectedDrugs(state.selectedDrugs.filter((item) => item !== drug));
      syncActiveInput();
    });
    dom.chipList.append(chip);
  });
}

function syncActiveInput() {
  dom.manualInput.value = state.selectedDrugs.join(", ");
}

async function runCheck() {
  if (state.checkController) {
    state.checkController.abort();
  }
  state.checkController = new AbortController();
  const signal = state.checkController.signal;

  const drugs = state.selectedDrugs.length
    ? state.selectedDrugs
    : state.mode === "paste"
      ? extractPrescriptionDrugs(dom.prescriptionInput.value)
      : parseManualInput(dom.manualInput.value);

  setSelectedDrugs(drugs);

  if (drugs.length < 2) {
    resetDashboard("Add at least two medicines for an interaction check.");
    showBanner("At least two drug names are needed to check interactions.");
    return;
  }

  const signature = drugs.join("|").toLowerCase();
  state.lastInputSignature = signature;

  setLoading(true);
  hideBanner();
  dom.dashboardTitle.textContent = "Checking prescription...";
  dom.apiState.textContent = "Contacting RxNorm";
  dom.interactionSource.textContent = "Resolving names";
  dom.interactionResults.className = "result-list empty-state";
  dom.interactionResults.innerHTML = "<p>Normalizing drug names with RxNorm...</p>";
  dom.drugResults.className = "drug-results empty-state";
  dom.drugResults.innerHTML = "<p>Preparing generic alternatives...</p>";

  try {
    const resolved = await Promise.all(drugs.map(d => resolveDrug(d, signal)));
    if (signal.aborted || signature !== state.lastInputSignature) {
      return;
    }

    const onlineInteractions = await fetchOnlineInteractions(resolved, signal);
    if (signal.aborted) return;
    
    const localFindings = evaluateLocalInteractions(resolved);
    const findings = mergeFindings(onlineInteractions.findings, localFindings);
    const summary = summarizeFindings(findings, resolved.length);

    renderDashboard(summary, findings, resolved, onlineInteractions);
  } catch (error) {
    if (error.name === "AbortError") return;
    console.error(error);
    showBanner("Something went wrong while checking. Try again, or verify the drug names manually.");
    dom.apiState.textContent = "Check failed";
  } finally {
    if (!signal.aborted) {
      setLoading(false);
    }
  }
}

async function resolveDrug(rawName, signal) {
  const mappedName = mapBrandHint(rawName);
  const catalogMatch = findCatalogEntry(`${rawName} ${mappedName}`);
  const fallback = {
    rawName,
    queryName: mappedName,
    rxcui: "",
    rxName: titleCase(mappedName),
    tty: "local",
    ingredients: catalogMatch ? [catalogMatch.display] : [titleCase(mappedName)],
    genericName: catalogMatch?.display || titleCase(mappedName),
    alternatives: catalogMatch?.alternatives || [`${titleCase(mappedName)} generic equivalent`],
    priceRange: catalogMatch?.range || "Rs. 40-250 per strip or pack",
    confidence: catalogMatch ? "Local catalog match" : "Unverified estimate",
    lookupStatus: "offline fallback",
  };

  try {
    const rxcui = await findRxcui(mappedName, signal);
    if (!rxcui) {
      return fallback;
    }

    const [properties, generic, relatedIngredients] = await Promise.all([
      getProperties(rxcui, signal),
      getGenericProduct(rxcui, signal),
      getRelatedByType(rxcui, "IN+PIN", signal),
    ]);

    const rxName = properties?.name || generic?.name || titleCase(mappedName);
    const ingredientNames = relatedIngredients.length
      ? relatedIngredients.map((item) => item.name)
      : [deriveIngredientName(rxName, mappedName)];
    const catalog = findCatalogEntry(`${rxName} ${ingredientNames.join(" ")} ${mappedName}`) || catalogMatch;
    const genericName = generic?.name || catalog?.display || ingredientNames[0] || rxName;
    const alternatives = buildAlternativeList(genericName, catalog, rxName);

    return {
      rawName,
      queryName: mappedName,
      rxcui,
      rxName,
      tty: properties?.tty || generic?.tty || "RxNorm",
      ingredients: ingredientNames,
      genericName,
      alternatives,
      priceRange: catalog?.range || "Rs. 40-250 per strip or pack",
      confidence: properties?.name ? "RxNorm normalized" : "RxNorm matched",
      lookupStatus: "online",
    };
  } catch (error) {
    console.warn(`RxNorm lookup failed for ${rawName}`, error);
    return fallback;
  }
}

function levenshteinDistance(a, b) {
  if (a.length === 0) return b.length;
  if (b.length === 0) return a.length;
  
  const matrix = Array(b.length + 1).fill(null).map(() => Array(a.length + 1).fill(null));
  
  for (let i = 0; i <= a.length; i++) matrix[0][i] = i;
  for (let j = 0; j <= b.length; j++) matrix[j][0] = j;
  
  for (let j = 1; j <= b.length; j++) {
    for (let i = 1; i <= a.length; i++) {
      const indicator = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[j][i] = Math.min(
        matrix[j][i - 1] + 1, // insertion
        matrix[j - 1][i] + 1, // deletion
        matrix[j - 1][i - 1] + indicator // substitution
      );
    }
  }
  return matrix[b.length][a.length];
}

function mapBrandHint(name) {
  const cleaned = cleanDrugText(name).toLowerCase();
  const first = cleaned.split(/\s+/)[0];
  
  if (BRAND_HINTS[cleaned]) return BRAND_HINTS[cleaned];
  if (BRAND_HINTS[first]) return BRAND_HINTS[first];
  
  const catalogKeys = Object.keys(PRICE_CATALOG);
  const hintKeys = Object.keys(BRAND_HINTS);
  
  let minDistance = Infinity;
  let bestMatch = cleaned;
  
  for (const key of [...hintKeys, ...catalogKeys]) {
    const d1 = levenshteinDistance(cleaned, key);
    const d2 = levenshteinDistance(first, key);
    const d = Math.min(d1, d2);
    
    // Strict threshold: Max distance 2, and the word must be at least 6 chars long to allow distance 2.
    // Distance 1 allowed for 4+ chars.
    const threshold = key.length > 5 ? 2 : key.length >= 4 ? 1 : 0;
    
    if (d <= threshold && d < minDistance) {
      minDistance = d;
      bestMatch = BRAND_HINTS[key] || key; 
    }
  }
  
  return bestMatch;
}

async function findRxcui(name, signal) {
  const normalizedUrl = `${RXNORM_BASE}/rxcui.json?name=${encodeURIComponent(name)}&search=2`;
  const normalized = await getJson(normalizedUrl, 9000, 2, signal);
  const exactIds = normalized?.idGroup?.rxnormId || [];
  if (exactIds.length) {
    return exactIds[0];
  }

  const approximateUrl = `${RXNORM_BASE}/rxcui.json?name=${encodeURIComponent(name)}&search=9`;
  const approximate = await getJson(approximateUrl, 9000, 2, signal);
  return approximate?.idGroup?.rxnormId?.[0] || "";
}

async function getProperties(rxcui, signal) {
  const data = await getJson(`${RXNORM_BASE}/rxcui/${encodeURIComponent(rxcui)}/properties.json`, 9000, 2, signal);
  return data?.properties || null;
}

async function getGenericProduct(rxcui, signal) {
  const data = await getJson(`${RXNORM_BASE}/rxcui/${encodeURIComponent(rxcui)}/generic.json`, 9000, 2, signal);
  const concepts = data?.minConceptGroup?.minConcept || [];
  return concepts[0] || null;
}

async function getRelatedByType(rxcui, tty, signal) {
  const data = await getJson(
    `${RXNORM_BASE}/rxcui/${encodeURIComponent(rxcui)}/related.json?tty=${tty}`,
    9000, 2, signal
  );
  const groups = data?.relatedGroup?.conceptGroup || [];
  return groups.flatMap((group) => group.conceptProperties || []);
}

async function fetchOnlineInteractions(resolved, signal) {
  const rxcuis = resolved.map((drug) => drug.rxcui).filter(Boolean);
  if (rxcuis.length < 2) {
    return {
      status: "skipped",
      message: "Not enough RxCUIs were resolved for the live interaction route.",
      findings: [],
    };
  }

  const url = `${RXNORM_BASE}/interaction/list.json?rxcuis=${rxcuis.join("+")}`;

  try {
    const data = await getJson(url, 6500, 2, signal);
    const findings = parseOnlineInteractions(data);
    return {
      status: findings.length ? "online" : "empty",
      message: findings.length
        ? "RxNav live interaction response plus local rules."
        : "RxNav live interaction route returned no usable findings; local rules used.",
      findings,
    };
  } catch (error) {
    if (error.name !== "AbortError") {
      console.info("Live interaction endpoint unavailable", error);
    }
    return {
      status: "unavailable",
      message: "Live interaction service unavailable. Using local safety rules.",
      findings: [],
    };
  }
}

function parseOnlineInteractions(data) {
  const groups = data?.fullInteractionTypeGroup || [];
  const findings = [];

  groups.forEach((group) => {
    (group.fullInteractionType || []).forEach((type) => {
      (type.interactionPair || []).forEach((pair) => {
        const names = (pair.interactionConcept || [])
          .map((concept) => concept.minConceptItem?.name)
          .filter(Boolean);
        if (names.length < 2) {
          return;
        }

        const level = normalizeSeverity(pair.severity || pair.sourceDisclaimer);
        findings.push({
          level,
          pair: names.slice(0, 2),
          message: pair.description || "Interaction listed by RxNav response.",
          action: level === "high" ? "Review urgently with a clinician." : "Monitor and confirm clinical intent.",
          source: "RxNav",
        });
      });
    });
  });

  return findings;
}

function normalizeSeverity(value = "") {
  const text = value.toLowerCase();
  if (text.includes("high") || text.includes("contra") || text.includes("major")) {
    return "high";
  }
  if (text.includes("moderate") || text.includes("significant")) {
    return "medium";
  }
  return "medium";
}

function evaluateLocalInteractions(resolved) {
  const findings = [];

  for (let i = 0; i < resolved.length; i += 1) {
    for (let j = i + 1; j < resolved.length; j += 1) {
      const left = resolved[i];
      const right = resolved[j];
      INTERACTION_RULES.forEach((rule) => {
        const forward = matchesAny(left, rule.a) && matchesAny(right, rule.b);
        const reverse = matchesAny(left, rule.b) && matchesAny(right, rule.a);
        if (forward || reverse) {
          findings.push({
            level: rule.level,
            pair: [left.rawName, right.rawName],
            message: rule.message,
            action: rule.action,
            source: "Local safety rules",
          });
        }
      });
    }
  }

  return findings;
}

function matchesAny(drug, terms) {
  const haystack = [
    drug.rawName,
    drug.queryName,
    drug.rxName,
    drug.genericName,
    ...drug.ingredients,
    ...drug.alternatives,
  ]
    .join(" ")
    .toLowerCase();

  return terms.some((term) => {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(^|\\W)${escaped}(\\W|$)`, "i").test(haystack);
  });
}

function mergeFindings(online, local) {
  const map = new Map();
  [...online, ...local].forEach((finding) => {
    const pairKey = finding.pair.map((name) => name.toLowerCase()).sort().join("|");
    const key = `${pairKey}|${finding.message.toLowerCase()}`;
    if (map.has(key)) {
      const existing = map.get(key);
      if (existing.source !== finding.source) {
        existing.source = "Both";
      }
    } else {
      map.set(key, { ...finding });
    }
  });
  return Array.from(map.values());
}

function summarizeFindings(findings, drugCount) {
  const high = findings.filter((item) => item.level === "high").length;
  const medium = findings.filter((item) => item.level === "medium").length;
  const low = high || medium ? 0 : Math.max(0, (drugCount * (drugCount - 1)) / 2);
  return { high, medium, low };
}

function renderDashboard(summary, findings, resolved, onlineInteractions) {
  dom.greenCount.textContent = summary.low;
  dom.yellowCount.textContent = summary.medium;
  dom.redCount.textContent = summary.high;

  const statusText = resolved.every((drug) => drug.lookupStatus === "online")
    ? "RxNorm lookup complete"
    : "RxNorm plus local fallback";
  dom.apiState.textContent = statusText;

  const highest = summary.high ? "red" : summary.medium ? "yellow" : "green";
  dom.dashboardTitle.textContent =
    highest === "red"
      ? "⚠ Dangerous interaction signals found"
      : highest === "yellow"
        ? "⚠ Caution signals detected"
        : "✓ No known dangerous interactions";

  dom.interactionSource.textContent = onlineInteractions.message;
  if (onlineInteractions.status === "unavailable") {
    showBanner(onlineInteractions.message);
  } else {
    hideBanner();
  }

  renderInteractionResults(findings, resolved);
  renderDrugCards(resolved);

  state.lastFindings = findings;
  state.lastResolved = resolved;
  state.lastSummary = summary;

  dom.shareToolbar.classList.remove("hidden");
}

function renderInteractionResults(findings, resolved) {
  dom.interactionResults.className = "result-list";
  dom.interactionResults.innerHTML = "";

  if (!findings.length) {
    const pairs = Math.max(0, (resolved.length * (resolved.length - 1)) / 2);
    dom.interactionResults.classList.add("empty-state");
    dom.interactionResults.innerHTML = `<p>Safe result for ${pairs} checked pair${pairs === 1 ? "" : "s"}: no interaction was found in the available checks.</p>`;
    return;
  }

  const hasHighRisk = findings.some(f => f.level === "high");
  if (hasHighRisk) {
    const warning = document.createElement("div");
    warning.className = "emergency-warning";
    warning.innerHTML = `<strong>Consult Your Doctor Immediately</strong>
      We found potentially dangerous interactions. Do not combine these medications without urgent medical advice.`;
    dom.interactionResults.append(warning);
  }

  findings
    .sort((a, b) => riskWeight(b.level) - riskWeight(a.level))
    .forEach((finding) => {
      const card = document.createElement("article");
      card.className = "interaction-card";
      card.innerHTML = `
        <span class="risk-stripe ${finding.level}" aria-hidden="true"></span>
        <div class="interaction-body">
          <div class="interaction-topline">
            <div class="interaction-title">${escapeHtml(finding.pair.join(" + "))}</div>
            <span class="badge ${finding.level}">${riskLabel(finding.level)}</span>
          </div>
          <p>${escapeHtml(finding.message)}</p>
          <p><strong>Suggested next step:</strong> ${escapeHtml(finding.action)}</p>
          <div class="meta-row">
            <span class="meta-chip">${escapeHtml(finding.source)}</span>
          </div>
        </div>
      `;
      dom.interactionResults.append(card);
    });
}

function renderSaveMoneyTable(selectedDrugs = state.selectedDrugs) {
  const selectedText = selectedDrugs.join(" ");
  const rows = BRAND_SAVINGS_LOOKUP.map((item) => ({
    ...item,
    matched: matchesSavingsRow(item, selectedText),
  })).sort((a, b) => Number(b.matched) - Number(a.matched) || a.brand.localeCompare(b.brand));
  const matchCount = rows.filter((row) => row.matched).length;

  dom.saveMoneySummary.textContent = matchCount
    ? `${matchCount} prescription ${matchCount === 1 ? "match" : "matches"} highlighted`
    : "30 common Indian brands";
  dom.saveMoneyResults.innerHTML = "";

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.className = row.matched ? "match-row" : "";
    tr.innerHTML = `
      <td>
        <strong>${escapeHtml(row.brand)}</strong>
        ${row.matched ? "<small>Found in current prescription</small>" : ""}
      </td>
      <td>${escapeHtml(row.generic)}</td>
      <td><span class="mrp-value">${escapeHtml(row.mrp)}</span></td>
      <td><span class="saving-cue">${escapeHtml(row.cue)}</span></td>
    `;
    dom.saveMoneyResults.append(tr);
  });
}

function matchesSavingsRow(item, selectedText) {
  if (!selectedText.trim()) {
    return false;
  }

  const haystack = normalizeLookupText(selectedText);
  const brand = normalizeLookupText(item.brand);
  const generic = normalizeLookupText(item.generic);
  const brandLead = brand.split(" ")[0];
  const genericLead = generic.split(" ")[0];

  return (
    hasLookupToken(haystack, brand) ||
    hasLookupToken(haystack, brandLead) ||
    hasLookupToken(haystack, genericLead)
  );
}

function hasLookupToken(haystack, needle) {
  if (!needle || needle.length < 3) {
    return false;
  }

  return ` ${haystack} `.includes(` ${needle} `);
}

function normalizeLookupText(value) {
  return String(value)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function renderDrugCards(resolved) {
  dom.drugResults.className = "drug-results";
  dom.drugResults.innerHTML = "";

  resolved.forEach((drug) => {
    const card = document.createElement("article");
    card.className = "drug-card";
    const ingredientText = drug.ingredients.length ? drug.ingredients.join(", ") : "Not found";
    
    // Map confidence text to badge color
    const confLower = (drug.confidence || "").toLowerCase();
    let badgeClass = "low"; // default green
    let confBadgeText = "High Confidence";
    if (confLower.includes("unverified") || confLower.includes("guess")) {
      badgeClass = "high"; // red
      confBadgeText = "Low Confidence";
    } else if (confLower.includes("match") && !confLower.includes("normalized")) {
      badgeClass = "medium"; // yellow
      confBadgeText = "Medium Confidence";
    }
    
    card.innerHTML = `
      <div class="drug-topline">
        <div>
          <div class="drug-title">${escapeHtml(drug.rawName)}</div>
          <p>${escapeHtml(drug.confidence)}${drug.rxcui ? `, RxCUI ${escapeHtml(drug.rxcui)}` : ""}</p>
        </div>
        <span class="badge ${badgeClass}">${confBadgeText}</span>
      </div>
      <dl>
        <dt>RxNorm name</dt>
        <dd>${escapeHtml(drug.rxName)}</dd>
        <dt>Ingredients</dt>
        <dd>${escapeHtml(ingredientText)}</dd>
        <dt>Generic options</dt>
        <dd>${escapeHtml(drug.alternatives.join(", "))}</dd>
        <dt>India estimate</dt>
        <dd class="price">${escapeHtml(drug.priceRange)}</dd>
      </dl>
      <div class="meta-row">
        ${confBadgeText === "Low Confidence" ? '<span class="meta-chip" style="color:var(--red-dark); border-color:var(--red-soft); background:var(--red-soft)">Verify Name! Guessed from OCR.</span>' : ""}
        <span class="meta-chip">Confirm brand, dose, and salt locally</span>
        <span class="meta-chip">Do not substitute without prescriber approval</span>
      </div>
    `;
    dom.drugResults.append(card);
  });
}

function buildAlternativeList(genericName, catalog, rxName) {
  const list = [genericName];
  if (catalog?.alternatives) {
    list.push(...catalog.alternatives);
  }
  if (rxName && rxName !== genericName) {
    list.push(rxName);
  }
  return [...new Set(list.filter(Boolean))].slice(0, 4);
}

function deriveIngredientName(rxName, fallback) {
  const beforeDose = rxName.split(/\b\d+(\.\d+)?\s*(MG|MCG|G|ML|UNT|%)\b/i)[0].trim();
  const cleaned = beforeDose.replace(/\s+(oral|tablet|capsule|solution|injection).*$/i, "").trim();
  return cleaned || titleCase(fallback);
}

function findCatalogEntry(text) {
  const haystack = text.toLowerCase();
  const normalizedHaystack = haystack.replace("paracetamol", "acetaminophen");
  const key = Object.keys(PRICE_CATALOG).find((item) => {
    const escaped = item.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(^|\\W)${escaped}(\\W|$)`, "i").test(normalizedHaystack);
  });
  return key ? PRICE_CATALOG[key] : null;
}

const CACHE_TTL = 7 * 24 * 60 * 60 * 1000; // 7 days

function getCachedJson(url) {
  try {
    const cached = localStorage.getItem(url);
    if (cached) {
      const parsed = JSON.parse(cached);
      if (Date.now() - parsed.timestamp < CACHE_TTL) {
        return parsed.data;
      }
      localStorage.removeItem(url); // Expired
    }
  } catch (err) {
    console.warn("Cache read failed", err);
  }
  return null;
}

function cacheJson(url, data) {
  try {
    localStorage.setItem(url, JSON.stringify({
      timestamp: Date.now(),
      data: data
    }));
  } catch (err) {
    console.warn("Cache write failed, possible quota exceeded", err);
  }
}

async function getJson(url, timeout = 9000, maxRetries = 2, externalSignal = null) {
  const cached = getCachedJson(url);
  if (cached) return cached;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeout);
    
    const abortHandler = () => controller.abort();
    if (externalSignal) {
      externalSignal.addEventListener("abort", abortHandler);
    }
    
    try {
      if (externalSignal && externalSignal.aborted) throw new Error("Aborted");
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      cacheJson(url, data);
      return data;
    } catch (err) {
      if ((err.name === "AbortError" || err.message === "Aborted") && externalSignal && externalSignal.aborted) {
        throw err;
      }
      if (attempt === maxRetries) throw err;
      await new Promise(r => setTimeout(r, Math.pow(2, attempt) * 500));
    } finally {
      window.clearTimeout(timer);
      if (externalSignal) {
        externalSignal.removeEventListener("abort", abortHandler);
      }
    }
  }
}

function resetDashboard(message) {
  dom.dashboardTitle.textContent = "Awaiting a prescription";
  dom.apiState.textContent = "RxNorm not contacted yet";
  dom.greenCount.textContent = "0";
  dom.yellowCount.textContent = "0";
  dom.redCount.textContent = "0";
  dom.interactionSource.textContent = "No check run";
  dom.interactionResults.className = "result-list empty-state";
  dom.interactionResults.innerHTML = `<p>${escapeHtml(message)}</p>`;
  dom.drugResults.className = "drug-results empty-state";
  dom.drugResults.innerHTML = "<p>Drug cards will appear after RxNorm lookup.</p>";
  dom.shareToolbar.classList.add("hidden");
  hideBanner();
}

function setLoading(isLoading) {
  dom.dashboard.classList.toggle("loading", isLoading);
  dom.checkBtn.disabled = isLoading;
  dom.checkBtn.textContent = isLoading ? "Checking..." : "Check interactions";
}

function showBanner(message) {
  dom.alertBanner.textContent = message;
  dom.alertBanner.classList.remove("hidden");
}

function hideBanner() {
  dom.alertBanner.textContent = "";
  dom.alertBanner.classList.add("hidden");
}

function riskWeight(level) {
  return { low: 1, medium: 2, high: 3 }[level] || 0;
}

function riskLabel(level) {
  return {
    high: "Dangerous",
    medium: "Caution",
    low: "Safe",
  }[level];
}

function titleCase(value) {
  return value
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => {
      if (word.length <= 3 && word === word.toUpperCase()) {
        return word;
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(" ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function generateVisitSummary() {
  const drugs = state.selectedDrugs;
  if (!drugs.length) {
    return "No medicines have been entered yet.";
  }

  const lines = [];
  lines.push(`Patient is taking: ${drugs.join(", ")}.`);

  if (state.lastFindings.length) {
    const interactionLines = state.lastFindings.map((f) => {
      const label = riskLabel(f.level);
      return `${f.pair.join(" + ")} (${label})`;
    });
    lines.push(`Potential interaction${state.lastFindings.length > 1 ? "s" : ""} flagged: ${interactionLines.join("; ")}.`);
  } else if (state.lastSummary) {
    lines.push("No known drug interactions were found.");
  }

  const selectedText = drugs.join(" ");
  const matchedRows = BRAND_SAVINGS_LOOKUP.filter((item) => matchesSavingsRow(item, selectedText));
  if (matchedRows.length) {
    const totalEstimate = matchedRows.reduce((sum, row) => {
      const match = row.mrp.match(/Rs\.\s*(\d+)/);
      return sum + (match ? parseInt(match[1], 10) : 0);
    }, 0);
    if (totalEstimate > 0) {
      lines.push(`Generic savings available: ~Rs.${totalEstimate} potential saving (ask your pharmacist about generic alternatives).`);
    }
  }

  lines.push("");
  lines.push("Generated by RxCheck — rxcheck.app");
  return lines.join("\n");
}

async function copyVisitSummary() {
  const summary = generateVisitSummary();
  try {
    await navigator.clipboard.writeText(summary);
    dom.copySummaryBtn.textContent = "✓ Copied!";
    setTimeout(() => {
      dom.copySummaryBtn.textContent = "📋 Copy doctor visit summary";
    }, 2000);
  } catch (err) {
    console.error("Clipboard API failed, using fallback", err);
    const ta = document.createElement("textarea");
    ta.value = summary;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    dom.copySummaryBtn.textContent = "✓ Copied!";
    setTimeout(() => {
      dom.copySummaryBtn.textContent = "📋 Copy doctor visit summary";
    }, 2000);
  }
}

async function shareWhatsApp() {
  if (state.selectedDrugs.length === 0) {
    showBanner("Add medicines first before sharing.");
    return;
  }
  const summary = generateVisitSummary();
  
  if (navigator.share) {
    try {
      await navigator.share({
        title: 'RxCheck Summary',
        text: summary
      });
      return;
    } catch (err) {
      if (err.name !== "AbortError") {
        console.warn("navigator.share failed, falling back to WhatsApp URL", err);
      } else {
        return; // user cancelled
      }
    }
  }

  const url = `https://wa.me/?text=${encodeURIComponent(summary)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}
