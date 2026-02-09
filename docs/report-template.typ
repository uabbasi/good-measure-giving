// Formal Report Template for AMAL Scoring Rubric
// Used by pandoc: pandoc SCORING_RUBRIC.md -o SCORING_RUBRIC.pdf --pdf-engine=typst --template=report-template.typ

#let report(
  title: none,
  subtitle: none,
  date: none,
  body,
) = {

  // Page setup
  set page(
    paper: "us-letter",
    margin: (top: 1.2in, bottom: 1in, left: 1.15in, right: 1.15in),
    header: context {
      if counter(page).get().first() > 1 {
        set text(size: 8.5pt, fill: luma(120))
        grid(
          columns: (1fr, 1fr),
          align(left)[AMAL Scoring Methodology],
          align(right)[Confidential],
        )
        v(-4pt)
        line(length: 100%, stroke: 0.4pt + luma(180))
      }
    },
    footer: context {
      if counter(page).get().first() > 1 {
        set text(size: 8.5pt, fill: luma(120))
        line(length: 100%, stroke: 0.4pt + luma(180))
        v(4pt)
        grid(
          columns: (1fr, 1fr),
          align(left)[© 2025 AMAL],
          align(right)[Page #counter(page).display() of #context counter(page).final().first()],
        )
      }
    },
  )

  // Fonts — Georgia for body text (serif, formal)
  set text(font: ("Georgia",), size: 10.5pt, fill: luma(30))

  // Paragraphs
  set par(leading: 0.72em, justify: true)

  // --- Title Page ---
  v(2fr)
  align(center)[
    #block(width: 90%)[
      #line(length: 100%, stroke: 1.5pt + rgb("#1a5276"))
      #v(24pt)
      #set par(justify: false)
      #text(size: 22pt, weight: "bold", fill: rgb("#1a5276"))[
        #title
      ]
      #v(8pt)
      #if subtitle != none {
        text(size: 14pt, fill: luma(80))[#subtitle]
      }
      #v(24pt)
      #line(length: 100%, stroke: 1.5pt + rgb("#1a5276"))
      #v(20pt)
      #text(size: 11pt, fill: luma(100))[
        #if date != none { date } else { datetime.today().display("[month repr:long] [day], [year]") }
      ]
      #v(8pt)
      #text(size: 10pt, fill: luma(120))[
        Version 1.0
      ]
    ]
  ]
  v(3fr)
  pagebreak()

  // --- Body styles ---

  // Headings
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => {
    v(20pt)
    block(width: 100%)[
      #text(size: 20pt, weight: "bold", fill: rgb("#1a5276"))[
        #if it.numbering != none {
          counter(heading).display()
          h(10pt)
        }
        #it.body
      ]
      #v(4pt)
      #line(length: 100%, stroke: 1pt + rgb("#1a5276"))
    ]
    v(12pt)
  }

  show heading.where(level: 2): it => {
    v(16pt)
    block[
      #text(size: 14pt, weight: "bold", fill: rgb("#2c3e50"))[
        #if it.numbering != none {
          counter(heading).display()
          h(8pt)
        }
        #it.body
      ]
    ]
    v(6pt)
  }

  show heading.where(level: 3): it => {
    v(12pt)
    block[
      #text(size: 12pt, weight: "bold", fill: rgb("#34495e"))[
        #if it.numbering != none {
          counter(heading).display()
          h(8pt)
        }
        #it.body
      ]
    ]
    v(4pt)
  }

  show heading.where(level: 4): it => {
    v(10pt)
    block[
      #text(size: 11pt, weight: "bold", fill: rgb("#4a6274"))[
        #it.body
      ]
    ]
    v(3pt)
  }

  // Tables
  show table: set text(size: 9.5pt)
  set table(
    stroke: (x, y) => {
      let s = 0.5pt + luma(200)
      if y == 0 { (bottom: 1.2pt + rgb("#1a5276"), left: s, right: s, top: s) }
      else { (bottom: s, left: s, right: s) }
    },
    inset: (x: 8pt, y: 6pt),
    fill: (x, y) => {
      if y == 0 { rgb("#eaf2f8") }
      else if calc.odd(y) { luma(248) }
    },
  )
  show table.cell.where(y: 0): set text(weight: "bold", size: 9pt)

  // Code blocks
  show raw.where(block: true): it => {
    block(
      width: 100%,
      fill: rgb("#f8f9fa"),
      stroke: 0.5pt + luma(210),
      inset: 12pt,
      radius: 3pt,
    )[
      #set text(size: 9pt, font: "Menlo", fill: luma(40))
      #it
    ]
  }

  // Inline code
  show raw.where(block: false): it => {
    box(
      fill: rgb("#f0f3f5"),
      inset: (x: 3pt, y: 1.5pt),
      radius: 2pt,
    )[#text(size: 9.5pt, font: "Menlo", fill: rgb("#c0392b"))[#it]]
  }

  // Block quotes
  show quote.where(block: true): it => {
    block(
      width: 100%,
      inset: (left: 16pt, top: 8pt, bottom: 8pt, right: 12pt),
      stroke: (left: 3pt + rgb("#1a5276")),
      fill: rgb("#f7f9fb"),
    )[
      #set text(style: "italic", fill: luma(60))
      #it.body
    ]
  }

  // Links
  show link: set text(fill: rgb("#2471a3"))

  // Strong emphasis
  show strong: set text(fill: luma(10))

  body
}

// Apply template using pandoc variables
#show: body => report(
  title: [$title$],
  subtitle: [$subtitle$],
  $if(date)$
  date: [$date$],
  $endif$
  body,
)
