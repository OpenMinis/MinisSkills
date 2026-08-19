// Amber theme template — prepended to pandoc typst output
// Font fallback: DejaVu Sans (Latin/half-width digits) → WenQuanYi Zen Hei (Chinese)
#let amber = rgb("#D97706")

// pandoc compatibility: horizontal rule
#let horizontalrule = line(length: 100%)

#set page(
  margin: (x: 2.5cm, y: 2cm),
  numbering: (x, y) => align(center)[#text(size: 8pt, fill: gray)[— #x —]],
)

#set text(
  font: ("DejaVu Sans", "WenQuanYi Zen Hei"),
  size: 11pt,
  lang: "zh",
)

#set par(leading: 0.8em)

// Headings
#show heading.where(level: 1): it => [
  #text(size: 18pt, weight: "bold")[#it.body]
  #v(-0.5em) #line(length: 100%, stroke: 2pt + amber) #v(0.3em)
]
#show heading.where(level: 2): it => [
  #text(size: 15pt, weight: "bold")[#it.body]
  #v(-0.3em) #line(length: 100%, stroke: 0.5pt + gray) #v(0.2em)
]
#show heading.where(level: 3): it => text(size: 13pt, weight: "bold")[#it.body]
#show heading.where(level: 4): it => text(size: 11.5pt, weight: "bold")[#it.body]

// Tables: amber header + zebra stripes + generous row height
#set table(
  stroke: 0.5pt + rgb("#d2d4d7"),
  inset: (top: 12pt, bottom: 12pt, left: 8pt, right: 8pt),
  fill: (x, y) => if y == 0 { amber } else if calc.even(y) { rgb("#f7f8fa") },
)
// Header: block preserves padding (a plain text show rule drops cell inset)
#show table.cell.where(y: 0): it => block(
  inset: (top: 12pt, bottom: 12pt, left: 8pt, right: 8pt),
)[#text(fill: white, weight: "bold")[#it.body]]

// Code blocks: gray background, monospace, full width
#show raw.where(block: true): it => block(
  width: 100%, fill: rgb("#f2f3f5"), inset: 0.8em, radius: 4pt,
  stroke: (top: 2pt + rgb("#d2d4d7")),
  text(size: 9.5pt, font: "DejaVu Sans Mono")[#it]
)
#show raw.where(block: false): it => box(
  fill: rgb("#ececed"), inset: (x: 0.4em, y: 0.15em), radius: 3pt,
  text(font: "DejaVu Sans Mono")[#it]
)

// Blockquotes: amber left bar, full width
#show quote.where(block: true): it => block(
  width: 100%, fill: rgb("#fef7ed"), inset: 1em,
  stroke: (left: 4pt + amber),
  text(size: 10pt, fill: rgb("#505050"))[#it]
)

// Link color
#show link: it => text(fill: amber)[#it]
