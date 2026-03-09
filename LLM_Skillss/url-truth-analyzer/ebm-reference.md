# EBM SORT Reference

**SORT = Strength Of Recommendation Taxonomy**
Developed for the *American Family Physician* journal to standardize how clinical evidence is graded and communicated.

---

## Core concept: POEMs vs DOEs

The most important distinction in SORT:

| Type | Full name | What it measures | Example |
|------|-----------|-----------------|---------|
| **POEM** | Patient-Oriented Evidence that Matters | Outcomes patients experience: mortality, morbidity, quality of life, symptom relief | "Drug X reduced heart attack deaths by 20%" |
| **DOE** | Disease-Oriented Evidence | Surrogate markers doctors measure | "Drug X reduced LDL cholesterol by 15 points" |

**Why it matters**: A drug can improve a DOE (lower cholesterol) without improving the POEM (survival). SORT rewards POEMs. A claim backed only by DOEs cannot exceed Grade B.

---

## SORT grading rules

### Grade A — Consistent, good-quality patient-oriented evidence
All of the following must be true:
- Evidence comes from RCTs, systematic reviews, or meta-analyses
- Outcomes are patient-oriented (POEMs), not just surrogate markers
- Results are consistent across multiple studies
- No serious risk of bias (independent funding, pre-registered, adequate blinding)

### Grade B — Limited or inconsistent patient-oriented evidence
Any of the following applies:
- RCT or systematic review exists, but with methodological limitations (small sample, short follow-up, industry funding)
- Evidence is patient-oriented but results are inconsistent across studies
- Good-quality evidence exists but only for disease-oriented outcomes (DOEs)
- Extrapolation from Grade A evidence to a different population or setting

### Grade C — Consensus, expert opinion, or disease-oriented evidence only
Any of the following applies:
- No RCTs; evidence comes from case series, case reports, or observational studies
- Claims rest solely on expert opinion, guidelines consensus, or usual clinical practice
- Mechanistic reasoning only ("this should work because of pathway X") with no clinical outcome data
- Animal or in vitro studies extrapolated to human outcomes

---

## Grading edge cases

| Situation | Grade |
|-----------|-------|
| Large, well-conducted RCT, but surrogate endpoint only | B |
| Systematic review of low-quality RCTs | B |
| Single high-quality RCT with POEM, not yet replicated | B |
| Consistent findings across 3+ independent RCTs with POEMs | A |
| Expert consensus with no trial data | C |
| Observational study showing association (not causation) | C |
| Mechanistic claim ("detox," "boosts immunity") with no trial | C |

---

## Four analysis lenses (how to apply them)

### 1. Safety lens
- Are absolute risks reported (e.g., "1 in 200 patients experienced X") or only relative risks ("50% reduction")?
- Relative risk without baseline rates is misleading. Flag it.
- Are harms, side effects, or contraindications mentioned or deliberately omitted?
- Is the number needed to harm (NNH) discussed alongside the number needed to treat (NNT)?

### 2. Outcomes lens
- Identify every outcome claimed in the transcript
- Label each as POEM or DOE
- If all outcomes are DOEs, the maximum grade is B regardless of study quality
- Watch for language that implies patient benefit from DOE results: "improves heart health" from a cholesterol number alone

### 3. Risk of bias lens

Rank study designs from most to least reliable:
1. Systematic review / meta-analysis of RCTs
2. Individual well-powered RCT (blinded, pre-registered, independent)
3. Cohort study (prospective > retrospective)
4. Case-control study
5. Cross-sectional study
6. Case series / case report
7. Expert opinion / anecdote

Additional bias signals to flag:
- Industry-funded study with positive results and no independent replication
- No conflict-of-interest disclosure
- Unpublished or preprint-only results
- Data dredging / p-hacking signals (many endpoints, post-hoc analysis)
- Lack of a control group or comparison arm

### 4. Total evidence lens
- Does the claim match or contradict established clinical guidelines (e.g., USPSTF, NICE, WHO)?
- Is the cited study an outlier in a field with many contradictory results?
- Has the claim been retracted, updated, or superseded?
- Is this an emerging finding with limited replication, or mature consensus?

---

## PubMed search instructions

Base URL: `https://pubmed.ncbi.nlm.nih.gov/`

Effective search patterns:
```
"[treatment/drug/intervention]"[Title/Abstract] AND "[condition]"[Title/Abstract] AND "randomized controlled trial"[Publication Type]
"[topic]" AND "systematic review"[Publication Type]
"[topic]" AND "meta-analysis"[Publication Type]
```

Filters to apply in the UI:
- Article types: Systematic Review, Meta-Analysis, Randomized Controlled Trial, Clinical Trial
- Publication date: last 10 years (unless looking for foundational studies)
- Full text available (for citing accessible links)

---

## Cochrane Library search instructions

Base URL: `https://www.cochranelibrary.com/`

- Use the search bar with condition + intervention terms
- Filter to **Cochrane Reviews** (not just protocols)
- Cochrane reviews are considered the gold standard for systematic evidence — a Cochrane review citing lack of evidence is itself significant and citable
- Use plain language summaries for quick orientation, full review for citation

---

## BMJ Evidence-Based Medicine

Base URL: `https://ebm.bmj.com/`

- Useful for critically appraised topics (CATs) and EBM-graded summaries
- Cite the DOI-linked article, not just the search result page

---

## Citation format

```
Author(s) Last, First. "Title of Article." Journal Name, vol. X, no. Y, Year, pp. Z–Z. URL or DOI.
```

Example:
```
Yusuf, S., et al. "Effect of potentially modifiable risk factors associated with myocardial infarction in 52 countries." The Lancet, vol. 364, 2004, pp. 937–952. https://pubmed.ncbi.nlm.nih.gov/15364185/
```

Always verify the link resolves before including it. Prefer PMC full-text links when available.
