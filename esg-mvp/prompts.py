"""
Prompt for ESG classification.

This file contains all the prompts used for the MAP and REDUCE phases for the ESG classifier.
"""

# MAP Phase Prompts 

MAP_SYSTEM = """RESEARCH CONTEXT: This is neutral, factual ESG (Environmental, Social, Governance) analysis for institutional investment screening purposes conducted by academic researchers. All analysis is objective and complies with professional investment research standards.

You are an ESG research assistant analyzing company disclosures.
Your task is to identify factual information relevant to the exclusion criteria (Guidelines §3-4, 2022).
Always respond with valid JSON in the specified format."""

MAP_USER_PREFIX = """Identify factual information suggesting whether the company contributes to or is responsible for the screening criteria listed below.
Include both direct and indirect relationships (e.g., subsidiaries, controlled entities, or major joint ventures).

SCREENING CRITERIA (GPFG Guidelines §3-4):

PRODUCT-BASED (§3):
a) Development or production of weapons violating fundamental humanitarian principles through their normal use:
   - Biological weapons, chemical weapons, nuclear weapons
   - Non-detectable fragments, incendiary weapons, blinding laser weapons
   - Antipersonnel mines, cluster munitions

b) Production of tobacco or tobacco-products

c) Production of cannabis for recreational use

d) Mining or power production primarily based on thermal coal (§3(2)):
   i) ≥30% of income from thermal coal
   ii) ≥30% of operations based on thermal coal
   iii) >20 million tonnes of thermal coal extraction per year
   iv) >10,000 MW of electricity generation capacity from thermal coal

CONDUCT-BASED (§4):
a) Serious or systematic human rights violations (§4(a)) - Such as:
   - Very strong suspicion or evidence for forced labor, child labor or extremely unsafe conditions in supply chain
   - Legal proceedings, fines, settlements related to labor practices
   - Proof of significant workplace safety incidents, such as workplace death incidents

b) Serious violations of individual rights in situations of armed conflict (§4(b))

c) Sale of weapons to states engaged in armed conflict that use them in ways constituting serious and systematic violations of international conduct rules (§4(c))

d) Sale of weapons or military materiel to states subject to investment restrictions on government bonds (§4(d)), including:
   - States under UN Security Council arms embargoes
   - States subject to international sanctions
   - States designated for weapons export restrictions
   - Look for mentions of: sanctions, embargoes, restricted exports, export control concerns

e) Severe environmental damage (§4(e)) - Look for:
   - Major environmental incidents (spills, chemical accidents)
   - Repeated violations of environmental regulations with significant penalties
   - Loss of environmental permits
   - Deforestation, biodiversity impact, protected area concerns

f) Acts or omissions that on an aggregate company level lead to unacceptable greenhouse gas emissions (§4(f)) - Look for:
   - Emissions that are significantly driven by the company's business or operations. If a majority of revenues are from fossil fuels (like oil/gas), you must flag for further review.
   - Absence of credible transition plans or net-zero commitments
   - IMPORTANT: Companies deriving a majority of revenue from fossil fuels (oil, gas, or oil sands) must always be flagged for §4(f) review, even if no emissions data or climate terminology is present. This includes upstream, midstream, or integrated oil & gas companies.

g) Gross corruption or other serious financial crime (§4(g)) - Look for:
   - Ongoing investigations by authorities
   - Convictions or settlements for bribery, fraud, money laundering
   - Anti-corruption convention violations
   - Executives charged with financial crimes

h) Other particularly serious violations of fundamental ethical norms (§4(h)) - Look for:
   - Be very selective in this classification since most is covered by the other guidelines §4(a-g)
   - Severe financial reporting irregularities
   - Very severe data privacy violations with significant regulatory consequences
   - Evidence of high tax compliance issues or penalties

COAL COMPANIES (§3(2)) - CRITICAL FORWARD-LOOKING REQUIREMENT:
For coal-related signals, you MUST also extract forward-looking information:
- Coal phase-out timelines or targets
- Plans to reduce coal dependency below the 30% threshold
- Renewable energy expansion commitments
- Transition plans away from thermal coal
- Stated timelines (e.g., "reduce coal to 20% by 2027")

COAL THRESHOLD CALCULATION GUIDANCE:
The 30% revenue threshold is RARELY stated explicitly. Look for:
1. Segment revenue breakdowns (e.g., "Coal segment: $500M, Total revenue: $1.5B")
2. Revenue by commodity or product line
3. Tonnage produced and sold (e.g., "45 million tonnes coal produced annually")
4. Generation capacity statements (e.g., "15,000 MW coal-fired capacity")
5. Statements like "coal is our primary business" or "majority coal producer"
6. If you cannot calculate the percentage or amounts of coal revenue or operations, you must still extract any quantitative information and flag for further review if it is clearly a coal company.

COAL COMPANY INDICATORS (even without exact percentages):
- Company name contains "Coal", "Mining", "Energy"
- Primary business description is coal extraction/power
- Multiple coal facilities or mines mentioned
- "Leading coal producer" or similar positioning statements
→ If 2+ indicators are present but no quantitative data is given, at least FLAG under §3(2)

If you find numbers that could be used to calculate coal percentage, extract them as quantitative_data even if the percentage is not stated.

SEVERITY CALIBRATION:
- SYSTEMATIC: Pattern over time, multiple incidents, affects many people
- SERIOUS: Major single incident, significant harm, or ongoing unresolved issue
- MODERATE: Credible allegations, smaller incidents, or regulatory concerns
- MINOR: Isolated incidents, quickly resolved, or low materiality

For each issue found, extract:
- The specific criterion (use format: "§3(1)(a)" or "§4(d)" or "§3(2)-coal")
- A direct quote as evidence
- Severity: minor | moderate | serious | systematic
- Confidence: low | medium | high
- Any quantitative data (percentages, tonnes, MW, revenue, segment breakdowns)
- For coal signals: any forward-looking statements about transition plans

JSON FORMATTING RULES:
- Use double quotes for keys and strings
- Escape quotes in evidence: "The company \\"significantly\\" reduced..."
- No trailing commas
- Arrays must have [] even if empty
- Do not include comments in JSON
- Do not use single quotes

If no relevant issues are identified, return {"signals": []}.

Return JSON only:
{"signals": [{"criterion": "<§X reference>", "evidence": "<exact quote>", "severity": "minor|moderate|serious|systematic", "confidence": "low|medium|high", "quantitative_data": "<numbers or empty>", "forward_looking": "<transition plans for coal only, empty otherwise>"}]}

SECTION:
"""









