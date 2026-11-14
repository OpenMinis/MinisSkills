# Surface Region legend and limits

SR means **Surface Region**, not “slope region”. Supplied regions retain existing `SR <room>.<index>` identifiers. Reconstructed zones use `SR reconstructed:<zoneKey>` and never impersonate a supplied face index. Registry entries record `origin`, `sourceRefs`, source face areas, and available geometry/height. Horizontal supplied faces remain intact.

CLI `--surface-region-groups <sidecar.json>` reads an explicit, source-SHA256-scoped override:

```json
{"sourceSHA256":"<exact input SHA256>","groups":[{"id":"K1","confirmation":"user-confirmed","members":["SR example.1","SR example.2"]}]}
```

A mismatched hash, unknown face, duplicate member, or cross-room/story group fails.
Without the flag the converter AUTO-DISCOVERS a sidecar beside the scan using only fixed names, most specific first:

1. `<scanDir>/<scanBase>.surface-region-groups.json`
2. `<projectDir>/surface-region-groups.json`
3. `<scanDir>/surface-region-groups.json` (for a scan at `data/scan.json`)

The same `sourceSHA256` gate applies. An explicit `--surface-region-groups` always wins over a discovered file. When two files exist the most specific one is used and `roomplan.surface-region-groups-sidecar-ambiguous` records the others. A discovered sidecar that cannot be read, is not a JSON object, or names a DIFFERENT source SHA256 is NOT applied: it is reported as `roomplan.surface-region-groups-sidecar-ignored` and conversion finishes with no groups, because a directory may legitimately hold a confirmation for another capture. An explicit path stays a hard error in that situation. Provenance is recorded as `surfaceRegions.groupsSource` (`mode` = `explicit` | `auto-discovered` | `none`, `path`, `relative`, `sourceSHA256`, `confirmedGroupCount`) in the report JSON and the Markdown line `Potvrda grupa:`; the sidecar warnings above travel with the other plan warnings into the `.roomplan.json` manifest. Nothing is inferred from a missing sidecar: no sidecar means no confirmed grouping, not a claim that the faces are not one slope.
 Without confirmation there is no confirmed grouping. A group retains all component faces; its area is a reference sum, never an additional quantity. Grouping does not flatten planes or delete horizontal caps, and it does not change any face's area. It records grouping metadata and computes the source-normal bend angle for two-face groups.

On the SHEET a confirmed group is drawn as ONE piece:

- the per-face SR labels are withdrawn and replaced by ONE group label — `SR 2.1-2.2  h 0.84-2.70` when the member ids form a series, otherwise the explicit `+` join — placed inside the stitched union of the member faces;
- ONE fall arrow is kept for the whole slope (the arrow of the largest member face); the other per-face fall arrows are withdrawn;
- the internal seam line is **not** drawn, and neither is the coincident perimeter line that both faces share — the group is outlined as one continuous union, not two adjacent polygons. The shared edge survives as data in `ceilingDiagnostics.surfaceRegionDraw[].seamWithdrawn` (`drawnOnSheet: false`), and the member faces stay in the registry with their areas unchanged. The `S<n>_CEILING_SEAM` layer remains defined in the layer table for compatibility but receives no entity. Manifest ceiling diagnostics, CLI report, Markdown references, CSV reference-only rows and USDZ root customData share one registry. CSV references leave quantity columns empty to avoid double counting. Standalone buildReport without the CLI does not construct this annotation registry.

The explicit source surface sum is retained only as a diagnostic (`surfaceAreaSumM2`): the reported ceiling quantity is the **plan-union envelope** (each square metre once, stacked duplicates add 0 m2), which is still **not a verified physical total**. Overlapping hypotheses remain unresolved; no minimum/maximum envelope is selected. User confirmation of one slope does not verify every other supplied face. Heights using supplied floor-level are not measured clear heights.

Room/storey titles contain name and area only, separated by ASCII spaces. Each reconstructed flat zone gets a regional height annotation; each split slope part gets its height. Layout sheet bounds include conservative text envelopes and unresolved annotations are moved to a reserved strip on their own story. Unresolved associations remain unresolved, without fabricated leaders. Font substitution and physical survey accuracy remain outside these guarantees.

Registry area sums are reference-only source-surface sums, never extra report
ceiling quantities. The report uses a plan-union envelope where supported;
when a footprint is unusable it explicitly falls back to a surface sum with
`usedFallback` and a warning. Group confirmation is a user assertion scoped
to the source hash, not independent physical verification.

