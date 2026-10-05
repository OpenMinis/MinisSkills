# Evidence types: the taxonomy and why it is drawn this way

The score only means something if the types are applied consistently, so this file is
the authority on what each type means, where the boundaries sit, and the tagging
mistakes that quietly inflate a score.

## The single dividing line

Every type answers one question: **can someone who is not in this conversation check
this item for themselves?**

- If yes → `official`, `paper`, `data`. Counts toward the score.
- If no → `internal`, `assertion`. Does not count.

Nothing else distinguishes them. Importance does not; a confidential board figure is
still `internal` no matter how much weight the user puts on it. Confidence does not;
an item the user is certain about is still `assertion` if there is no document.

This is why the score is not a quality judgement. It measures *auditability* — whether
the chain can be walked by someone else, later, without asking the original author.

## The five types

### `official`

A primary document from the body that owns the fact, or that body itself.

Counts: a regulator's published guidance; a standard; a filed annual report; a
certificate; a court record; a vendor's own released specification; the statistics
office that collected the numbers.

Does not count, though it often gets tagged this way:

- a news article *about* a report (secondary — cite the report)
- a summary or briefing that cites the report
- the company's own marketing copy describing its own product claim
- a screenshot of a document, unless the document itself is identified

When a secondary source names its primary, tag the primary and cite the secondary as
where the user found it. That keeps the chain walkable.

### `paper`

Peer-reviewed literature, or a dataset that states its method.

Counts: a journal article; a conference paper; a registered trial; a public dataset
with a documented collection method.

Does not count: a preprint with no review beyond the author's own; an abstract
without the paper; a citation of a citation. `paper` asserts that a paper exists and
was named — **not** that it is any good. Sample size, blinding, conflicts of interest
and replication are all outside this tool. If the decision depends on those, say so
explicitly instead of letting the type imply more than it earned.

### `data`

Raw material the user can re-run or re-inspect: logs, exports, instrument readings,
query output, a spreadsheet of primary measurements.

`data` is the strongest type when the numbers are primary and the collection is
undisputed, because anyone can recompute. It is worth noting what it is not: data
proves what was measured, not that the measurement answers the claim. A well-formed
export can be entirely irrelevant. If relevance is the weak point, say that — the
score will not.

### `internal`

The user's own records, notes, or undocumented internal numbers: support logs, sales
figures from a system only they can query, an internal memo, a conversation.

Not verifiable *from outside*, which is the only reason it does not count. This is
not a slur on internal evidence — for many private claims it is the only evidence
there is. The honest move when a chain leans on `internal` is to say so, then name
what would make it checkable: a published figure, a filed document, a method someone
else can repeat. When nothing can make it checkable, the claim stays unestablished,
and that is the correct outcome rather than a reason to re-tag.

### `assertion`

The claim restated, an opinion, a recollection, a forecast, or an item with no source
stated at all.

This is also the **default**: an item with no `@type` marker is treated as
`assertion`. That default is deliberate — an untagged item has, by definition, no
stated provenance, so the tool assumes the weakest case and lets the user strengthen
it. It is never the tool's job to infer a stronger type.

## Tagging rules

Syntax: `text@type:source`, for example
`"2025 QA audit report@official:QA dept"`. `source` is free text naming who issued
or holds the item. Both `@type` and `@type:source` are accepted; a bare `@word` that
is not a known type is left in the text, so it cannot silently vanish.

1. **One item, one type.** An item that is half document and half recollection is two
   items. Splitting is honest; picking the stronger half is not.
2. **Never round up.** The temptation is always upward — `assertion` to `internal`,
   `internal` to `official`. Each step up the ladder is a claim about provenance the
   user has to be able to defend.
3. **Tag from the artifact, not from the sentence.** "According to the 2024 annual
   report, revenue grew 30%" is `official` only if the report is identified; if the
   sentence merely asserts that a report says so, it is `assertion` until the report
   is named.
4. **The same item can be `internal` and important.** Do not re-tag to raise the
   score. A truthful score of 0 is more useful than a flattering 30.
5. **Name the source even when the type is weak.** `@internal:support inbox` tells a
   reader where to look; a bare `@internal` does not.

## Worked examples

| evidence as given | correct type | why |
|---|---|---|
| `2024 annual report, p.42@official:company filings` | `official` | primary document, identified |
| `a news story said the annual report shows growth` | `assertion` | the report itself is not named |
| `Smith et al. 2025, J. Clin. Invest.@paper:JCI` | `paper` | identifiable paper |
| `studies show it works` | `assertion` | no study named |
| `support inbox has no complaints@internal:support` | `internal` | real, but only checkable inside |
| `instrument log, 3 runs, raw csv available@data:lab` | `data` | re-runnable primary measurement |
| `our best estimate is 0.5%` | `assertion` | an estimate, not a record |

## Common mistakes and their effect

| mistake | effect on the score |
|---|---|
| Tagging "our records show" as `official` | inflates — internal records are the most common mis-tag |
| Tagging a secondary summary as `official` | inflates, and breaks the chain's walkability |
| Leaving a genuinely sourced item untagged | deflates — it silently counts as `assertion` |
| Merging a document and an opinion into one item | inflates, by giving the opinion the document's type |
| Splitting one document into several items to raise the ratio | inflates; one source is one item however many times it is quoted |
| Tagging a preprint as `paper` | inflates; note the review status in the text |

## Why there is no sixth type for "expert opinion"

Expert opinion is genuinely valuable and it is still not independently checkable —
that is what makes it opinion. Giving it its own counting type would reintroduce
exactly the ambiguity the taxonomy removes. Record it, name the expert, and let the
score treat it as what it is: an `assertion` with an author attached.
