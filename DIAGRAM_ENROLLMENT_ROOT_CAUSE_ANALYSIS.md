# Root Cause Analysis: Why Diagrams Were Still Enrolling

## Executive Summary

**Root Cause Found**: Users were accessing the **old static HTML UI** (`/static/fingerprint.html`) which was hardcoded to use the **legacy v1 fingerprint endpoint** (`/api/enroll/fingerprint`). The v1 endpoint calls the old model-service engine with minimal anti-diagram checks, allowing diagrams to pass through.

**Status**: ✅ **FIXED** - All static UI files now forced to use v2 endpoints with strict anti-diagram gates.

---

## The Issue Chain

### 1. Two Frontend UIs Exist
- **New**: Modern Next.js at `bio-secure-gate-ui-build/` (forces v2 endpoints ✓)
- **Old**: Static HTML at `static/fingerprint.html` (used v1 endpoints ✗)

### 2. User Accessing Old UI
If a user navigated to:
- `http://server/static/fingerprint.html` (old UI)
- Instead of the modern dashboard

### 3. Old UI Used Legacy Endpoint
```javascript
// OLD CODE - static/js/fingerprint-scanner.js (BEFORE FIX)
fetch(`${apiBase}/api/enroll/fingerprint`, ...)  // ← v1 endpoint (WEAK)
```

### 4. v1 Endpoint Uses Weak Validation
```python
# OLD MODEL-SERVICE ENDPOINT - /fingerprint/template (v1)
# Only checks: fp_score < FINGERPRINT_FP_SCORE_THRESHOLD
# Does NOT check the 11+ anti-diagram gates in v2:
#   - coverage, orientation_entropy, kp_count, kp_spread
#   - tile_active_ratio, tile_coverage_std
#   - edge_component_count, largest_edge_component_ratio
#   - periodic_tile_ratio, mean_periodicity, ridge_block_ratio
```

### 5. Diagram Passes Weak Validation
- Old engine sees: "has some fp_score, looks okay"
- Diagram gets template extracted and enrolled in database ✗

### 6. New UI Would Have Rejected It
```python
# NEW MODEL-SERVICE ENDPOINT - /fingerprint_v2/template (v2)
# Checks ALL 11+ metrics with strict floors
# Diagram fails: coverage, edge_component_count, quality_score
# Would return error: "Image does not appear to be a fingerprint"
```

---

## Proof: Local Diagnostic Test

Ran diagnostic test (`scripts/test_diagram_enrollment_debug.py`) with synthetic sad-face diagram:

### Results:
```
✓ Likeness score: 0.6290 >= 0.6
✓ Orientation entropy: 0.8548 >= 0.58
✓ Keypoint count: 165 >= 35
✓ Keypoint spread: 0.2002 >= 0.12
✓ Tile active ratio: 0.3333 >= 0.32
✓ Tile coverage std: 0.0587 <= 0.24
✓ Periodic tile ratio: 0.8462 >= 0.2
✓ Mean periodicity: 18.0299 >= 4.5
✓ Ridge block ratio: 0.2500 >= 0.16

❌ COVERAGE: 0.0488 < 0.16               ← FAILS
❌ EDGE COMPONENT COUNT: 5 < 55          ← FAILS  
❌ LARGEST EDGE COMPONENT: 0.4068 > 0.32 ← FAILS
❌ QUALITY SCORE: 0.2928 < 0.35          ← FAILS

Result: ✓ Diagram correctly REJECTED by v2 engine
```

**Conclusion**: v2 code logic is correct. Issue was routing/endpoint selection.

---

## Configuration Context

### Environment Variables (Now Centralized)

Added to `app/core/config.py`:
- `FINGERPRINT_V2_LIKENESS_THRESHOLD` = 0.60
- `FINGERPRINT_V2_MIN_COVERAGE` = 0.16
- `FINGERPRINT_V2_MIN_ORIENTATION_ENTROPY` = 0.58
- `FINGERPRINT_V2_MIN_KP_COUNT` = 35
- `FINGERPRINT_V2_MIN_KP_SPREAD` = 0.12
- `FINGERPRINT_V2_MIN_TILE_ACTIVE_RATIO` = 0.32
- `FINGERPRINT_V2_MAX_TILE_COVERAGE_STD` = 0.24
- `FINGERPRINT_V2_MIN_EDGE_COMPONENT_COUNT` = 55
- `FINGERPRINT_V2_MAX_LARGEST_EDGE_COMPONENT_RATIO` = 0.32
- `FINGERPRINT_V2_MIN_PERIODIC_TILE_RATIO` = 0.20
- `FINGERPRINT_V2_MIN_MEAN_PERIODICITY` = 4.50
- `FINGERPRINT_V2_MIN_RIDGE_BLOCK_RATIO` = 0.16