## Source-region annotation contract (2026-11-08)

Moved verbatim out of `SKILL.md`; this is the current contract, not history.

- Explicit supplied ceiling polygons are retained as source regions, labelled
  `SR <room identifier>.<index>`. Read `sourceRegionId`, `interpretation`,
  `regionPlanM`, `worldCornersM` and `heightM` in ceiling diagnostics.
- Multiple supplied surfaces are alternatives that may overlap or conflict:
  `roomplan.ceiling-source-alternatives`. No minimum/maximum physical envelope
  is selected or verified. An individual region height is not a certified
  room-wide clear height; source regions are not additive physical quantities.
- **Ceiling accounting uses a plan-union ENVELOPE where available, not a
  naive surface sum.** Producers often
  emit several ceiling surfaces for one room that share the same plan footprint
  at different heights ("stacked"), or overlapping roof pieces; adding them
  double counted the same square metre (an anonymized regression example, 2026-11-08: one room carried
  three co-located surfaces and reported 3x its area; a second room reported
  41.74 m2 against a 19.64 m2 room). `ceilingArea` is the exact plan union of
  the supplied footprints (`scripts/lib/polygon-union.js`: x-sweep over split
  edges, no rasterisation, no bounding box), and only the exclusive part of a
  surface contributes, with its own developed-area tilt factor
  (`surfaceArea/planArea`, so a real slope keeps its extra area while a stacked
  duplicate adds 0 m2). Exclusive parts are assigned largest surface first;
  when overlapping surfaces have different tilts the developed area depends on
  that order and `roomplan.ceiling-envelope-order-sensitive` reports the
  bounds. The arithmetic surface sum is retained as a diagnostic
  (`surfaceAreaSumM2`, `overlapAreaM2`, `doubleCountAvoidedM2`) and the
  per-surface SR records, labels and heights are untouched — no surface is
  deleted or merged. A supplied surface with no plan extent (a vertical plane)
  makes the union undefined for that room: the surface sum is then reported
  with `usedFallback` and `roomplan.ceiling-envelope-unavailable`. On an anonymized regression example
  the envelope changed the ceiling total from 100.32 m2 (sum) to 69.65 m2
  (envelope), numerically matching the sum of the declared room areas. That
  agreement is not independent evidence of the built ceiling or room area.
- **Provenance is not physical verification.** `status: supplied` says where
  the input came from; `coverage: complete` says all expected source zones
  contributed, not that the building was measured completely. Largest-surface-
  first is an accounting convention, not a verified choice of the built face.
  Inspect conflicts, `orderSensitive`/`boundsM2`, and `usedFallback` in
  `manifest.ceilingDiagnostics.envelope` (room/total measures do not carry
  every diagnostic field). `orderSensitive` is a conservative tilt-difference
  flag (threshold 0.01), including disjoint faces; its bounds are broad
  source-derived bounds, not a measured physical interval. With a fallback the reported value is a surface
  sum, not a union. With conflicts or order dependence, report a conditional
  source-derived quantity and its limitations, never a verified physical total.
- Explicit horizontal source regions retain their thin gray outline and SR
  height label on `S<n>_CEILING_FLAT`; they are not orange slope bands.
  Reconstructed flat ceilings do not acquire a whole-room dashed slope outline.
- Layout tests a conservative TEXT envelope inside each polygon, then a local
  external callout with a checked leader. If neither fits, annotation remains
  visible with `UNRESOLVED` and `layoutStatus: unresolved-visible-no-leader`;
  no unsafe leader is fabricated. This is an unresolved association requiring
  review, not successful in-region placement. Arbitrary CAD font substitutions
  and full paper plotting remain outside this guarantee.
- Short downhill arrows are checked within the region; annotation offsets do
  not change source geometry or measurement quantities. Per-story framing
  translates geometry and text together once, after source-space alignment.
- `supplied-floor-level` is an explicitly supplied scalar fallback, not a
  measured floor plane. Positive separations up to 6 m can remain visible,
  including low heights; do not silently clamp them to plausible room heights.
- A structurally clean DXF requires audit `errors: 0` AND `fixes: 0`. It does
  not resolve source conflicts, low heights, unknown heights, unresolved labels
  or establish a verified physical envelope. Review diagnostics separately.
