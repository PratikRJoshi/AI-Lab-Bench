# Folder Depth Examples

Visual guide to understanding the 5-level depth limit for recursive folder scanning.

---

## ✅ ALLOWED: Depth 1 (flat folder)

```
/Users/pratik.joshi/Desktop/my-images/
├── photo1.jpg          ← Level 1
├── photo2.jpg          ← Level 1
└── photo3.jpg          ← Level 1
```

**Relative depth**: 1 level
**Status**: ✅ Allowed
**Analysis**: Standard flat folder processing

---

## ✅ ALLOWED: Depth 2 (common use case)

```
/Users/pratik.joshi/Desktop/study/
├── before/             ← Level 1
│   ├── img1.jpg        ← Level 2
│   └── img2.jpg        ← Level 2
└── after/              ← Level 1
    ├── img1.jpg        ← Level 2
    └── img2.jpg        ← Level 2
```

**Relative depth**: 2 levels
**Status**: ✅ Allowed
**Analysis**: Before/after structure detected, temporal comparison analysis

---

## ✅ ALLOWED: Depth 3 (organized research)

```
/Users/pratik.joshi/Documents/research/
├── experiment-1/       ← Level 1
│   ├── control/        ← Level 2
│   │   ├── baseline/   ← Level 3
│   │   │   └── *.jpg
│   │   └── followup/   ← Level 3
│   │       └── *.jpg
│   └── treatment/      ← Level 2
│       ├── baseline/   ← Level 3
│       │   └── *.jpg
│       └── followup/   ← Level 3
│           └── *.jpg
└── experiment-2/       ← Level 1
    └── ...
```

**Relative depth**: 3 levels
**Status**: ✅ Allowed
**Analysis**: Multi-group clinical trial structure, baseline vs followup comparison

---

## ✅ ALLOWED: Depth 4 (complex project)

```
/Users/pratik.joshi/Desktop/project/
└── data/                   ← Level 1
    └── 2024/               ← Level 2
        └── Q1/             ← Level 3
            └── January/    ← Level 4
                ├── img1.jpg
                └── img2.jpg
```

**Relative depth**: 4 levels
**Status**: ✅ Allowed
**Analysis**: Date-hierarchical organization, chronological analysis

---

## ✅ ALLOWED: Depth 5 (maximum allowed)

```
/Users/pratik.joshi/Desktop/archive/
└── project/                ← Level 1
    └── medical/            ← Level 2
        └── trials/         ← Level 3
            └── 2024/       ← Level 4
                └── study1/ ← Level 5
                    └── *.jpg
```

**Relative depth**: 5 levels
**Status**: ✅ Allowed (at limit)
**Analysis**: Maximum allowed depth, processes normally

---

## ❌ REJECTED: Depth 6 (exceeds limit)

```
/Users/pratik.joshi/Desktop/deep/
└── a/                      ← Level 1
    └── b/                  ← Level 2
        └── c/              ← Level 3
            └── d/          ← Level 4
                └── e/      ← Level 5
                    └── f/  ← Level 6 ❌
                        └── test.jpg
```

**Relative depth**: 6 levels
**Status**: ❌ REJECTED
**Error**: `(failed YYYY-MM-DD — folder structure exceeds maximum depth of 5 levels. Found: 6 levels)`

**Solution**: Flatten structure or split into multiple analysis runs

---

## ❌ REJECTED: Depth 10 (way too deep)

```
/Users/pratik.joshi/Documents/deeply-nested/
└── year/
    └── month/
        └── week/
            └── day/
                └── hour/
                    └── minute/
                        └── category/
                            └── subcategory/
                                └── type/
                                    └── subtype/
                                        └── image.jpg
```

**Relative depth**: 10 levels
**Status**: ❌ REJECTED
**Error**: `(failed YYYY-MM-DD — folder structure exceeds maximum depth of 5 levels. Found: 10 levels)`

**Solution**: Reorganize folder structure before analysis

---

## Edge Cases

### Empty intermediate folders (allowed)

```
/Users/pratik.joshi/Desktop/sparse/
├── level1/                 ← Empty folder
│   └── level2/             ← Empty folder
│       └── level3/         ← Has images
│           ├── img1.jpg
│           └── img2.jpg
└── other/
    └── img3.jpg
```

