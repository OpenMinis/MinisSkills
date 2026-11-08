# Surface Region legend and limits

SR means **Surface Region**, not “slope region”. Supplied regions retain existing `SR <room>.<index>` identifiers. Reconstructed zones use `SR reconstructed:<zoneKey>` and never impersonate a supplied face index. Registry entries record `origin`, `sourceRefs`, source face areas, and available geometry/height. Horizontal supplied faces remain intact.

CLI `--surface-region-groups <sidecar.json>` reads an explicit, source-SHA256-scoped override:

```json
{"sourceSHA256":"<exact input SHA256>","groups":[{"id":"K1","confirmation":"user-confirmed","members":["SR example.1","SR example.2"]}]}
```

A mismatched hash, unknown face, duplicate member, or cross-room/story group fails. Without confirmation there is no confirmed grouping. A group retains all component faces; its area is a reference sum, never an additional quantity. Grouping does not flatten planes, erase seams, or delete horizontal caps. This implementation records grouping metadata and computes the source-normal bend angle for two-face groups. Group outline/label rendering is not implemented: the original per-face SR labels remain. Manifest ceiling diagnostics, CLI report, Markdown references, CSV reference-only rows and USDZ root customData share one registry. CSV references leave quantity columns empty to avoid double counting. Standalone buildReport without the CLI does not construct this annotation registry.

The explicit source surface sum preserves multiplicity and is **not a verified physical total**. Overlapping hypotheses remain unresolved; no minimum/maximum envelope is selected. User confirmation of one slope does not verify every other supplied face. Heights using supplied floor-level are not measured clear heights.

Room/storey titles contain name and area only, separated by ASCII spaces. Each reconstructed flat zone gets a regional height annotation; each split slope part gets its height. Layout sheet bounds include conservative text envelopes and unresolved annotations are moved to a reserved strip on their own story. Unresolved associations remain unresolved, without fabricated leaders. Font substitution and physical survey accuracy remain outside these guarantees.
