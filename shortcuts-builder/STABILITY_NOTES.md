# STABILITY_NOTES

## Goal

Record the key principles that affect stability, reproducibility, and success rate.

## Stability-First Rules

- Prefer native system actions before considering external capabilities
- Prefer the minimal runnable action chain first, then add extra behavior
- Prefer a fixed target before considering dynamically chosen targets
- Prefer verified URIs / third-party capabilities before trying new routes
- Validate the draft first, then decide whether to sign

## Common Failure Sources

### 1. Unclear boundaries

Symptoms:
- The user states the target but not the write mode
- The user states the actions but not their order
- The user states what to record but not whether to open the target afterward

Handling:
- Clarify first; do not generate directly

### 2. Hand-calculated variable positions

Symptoms:
- `attachmentsByRange` is wrong
- URL or text variables show up empty

Handling:
- Always use `placeholder-range`

### 3. Filling in too many optional parameters at the start

Symptoms:
- Validation gets more complicated
- Abnormal behavior after import
- Reduced compatibility with third-party services

Handling:
- Generate the minimal runnable structure first, then add extension parameters

### 4. Going Hybrid too early

Symptoms:
- Native actions could do the job, yet URIs, external services, or scripts are introduced
- The route is more complex and costlier to maintain

Handling:
- Try native-first

### 5. Treating the signed artifact as the only validation point

Symptoms:
- Draft problems are not exposed until the very end

Handling:
- Validate locally first, then sign, then check the file header

## Reproducibility Requirements

- Use the same recipe for the same kind of request
- Use the same fragment skeleton for the same kind of recipe
- Read the same default environment from the environment profile
- If the route changes, explain clearly why in the notes
