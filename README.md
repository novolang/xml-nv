# xml-nv

XML is a markup language for documents and data, defined by
[XML 1.0](https://www.w3.org/TR/xml/) and, for names carrying a prefix,
by [XML Namespaces 1.0](https://www.w3.org/TR/xml-names/). This package
reads and writes it in novo-lang, with no dependencies and no document
type definition: a pull parser whose events are byte ranges into the
caller's own string, a tree built from those events, named walks over
that tree, and a writer.

## What it is

An XML document is one **root element** with markup and text inside it.
An **element** is a start tag, its content and an end tag, or an empty
tag that is both at once. A tag carries **attributes**, each a name and
a quoted value.

A **pull parser** answers one **event** at a time: the caller asks for
the next one and decides what to do with it. This package's events are
XML 1.0's own list of what a document can contain.

| Event | The construct |
| --- | --- |
| `XmlStartTag` | `<tag a="1">`, with the attributes in source order |
| `XmlEndTag` | `</tag>` |
| `XmlEmptyTag` | `<tag a="1"/>`, kept as one event so a rewriter can put it back |
| `XmlText` | A run of character data between markup |
| `XmlCData` | `<![CDATA[...]]>`, never decoded, which is what the section is for |
| `XmlComment` | `<!-- ... -->` |
| `XmlProcessingInstruction` | `<?target data?>` |
| `XmlDeclaration` | `<?xml version="1.0" encoding="UTF-8"?>` |
| `XmlDoctype` | `<!DOCTYPE ...>`, whole and unparsed |
| `XmlEof` | The document ended |

Every event is a **range**: a pair of byte offsets into the string the
caller still holds. Nothing is copied. `&amp;` is not a substring of the
document, so decoding is a separate call a caller makes when it wants
the text and skips when it only wants to know an element was there.

A **document type definition**, or DTD, is a schema language XML carries
inside the document or references outside it. This package does not read
one. The five predefined entities and the numeric character references
are expanded, and nothing else is.

A **namespace** is a URI that qualifies a name. It is bound to a
**prefix** by an `xmlns:` attribute, scoped to the element the attribute
is written on. The scanner hands over names as they are written and the
tree resolves them, because resolving a prefix needs the stack of open
elements.

| Quantity | Default |
| --- | --- |
| Deepest nesting | 256 elements |
| Most attributes on one element | 4096 |
| Longest single name | 1024 bytes |
| Predefined entities | 5 |

## Install

```
novo pkg add xml-nv
```

## Example

```novo
use xmltree
use xmlfind

fn main() [io]
    // Build a tree. Nothing is opened: the caller holds the text.
    let doc = xmltree.build("<feed><item><title>hello</title></item></feed>")

    // Every `item` anywhere below the root, then the text of the
    // `title` inside each one, with a fallback when there is none.
    for item in xmlfind.findall_descendants(doc, xmltree.root(doc), "item")
        println(xmlfind.findtext(doc, item, "title", "(untitled)"))

    // A tolerant build records what it had to repair rather than
    // refusing. An empty list means the document was well-formed.
    for issue in xmltree.issues_of(doc)
        println(xmltree.issue_text(doc, issue))
```

It prints `hello`.

## What the package contains

| Module | Contents |
| --- | --- |
| `xmlparse` | The scanner: the events, the ranges, the limits, the decoders for text and attribute values, and the line and column of an offset. |
| `xmltree` | The tree: the nodes as an arena of indices, the namespaces resolved, the attributes, the text, and the repairs a tolerant build recorded. |
| `xmlfind` | Named walks over a tree: by tag, by namespace and local name, by attribute, over children or over descendants, and upwards to an ancestor. |
| `xmlwrite` | Writing: a whole document or one node into a caller's buffer, three option sets, and each construct on its own. |
| `xmlerror` | Every way a document is not well-formed, each with the byte range, and which of them a tolerant build can repair. |

## How to choose an entry point

**`xmlparse.next_event` is the scanner.** A scanner value in, an event
and the next scanner out. Use it when the document is large, or when
you want one element out of it. The state is an offset, a stack of open
names and two flags. An event allocates its attribute list, and a start
or end tag a new copy of the name stack, so the scanner passed in is
never changed.

**`xmltree.build_from` turns part of a scan into a tree.** A streaming
reader scans to each `<item>` and builds a tree of that element's
content alone.

**`xmltree.build` gives you the whole document.** Use it when the
document fits in memory and you will ask it several questions.
`build_strict` is the same thing that refuses rather than repairs.

**`xmlfind` is how a tree is searched.** Each function is a named walk,
so the signature says what it does.

**`xmlwrite.serialize` puts a tree back out**, and the `write_*`
functions write one construct at a time for a caller producing XML
without a tree.

## The rules a user needs

1. **The scanner stops at the first fault, and the scan is over.** XML
   1.0 section 1.2 makes a well-formedness error fatal and forbids a
   conforming processor from continuing past one. That is the
   difference between XML and HTML.
2. **`xmltree.build` repairs four things and nothing else.**

   | What | What happens | Recorded as |
   | --- | --- | --- |
   | An end tag matching an open element other than the innermost | Closes every element up to and including that one | `XmlMismatchedEnd` |
   | An end tag matching no open element, or with nothing open | Dropped | `XmlStrayEnd` |
   | The document ending mid-element | Everything still open closes at the end of the source | `XmlUnexpectedEnd` |
   | An undeclared namespace prefix | The name keeps its prefix and is in no namespace | `XmlUndeclaredPrefix` |

   Each repair records an `XmlIssue` on the document.
   `xmltree.issues_of` lists them, so a caller wanting strictness can
   require the list to be empty, or call `build_strict`, which answers
   the first fault of any kind. `xmlerror.is_recoverable` is the same
   rule as a function.
3. **Anything else stops the build.** After a malformed entity, an
   unquoted attribute or a bad declaration the scanner cannot say what
   the next event is, and a tree built past one would be a guess.
4. **An event is a range, not a string.** `xmlparse.text_at` answers
   the bytes, `xmlparse.decode` answers text with the references
   expanded, and `xmlparse.decode_attr` answers an attribute value the
   way XML 1.0 section 3.3.3 normalises it, each literal tab, line feed
   and carriage return becoming a space. A scan looking for one tag in
   a large file calls none of them.
5. **Only the five predefined entities and numeric references are
   expanded.** `&lt;`, `&gt;`, `&amp;`, `&apos;`, `&quot;`, `&#nn;` and
   `&#xNN;`. A document that declares `<!ENTITY mine "...">` and writes
   `&mine;` answers `XmlBadEntity`.
6. **There is no entity expansion, so there is no billion-laughs
   attack.** The limits bound nesting, attribute count and name length,
   because those are the pathological inputs that remain.
7. **The doctype arrives whole and unparsed.** The event's range covers
   `<!` to the matching `>`, internal subset included. A caller that
   needs the subset has the bytes.
8. **Nothing outside the document is ever fetched.** A `SYSTEM`
   identifier is bytes in the doctype event and nothing follows it.
   This package declares no effects at all, so an XML external entity
   attack is not a risk that was mitigated: it is a capability that
   does not exist.
9. **Text is UTF-8.** novo-lang's `Str` is UTF-8, so
   `<?xml encoding="ISO-8859-1"?>` answers `XmlUnsupportedEncoding`
   rather than being transcoded. A caller holding other bytes decodes
   them first. Every character is checked against XML 1.0's Char
   production (section 2.2), and a control character or bytes that are
   not UTF-8 answer `XmlBadChar`.
10. **Line ends are normalised on the way out.** A carriage return and
    line feed, or a carriage return alone, reads as one line feed
    (section 2.11) in every decoded text, a CDATA section included. The
    ranges still cover the bytes as written.
11. **Whitespace inside an element is content.** Without a schema there
    is nothing that could say otherwise, and `xml:space` and
    `xml:lang` are ordinary attributes here.
12. **Namespace matching is on the local name and the URI, never on
    the prefix.** A prefix is a spelling the document chose, and two
    feeds in one namespace may spell it `atom:` and `a:`. That is what
    every `_ns` function does; the plain functions match the qualified
    name as written, which is what a document with no namespaces
    wants.
13. **An unprefixed attribute is in no namespace.** Never in the
    default one. XML Namespaces 1.0 section 6.2.
    `<a xmlns="urn:x" id="1">` has an element in `urn:x` and an
    attribute in nothing.
14. **`xmlns` attributes stay in the attribute list.** A rewriter that
    dropped them would write a document whose prefixes no longer bind.
    `xmltree.is_namespace_decl` is how a walk over the attributes skips
    them.
15. **An empty tag stays one event.** Collapsing `<tag/>` into a start
    and an end would lose the one thing a rewriter needs to reproduce
    the source.
16. **The same attribute name twice on one element is refused.** XML
    1.0 section 3.1 forbids it outright.
17. **A document has exactly one root**, and content outside it that
    is not a comment, a processing instruction or whitespace is
    `XmlTrailingContent`.
18. **A fault carries byte offsets, and lines are computed on demand.**
    `XmlFault.at` and `.to` are offsets into the source.
    `xmlparse.line_of` and `column_of` turn one into a place a person
    can go to.
19. **`xmlerror.kind_name` is stable across releases.** Programs quote
    the spellings in their own messages and tests.

## What is not included

- **Reading a DTD, past the five predefined entities.** See rule 5.
- **Validation of any kind.** No DTD validity, no XML Schema, no
  RelaxNG. A document is well-formed or it is not.
- **Fetching the external subset, or anything else.** See rule 8.
- **Encodings other than UTF-8.** See rule 9.
- **XPath, XPointer, XInclude, XSLT and canonical XML.** `xmlfind` is
  deliberately not a path language. ElementTree's limited XPath subset
  has `//`, `[@attr='v']` and `[position()]` and silently lacks axes,
  functions and unions, so a caller who knows XPath writes an
  expression that parses and answers the wrong nodes. Every function
  here is a named walk instead, and a caller who wants a path language
  wants a package that says XPath on the tin.
- **Checking that two attributes on one element have different
  expanded names.** XML Namespaces 1.0 section 6.3 forbids
  `<a p:x="1" q:x="2">` when `p` and `q` are bound to one URI. The
  scanner refuses two attributes with the same qualified name, and the
  tree does not compare expanded names.
- **A microcontroller build.** The tree is an allocation per document
  and the scanner speaks `Str`.
  [cbor-nv](https://novo-lang.org/packages/cbor-nv) is the format
  package on the registry with a half that compiles for a device.

## Related packages

- [html-nv](https://novo-lang.org/packages/html-nv) is HTML5, and the
  two are siblings rather than one built on the other. HTML5's
  tokenizer has eighty states and 2231 named character references and
  recovers from everything; XML's has neither and recovers from
  nothing. A shared markup scanner would be two state machines behind
  one name.
- `rss-nv` is RSS and Atom over these events, and it is why
  `xmlfind`'s namespace-aware half exists: an Atom feed puts everything
  in `http://www.w3.org/2005/Atom` and every publisher spells the
  prefix differently.
- [schema-nv](https://novo-lang.org/packages/schema-nv) validates a
  JSON document rather than an XML one. Whether an XML document matches
  a schema is not a question this package answers.
- [cbor-nv](https://novo-lang.org/packages/cbor-nv) and
  [yaml-nv](https://novo-lang.org/packages/yaml-nv) are the other
  document formats on the registry.
- libxml2 is not the reference and is not on the bindings shelf. This
  is a native port: it builds for wasm, and a consumer who takes it
  does not take a C toolchain.

## Tests

```bash
novo test tests/xmlparse_tests.nv      # the events and the refusals
novo test tests/xmlscan_tests.nv       # each construct's refusals, references, limits
novo test tests/xmltree_tests.nv       # the tree, the finds, the writer
novo test tests/xmlns_tests.nv         # namespaces, the repairs, building from a scan
novo test tests/xmlwrite_tests.nv      # escaping, refusals, the three option sets
novo test tests/conformance_tests.nv   # the W3C suite, against Python's expat
bash tests/coverage.sh                 # line coverage over src/
```

The oracle is the W3C XML Conformance Test Suite, xmlts20130923.
`tools/conformance.py` writes `tests/conformance_tests.nv` from its
`xmltest` collection: the 85 `not-wf/sa` documents with no document
type declaration must be refused, and the 101 `valid/sa` documents
that refer to no entity but the five predefined ones must be read.
Python's expat must agree with the suite on every one. For each
well-formed document the file records the text and the element count
expat reads, which the tree must match, and the document itself, which
`xmlwrite.preserve()` must write back byte for byte. The other 120
documents of the two directories are left out: a not-wf one whose fault
is inside a DTD, which this package reads as opaque bytes, and a valid
one that uses an entity its DTD declares, which this package does not
expand. The suite's `invalid` collection is about DTD validity and is
not an oracle here.

`quick-xml` in Rust is the reference for the event half, and Python's
`xml.etree.ElementTree` for the tree and the finds; the find tests are
the ElementTree tutorial's own examples.

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
