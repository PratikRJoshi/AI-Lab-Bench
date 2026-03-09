---
name: url-truth-analyzer
description: Transcribes video/audio URLs and performs a truth-claim analysis. For medical content, applies EBM SORT analysis with peer-reviewed citations. For general science, validates claims and finds credible supporting or refuting videos from across the web. Use when the user mentions analyzing URLs, truth claims, transcribing videos, checking medical claims, or asks to process the watch-urls.md file.
---

# URL Truth Analyzer

## Workflow overview

1. Read `~/Documents/watch-urls.md`, collect URLs listed under `## Pending`
2. For each URL: transcribe → classify → analyze → output → cleanup
3. Update `watch-urls.md` when done

**Progress reporting**: At the start of processing each URL, output a status message to the user:
```
🔄 Processing URL 1 of N: <URL>
  ⏳ Step 1/5: Transcribing audio...
```

Update progress after each major step (transcribe, classify, analyze, save, cleanup).

---

## Step 1: Transcribe

**Progress indicator**: `⏳ Step 1/5: Transcribing audio...`

Run the shell command for each pending URL:

```bash
extract_audio --transcribe <URL>
```

Capture the full stdout as the transcript. If the command fails, note the error in the output file and skip to the next URL.

**After transcription completes**: Report `✓ Step 1/5: Transcription complete (N words)`

---

## Step 2: Classify the transcript

**Progress indicator**: `⏳ Step 2/5: Classifying content type...`

Read the transcript and determine the content type:

**Medical** — content is medical if it mentions any of:
- Diagnoses, symptoms, diseases, or conditions
- Drugs, supplements, dosages, or treatments
- Clinical trials, studies, or patient outcomes
- Surgery, procedures, or medical devices
- Claims about health benefits or risks

**General science** — everything else: physics, chemistry, biology, psychology, nutrition (non-clinical), technology, environment, astronomy, etc.

If genuinely ambiguous, classify as **General science** and note the ambiguity.

**After classification**: Report `✓ Step 2/5: Classified as [Medical | General Science]`

---

## Step 3a: Medical content — EBM SORT Analysis

**Progress indicator**: `⏳ Step 3/5: Performing EBM SORT analysis...`

Read [ebm-reference.md](ebm-reference.md) for the full rubric before starting.

EBM SORT = **Strength Of Recommendation Taxonomy**. It grades clinical recommendations based on the quality and type of evidence behind them. Apply in two passes:

### Pass 1 — Four analysis lenses

Work through the transcript using these four lenses (these are analytical dimensions, not the SORT acronym itself):

- **Safety**: What harms, side effects, or risks are mentioned or omitted? Are they quantified with absolute numbers (not just relative risk)?
- **Outcomes**: Are claims backed by *patient-oriented* evidence (POEMs — mortality, morbidity, quality of life) or only *disease-oriented* evidence (DOEs — lab values, imaging, biomarkers)? DOEs do not always translate to patient benefit.
- **Risks of bias**: What is the study design (RCT > cohort > case series > anecdote)? Who funded it? Is there cherry-picking, missing comparators, or undisclosed conflicts of interest?
- **Total evidence**: Is this claim consistent with or contradicted by the broader body of literature? Is the cited study an outlier?

### Pass 2 — Assign a SORT grade

Based on Pass 1, assign one of:

- **Grade A** — Consistent, good-quality patient-oriented evidence (POEMs from well-designed RCTs or systematic reviews)
- **Grade B** — Inconsistent or limited-quality patient-oriented evidence, or good-quality disease-oriented evidence only
- **Grade C** — Consensus, disease-oriented evidence, expert opinion, usual practice, or case series only

See `ebm-reference.md` for grade decision rules and edge cases.

**Peer-reviewed citations**: End the analysis with 3–5 real, specific citations from:
- PubMed (pubmed.ncbi.nlm.nih.gov)
- Cochrane Library (cochranelibrary.com)
- BMJ Evidence-Based Medicine (ebm.bmj.com)

Format each citation as: `Author(s), Title, Journal, Year — [link]`

---

## Step 3b: General science — Claim validation

**Progress indicator**: `⏳ Step 3/5: Validating science claims...`

1. **Extract claims**: List each distinct factual claim made in the transcript as a numbered bullet.

2. **For each claim**:
   - State whether the claim is **supported**, **contested**, or **refuted** by current scientific consensus
   - Briefly explain the mechanism or evidence that would prove or disprove it (e.g., reproducible experiment, peer consensus, physical law)
   - Note any important caveats, nuances, or missing context

3. **Find validation videos**: For each major claim, search the broader web (not limited to YouTube) for credible videos that demonstrate, validate, or refute it. Sources to consider:
   - YouTube channels: established science communicators (e.g., Veritasium, SciShow, PBS Space Time, Kurzgesagt, 3Blue1Brown)
   - Vimeo, university/institution portals, TED/TEDx
   - PBS, BBC, National Geographic, Smithsonian Channel clips
   - Conference talks from established institutions

   **Credibility filter**: Only link videos from verified, named creators or institutions. Skip videos that are anonymous, lack citations, or make extraordinary claims without evidence. Flag any claim where no credible video exists.

---

## Step 4: Output format

**Progress indicator**: `⏳ Step 4/5: Saving analysis...`

Save to `~/Documents/truth-analyses/YYYY-MM-DD-<slugified-video-title>.md`:

```markdown
# Truth Analysis: <Video Title>
**Source URL**: <URL>
**Analyzed**: YYYY-MM-DD
**Content type**: Medical | General Science

## Summary
<2–3 sentence overview of what the video claims>

## Analysis

### [Medical: SORT Analysis | Science: Claim Validation]
<Full analysis here>

## Evidence / Validation Links
<Citations or validation videos>

## Verdict
<One-paragraph plain-language summary of how trustworthy this content is>
```

**After saving**: Report `✓ Step 4/5: Analysis saved to ~/Documents/truth-analyses/YYYY-MM-DD-<slug>.md`

---

## Step 5: Cleanup downloaded files

**Progress indicator**: `⏳ Step 5/5: Cleaning up temporary files...`

The `extract_audio` command downloads video/audio files and creates working directories in the current working directory. After the analysis is complete, delete all downloaded files and folders to save disk space.

**What to keep:**
- The original URL (already in watch-urls.md)
- The truth analysis markdown file in `~/Documents/truth-analyses/`

**What to delete:**
- Any folders created by `extract_audio` (typically long hash-named directories)
- Any `.mp4`, `.mp3`, `.wav`, or `_transcription.txt` files in the working directory
- Any temporary files created during processing

**How to clean up:**
```bash
# Find and delete folders created by extract_audio (they have long hash-like names)
# Look in the current working directory for recently created folders
rm -rf <hash-folder-name>
```

**After cleanup**: Report `✓ Step 5/5: Cleanup complete. Kept: analysis file. Removed: N MB of temporary files.`

---

## Step 6: Update watch-urls.md

After processing each URL (including cleanup), remove it from `## Pending` and add it to the `## Processed` section with the analysis date.

**Rules for updating the Processed section:**
- If `## Processed` already exists in the file, append the new entry directly below the `## Processed` heading (before any existing processed entries), preserving everything else in the file unchanged.
- If `## Processed` does not exist, create it as a new section at the end of the file.
- Never create a duplicate `## Processed` heading.

The entry format is:
```
- <URL> (analyzed YYYY-MM-DD → truth-analyses/YYYY-MM-DD-<slug>.md)
```

**Final status**: Report `✅ Completed: <URL>`