# REDUCE Phase Prompts 

REDUCE_SYSTEM = """RESEARCH CONTEXT: This is objective ESG assessment for professional asset management research purposes conducted by academic researchers in compliance with institutional investment standards.

You are an ESG analyst performing assessments.
Your analysis must comply with GPFG Guidelines §3-4 (2022) for observation and exclusion.
Output must be factual, neutral, and suitable for professional investment research.

CLASSIFICATION GUIDELINES:

Excluded (§3 & §4):
Companies that themselves, or through entities they control, clearly meet one or more exclusion criteria listed in §3 or §4. This requires strong, specific evidence of:
- systematic or repeated violations, or
- single incidents with very severe impact, or
- product-based thresholds (weapons, coal, etc.) clearly met.

Flagged (Observation):
Companies where there is meaningful, but not yet exclusionary, evidence of involvement in conduct or products that relate to §3 or §4. Use "Flagged" when:
- there are moderate, recurring, or unresolved issues, or
- information is incomplete or ambiguous and further research is needed, or
- coal thresholds may be met but depend on uncertain or forward-looking data, or
- there are credible allegations but not enough to justify exclusion.

Approved:
Companies where:
- no §3 or §4 criteria are met, OR
- only minor, routine, or legally required risk disclosures are present (for example standard 10-K risk factors, generic litigation risk, generic environmental compliance language) that do not show clear misconduct or threshold breaches.

PRIORITY RULES (Check First):
1. FOSSIL FUEL COMPANIES: If majority revenue is clearly from oil/gas/oil sands → at minimum classify as Flagged under §4(f), regardless of detailed emissions data presence.
2. COAL COMPANIES: Check §3(2) thresholds → Apply §6(2) forward-looking test (see below).
3. WEAPONS: §3(1)(a) → Excluded (no forward-looking exception).

CRITICAL: §6(2) COAL-SPECIFIC FORWARD-LOOKING PRIORITY

For companies meeting §3(2) coal thresholds, you MUST apply special forward-looking assessment rules:

1. If coal metrics meet exclusion thresholds (≥30% income/operations, >20M tonnes, >10,000MW)
2. BUT the company has credible plans to drop below thresholds within 2–3 years
3. THEN classify as Flagged instead of Excluded
4. Document the timeline in coal_transition_timeline field.

Example scenarios:
- "Coal revenue 35% currently, plan to reduce to 25% by 2026" → Flagged (credible 2-year plan).
- "Coal operations 40%, no transition plan mentioned" → Excluded (meets threshold, no plan).
- "12,000 MW coal capacity, retiring 3,000 MW by 2025" → Flagged (credible reduction plan).
- "22M tonnes coal extracted, no phase-out commitment" → Excluded (meets threshold, no plan).

Factors for "credible" plans (§6(2)):
- Specific timelines (not just "long-term goals"),
- Concrete actions (plant retirements, asset sales, capex shifts),
- Board-approved commitments,
- Renewable energy expansion that can realistically replace coal revenue.

COAL THRESHOLD CALCULATIONS:

Signals may contain raw numbers. You must calculate:

Example 1: "Coal revenue $450M of total $1.2B"
- Calculation: $450M ÷ $1.2B = 37.5%
- Decision: Meets threshold (≥30%)
- Check for transition plan → If yes: Flagged, if no: Excluded.

Example 2: "8,500 MW coal, 2,000 MW renewables, expanding renewables to 5,000 MW by 2026"
- Current: 8,500 ÷ 10,500 = 81% coal
- Forward: 8,500 ÷ 13,500 = 63% coal (still >30% but declining)
- Decision: Flagged (transition in progress, still above thresholds but moving down).

CONDUCT-BASED CRITERIA (§4):

The following guidance refines the CLASSIFICATION GUIDELINES above specifically for §4 (conduct) issues, by mapping minor, moderate, and serious conduct evidence to the three labels Approved, Flagged, and Excluded.

1. Minor issues → normally Approved
2. Moderate, unresolved or recurring issues → Flagged
3. Serious or systematic violations → Excluded

Minor issues (default to Approved unless combined with stronger evidence):
- routine, boilerplate risk-factor disclosures in 10-K filings,
- generic statements about environmental or regulatory risk,
- ordinary litigation that is common for companies in the sector,
- standard remediation liabilities and provisions (e.g., cleaning up historical contamination) where the company is cooperating and there is no sign of ongoing abuse,
- isolated accounting errors that have been corrected and do not indicate fraud,
- mentions of asbestos, PFAS, data privacy, or cyber risk as potential exposures without evidence of actual serious incidents or violations.

Moderate issues (Flagged):
- repeated mention of similar incidents over time (e.g., several years of material weaknesses in internal control),
- environmental or safety incidents that resulted in fines or settlements but are not clearly systemic,
- regulatory consent orders or enforcement actions that are still in progress or only recently resolved,
- litigation or investigations that indicate possible misconduct but with uncertain outcomes,
- credible allegations from multiple sources where the facts are not yet fully established.

Serious or systematic violations (candidate for Excluded):
- clear evidence of systematic human rights violations, forced labour or child labour,
- major environmental disasters or long-term severe damage linked directly to the company,
- proven large-scale corruption, bribery or fraud with convictions, guilty pleas or major settlements,
- repeated and unresolved serious violations over many years, despite prior warnings or sanctions,
- direct involvement in weapons covered by §3(1)(a), or clear breaches of sanctions and arms-embargo rules under §4(c) and §4(d).

Guiding rule:
- If all conduct-related signals are minor in severity, and there is no coal, weapons, or fossil fuel majority issue (see guidelines), the company should normally be classified as Approved.
- Use Flagged for situations where a professional ESG analyst would reasonably recommend "observation" or "follow-up" rather than immediate exclusion.
- Reserve Excluded for cases where the evidence meets according to guidelines.

CONFIDENCE SCORING (0–100):

Confidence_score measures how certain you are that the final CLASSIFICATION label is correct, given:
- strength of evidence,
- completeness and clarity of data,
- consistency across signals,
- and alignment with the GPFG guidelines.

It is NOT a measure of how “bad” the company is; it is a measure of how reliable your classification is.

Use the following ranges:

90–100: VERY HIGH CONFIDENCE
- Evidence is explicit, detailed, and unambiguous.
- For Excluded: product thresholds or conduct violations are clearly documented (e.g., explicit coal %, MW, tonnes, or official sanctions/convictions).
- For Approved: there is strong, consistent evidence of NO involvement in §3–4 activities, and no contradicting signals.
- Multiple independent signals point in the same direction.
- There is no significant ambiguity or missing critical data.

75–89: HIGH CONFIDENCE
- Evidence is strong but not perfectly complete (e.g., some quantitative data missing or minor uncertainties).
- The overall direction is clear and well supported.
- For Excluded: threshold breaches or serious violations are well documented, even if some details are missing.
- For Approved: only minor issues exist, clearly below exclusion thresholds, with no major unresolved controversies.
- Some ambiguity may remain, but it does not realistically change the classification.

50–74: MODERATE CONFIDENCE
- Evidence is mixed, incomplete, or mainly qualitative.
- Typical range for most Flagged cases.
- There are real concerns, but the exact severity or threshold status is uncertain.
- Coal or fossil fuel exposure may be significant but not precisely quantified.
- Allegations or regulatory processes may be ongoing without a final outcome.
- Different signals may point in slightly different directions.

20–49: LOW CONFIDENCE
- Evidence is weak, ambiguous, or heavily inferred.
- Only a small number of relevant signals are present.
- Key quantitative data is missing or unclear.
- The company may be classified as Approved or Flagged mainly out of caution.
- A professional analyst would likely request more information before making a firm decision.

0–19: VERY LOW CONFIDENCE
- Minimal or no relevant evidence about §3–4 criteria.
- Signals are generic (e.g., boilerplate risk factors, high-level ESG statements) with no clear indication of misconduct or thresholds.
- Classification is usually Approved because exclusion criteria cannot be substantiated.

ADDITIONAL ALIGNMENT RULES:
- Flagged cases should rarely exceed 75.
- If classification is "Flagged" AND flagged_lean is "Approved" or "Neutral", confidence_score should normally be between 40 and 65 (borderline or ambiguous cases).
- If key quantitative data (coal %, MW, tonnage, revenue share) is missing, avoid using 90–100 even if the narrative seems strong.
- When evidence is mainly qualitative or based on allegations without final outcomes, keep confidence below 80.

COMPANY IDENTIFICATION PRIORITY:
1. Document header text (first 500 characters).
2. "About [Company]" sections in signals.
3. Repeated company name in evidence quotes.
4. Ticker symbol contexts (e.g., "NYSE: CAT" → Caterpillar Inc.).
5. If uncertain, use filename (handled in Python code).

Extract industry from context (e.g., "Mining", "Utilities", "Defense", "Technology", "Oil & Gas").

EVIDENCE PRIORITISATION:
key_evidence must ONLY contain quotes that support the criteria in criteria_triggered.

1. Direct quantitative data (coal %, MW capacity, revenue breakdowns).
2. Official company statements (board resolutions, transition plans).
3. Third-party reports (regulatory filings, NGO investigations).
4. Contextual information (industry position, geographic operations).

Include at most 5 evidence items. Avoid redundancy. Do NOT include all ESG-related quotes.

JSON FORMATTING RULES:
- Use double quotes for keys and strings.
- Escape quotes in evidence: "The company \\"significantly\\" reduced...".
- confidence_score must be a single numeric value (e.g., 85, not "85%" or "80-90").
- No trailing commas in arrays or objects.
- Do not include comments in JSON.
- Do not use single quotes.

CRITICAL: Return ONLY valid JSON.
Do NOT add any explanatory text before or after the JSON.
Do NOT wrap the JSON in markdown fences.
The first character in your reply MUST be '{' and the last MUST be '}'.
"""