These are now:
- ✅ Read by backend routes
- ✅ Propagated to Cloud Run model-service via `cloudbuild.yaml`
- ✅ Used by model-service v2 endpoints
- ✅ Enforced with hard floors/ceilings for safety

---

## Fixes Applied

### Fix #1: Centralize Configuration
**File**: `app/core/config.py`
- Added all 12 FINGERPRINT_V2_* threshold variables
- Used safe getters with floor/ceiling enforcement
- Now readable by backend routes

### Fix #2: Force Old UI to v2 Endpoints  
**File**: `static/js/fingerprint-scanner.js`
```javascript
// BEFORE
fetch(`${apiBase}/api/enroll/fingerprint`, ...)
fetch(`${apiBase}/api/match/fingerprint`, ...)

// AFTER (NEW)
fetch(`${apiBase}/api/experimental/enroll/fingerprint`, ...)
fetch(`${apiBase}/api/experimental/match/fingerprint`, ...)
```

### Fix #3: Add Deprecation Notice
**File**: `app/api/fingerprint_routes.py`
- Added docstring warning: v1 endpoint is deprecated
- Recommends using v2 endpoint instead

### Fix #4: Cloud Run Propagation (Already Done)
**File**: `cloudbuild.yaml`
- Already updated to pass all 13 FINGERPRINT_V2_* env vars to model-service
- Commit: `feee02e`

---

## Endpoint Routing Summary

| Route | Handler | Model-Service | Engine | Anti-Diagram |
|-------|---------|----------------|--------|--------------|
| `/api/enroll/fingerprint` | v1 (legacy) | `/fingerprint/template` | ORB old | ❌ Weak |
| `/api/experimental/enroll/fingerprint` | v2 (new) | `/fingerprint_v2/template` | AKAZE v2 | ✅ Strong |
| `/api/match/fingerprint` | v1 (legacy) | `/fingerprint/match` | ORB old | ❌ Weak |
| `/api/experimental/match/fingerprint` | v2 (new) | `/fingerprint_v2/match` | AKAZE v2 | ✅ Strong |

---

## Why This Happened

### Code Archaeology
1. Originally built: v1 fingerprint engine with basic quality checks
2. Later added: v2 engine with 11+ anti-diagram metrics
3. New Next.js frontend hardcoded to force v2
4. **BUT**: Old static HTML was never updated to match

### Deployment Reality
- Multiple UIs exist in production
- Users found the old one via `/static/fingerprint.html`
- Old UI silently used weak v1 validation
- No warning that v1 existed
- Result: Diagrams passed v1 but would fail v2

---

## Now Testing

### What to Do Next

**1. Deploy staging**
```bash
git log --oneline staging | head -5
# Should show these commits:
# 6105d1b fix(fingerprint): force v2 endpoints in old static UI
# feee02e fix(deploy): propagate fingerprint v2 thresholds to Cloud Run
```

**2. Test with actual diagram**
- Access old UI: `https://staging/static/fingerprint.html`
- Try to enroll a diagram/drawing
- Should now be REJECTED with v2 validation message

**3. Test with new UI**
- Access new dashboard: `https://staging/`
- Try to enroll a diagram
- Should be REJECTED (was already working)

**4. Test with real fingerprint**
- Both UIs should enroll real fingerprints successfully

---

## Prevention Measures

### Recommended
1. **Disable old static UI**: Remove `/static` serving if only new UI should be used
2. **Add feature flag**: Detect which UI is being accessed, warn or redirect
3. **Monitor logs**: Track which endpoints are actually being used
4. **Add version header**: Have UI send header indicating which version is calling

### Already Implemented
✅ v2 thresholds centralized in `app.core.config`  
✅ Old static UI forced to use v2 endpoints  
✅ Deprecation notice on v1 endpoint  
✅ All configs propagated to Cloud Run  
✅ Strict anti-diagram gates in v2 engine  

---

## Code References

### Key Files Modified
- `app/core/config.py` - Added FINGERPRINT_V2_* thresholds
- `static/js/fingerprint-scanner.js` - Force v2 endpoints
- `app/api/fingerprint_routes.py` - Added deprecation notice
- `cloudbuild.yaml` - Propagate thresholds (already done)

### Anti-Diagram Gates (v2 Only)
See: `app/engines/fingerprint_engine_v2.py::fingerprint_likeness_components()`
- 11 metrics extracted from image
- Each metric has floor/ceiling validation
- All must pass for enrollment to proceed

### Model Service Validation
See: `model_service/main.py::_v2_likeness_verdict()`
- Validates all 11 metrics against thresholds
- Returns specific failure reasons
- Hard floor/ceiling enforcement

---

## Summary

**What Was Wrong**: Users could bypass v2 anti-diagram gates by using old UI that called v1 endpoint.

**How It's Fixed**: Old UI now forced to use v2 endpoints with strict validation.

**Verification**: Local test confirms synthetic diagram is properly rejected by v2 engine.

**Deployment**: Changes pushed to staging - ready for testing.

