# Changelog

Every published version, newest first. This file is on the publish
allow-list, so it travels with the package: it is the only thing a
consumer deciding whether to upgrade can read.

## 0.0.1 — 2026-09-11

The **interface**, before anyone implements it.  Every signature, every
type and every effect row is published; every body is `todo()`, and the
release is stamped `NOT IMPLEMENTED — interface only`.  Adding this
package works and calling it panics.

- Five modules.  `xmlparse` is the pull parser, `xmltree` the tolerant
  tree, `xmlfind` the finds over it, `xmlwrite` the writer back out, and
  `xmlerror` the one fault type all of them answer with.
- **Every event is a byte range into the caller's own string**, never a
  copy — a start tag says where its name is and where each attribute's
  name and value are — so a scan of a large document allocates nothing.
  `decode` is a separate call because `&amp;` is not a substring of the
  document, and a caller looking for one tag never needs it.
- Nine event kinds, which is XML 1.0's own list plus the end of the
  document.  An empty tag stays one arm rather than becoming a start and
  an end, because that is the one thing a rewriter needs to reproduce
  the source.
- **The scanner is draconian and the tree is tolerant**, and the split
  is XML 1.0 § 1.2's rather than this package's: a well-formedness error
  is fatal, so `next_event` answers `Err` and `xmltree.build` recovers
  from exactly four named things — a mismatched end tag, a stray end
  tag, a document that ends mid-element, and an undeclared namespace
  prefix — recording an issue for each.  `xmlerror.is_recoverable` is
  that rule as a function, and `xmltree.build_strict` is XML's own
  behaviour for a caller who wants it back.
- **Namespaces are resolved on the tree, not on the events**, because an
  `xmlns:` declaration is scoped to the element it sits on and a pull
  parser would have to carry that stack for every caller, including
  everyone scanning a document with no namespaces in it.  An unprefixed
  attribute resolves to no namespace rather than to the default one,
  which is XML Namespaces 1.0 § 6.2 and the rule most libraries get
  wrong, and `xmlns` attributes stay in the attribute list so that a
  rewriter does not unbind the document.
- **`xmlfind` is named walks, not an XPath subset.**  ElementTree ships
  a "limited XPath subset" whose limits nobody can state, so an
  expression that parses answers the wrong nodes; here `find`,
  `findall`, `find_descendant`, `findall_by_attr`, `ancestors` and
  `closest` each say what they do in their own signature.
- **The writer refuses what it cannot escape.**  Character data escapes
  three characters, an attribute value escapes its own delimiter and the
  whitespace an XML processor would normalise away, and a comment or a
  CDATA section holding `--` or `]]>` is an `Err` rather than a mangled
  document — XML gives neither construct an escape mechanism, so there
  is no correct output to produce.  Every name a caller supplies is
  checked against the Name production first.
- **Five named refusals of XML 1.0 itself**, in the README: the DTD past
  the five predefined entities and the numeric references, validation of
  any kind, anything that would be fetched, encodings other than UTF-8,
  and the XPath family.  One of them is worth having on purpose — with
  no entity expansion there is no billion-laughs surface, and with no
  `[net]` and no `[fs]` in a `core` package XXE is not a mitigated
  vulnerability but a capability that does not exist.
- **No dependencies.**  Not unicode-nv: XML's Name and Char productions
  are code point ranges, not property lookups, and name matching is
  defined as an exact comparison.  Not html-nv: the two are siblings and
  neither builds on the other, because HTML5's tokenizer recovers from
  everything and XML's recovers from nothing.
- **No device claim.**  There is no `tests/embedded_probe.nv`, because
  the tree is an allocation per document and the scanner speaks `Str`.

The oracle is the W3C XML Conformance Test Suite: its `valid` documents
must scan to `XmlEof` and its `not-wf` documents must answer a fault.
`tests/xmlparse_tests.nv` quotes the cases a reader can check against
the suite rather than against this package.