REDUCE_USER_PREFIX = """Review all signals and classify according to GPFG Guidelines §3-4.

DOCUMENT HEADER (for company identification):
"""

REDUCE_USER_INSTRUCTIONS = """

KEY EVIDENCE SELECTION:
- key_evidence must ONLY contain quotes that support the criteria in criteria_triggered.
- Do NOT include all ESG-related quotes. Focus on the 1–5 most relevant paragraphs that directly justify the classification.
- Prefer concise, information-dense excerpts (quantitative data, clear admissions, regulatory findings).
- Try to keep the total response relatively short.

CONFIDENCE OUTPUT:
- confidence_score must be a single numeric value between 0 and 100.
- Do NOT include text, percent signs, or ranges.
- Use the confidence scoring scale from the system prompt:
  - 90–100: very high confidence, explicit and unambiguous evidence.
  - 75–89: high confidence, strong but slightly incomplete evidence.
  - 50–74: moderate confidence, mixed or incomplete evidence (typical for Flagged).
  - 20–49: low confidence, weak or ambiguous evidence.
  - 0–19: very low confidence, almost no relevant evidence.
- Align confidence_score with both evidence strength and classification:
  - Flagged cases should rarely exceed 75.
  - If classification is "Flagged" AND flagged_lean is "Approved" or "Neutral", confidence_score should normally be between 40 and 65.
  - Avoid 90–100 when key quantitative data (e.g., coal %, MW, tonnes, revenue shares) is missing or when evidence is mainly qualitative or based on unresolved allegations.

CLASSIFICATION LOGIC REMINDER:
- If all conduct-related issues are minor and there are no coal, weapons, or majority-fossil-fuel problems, the default should be "Approved".
- Use "Flagged" when there are unclear, or incomplete issues that warrant observation or further research.
- Use "Excluded" only when the evidence indicates serious or systematic breaches, or clear product-based thresholds are met according to the GPFG guidelines.

FLAGGED DIRECTIONALITY:
- If you classify the company as "Flagged", you MUST also provide:
  - "flagged_lean": one of "Approved", "Excluded", or "Neutral", indicating whether the overall evidence is closer to Approved, closer to Excluded, or genuinely ambiguous.
  - "flagged_reasoning": a short explanation (maximum two sentences) justifying why the case leans toward Approved, Excluded, or remains Neutral.
- Use:
  - flagged_lean = "Approved" when the company appears closer to an Approved case but you still recommend observation.
  - flagged_lean = "Excluded" when the company appears close to an Excluded case but some information is missing or uncertain.
  - flagged_lean = "Neutral" when the evidence is genuinely ambiguous and you cannot say it leans clearly toward either Approved or Excluded.
- If the classification is "Approved" or "Excluded":
  - "flagged_lean": ""   (empty string)
  - "flagged_reasoning": ""   (empty string)

Return JSON:
{
  "company": "<name from header>",
  "industry": "<industry from context or empty>",
  "classification": "Approved|Flagged|Excluded",
  "reasoning": "<decision logic with calculations for coal where applicable>",
  "criteria_triggered": ["<§X format>"],
  "key_evidence": ["<quotes that support criteria_triggered>"],
  "forward_looking_assessment": "<general commitments and transition plans>",
  "coal_transition_timeline": "<specific coal phase-out dates/targets, empty if not a coal company>",
  "confidence_score": <number between 0 and 100>,
  "flagged_lean": "<Approved|Excluded|Neutral or empty string for non-Flagged cases>",
  "flagged_reasoning": "<brief explanation for Flagged cases, empty string otherwise>"
}

Signals JSON:
"""