**Status**: ✅ Allowed (depth 3)
**Behavior**: Empty folders are skipped, images from all levels processed

---

### Mixed depth (uses deepest)

```
/Users/pratik.joshi/Desktop/mixed/
├── root-level.jpg          ← Depth 1
└── deep/
    └── nested/
        └── very/
            └── deep/
                └── image.jpg    ← Depth 5
```

**Status**: ✅ Allowed (depth 5, at limit)
**Behavior**: Depth check uses **maximum depth** found, not average

---

### No images in deep folder (still validated)

```
/Users/pratik.joshi/Desktop/no-images/
└── a/
    └── b/
        └── c/
            └── d/
                └── e/
                    └── f/          ← No images here
                        └── g/      ← Depth 7
```

**Status**: ❌ REJECTED (depth 7 exceeds limit)
**Note**: Depth check happens **before** image scanning for safety

---

## How Depth is Calculated

### Algorithm

```bash
# 1. Find deepest folder in tree
MAX_DEPTH=$(find /path/to/folder -type d -printf '%d\n' 2>/dev/null | sort -rn | head -1)

# 2. Count depth of base folder (count slashes)
BASE_DEPTH=$(echo "/path/to/folder" | tr -cd '/' | wc -c)

# 3. Calculate relative depth
RELATIVE_DEPTH=$((MAX_DEPTH - BASE_DEPTH))

# 4. Validate
if [ "$RELATIVE_DEPTH" -gt 5 ]; then
  echo "❌ REJECTED: Depth $RELATIVE_DEPTH exceeds limit of 5"
else
  echo "✅ ALLOWED: Depth $RELATIVE_DEPTH"
fi
```

### Example calculation

**Folder**: `/Users/pratik.joshi/Desktop/study/data/images/`

1. Deepest folder: `/Users/pratik.joshi/Desktop/study/data/images/` → count slashes = 7
2. Base folder: `/Users/pratik.joshi/Desktop/study/` → count slashes = 5
3. Relative depth: 7 - 5 = **2 levels** ✅

**Folder**: `/Users/pratik.joshi/Desktop/study/` with subfolder `a/b/c/d/e/f/`

1. Deepest folder: `/Users/pratik.joshi/Desktop/study/a/b/c/d/e/f/` → count slashes = 11
2. Base folder: `/Users/pratik.joshi/Desktop/study/` → count slashes = 5
3. Relative depth: 11 - 5 = **6 levels** ❌

---

## Tips for Organizing Folders

### ✅ Good: Semantic organization (depth 2-3)

```
medical-study/
├── participants/
│   ├── group-a/
│   │   └── *.jpg
│   └── group-b/
│       └── *.jpg
└── charts/
    └── *.png
```

**Why good**: Clear categories, easy to analyze, subfolder context meaningful

---

### ❌ Bad: Date hierarchy (depth 4-6)

```
archive/
└── 2024/
    └── 03/
        └── 29/
            └── morning/
                └── category/
                    └── *.jpg
```

**Why bad**: Excessive depth for organizational overhead, date info better in filename

**Better alternative**:
```
archive/
└── 2024-03-29/
    ├── morning/
    │   └── *.jpg
    └── afternoon/
        └── *.jpg
```

---

### ✅ Good: Comparison structure (depth 2)

```
product-claims/
├── before/
│   └── *.jpg
├── after/
│   └── *.jpg
└── charts/
    └── *.png
```

**Why good**: Before/after structure immediately understood by analysis

---

## Summary

| Depth | Status | Common use case |
|-------|--------|----------------|
| 0-1 | ✅ Allowed | Single folder, flat structure |
| 2 | ✅ Allowed | Before/after, categories |
| 3 | ✅ Allowed | Multi-group studies, time-series |
| 4 | ✅ Allowed | Complex projects, date hierarchies |
| 5 | ✅ Allowed | Maximum limit, still safe |
| 6+ | ❌ Rejected | Too deep, reorganize structure |

**Recommendation**: Keep depth ≤3 for best performance and clarity.
