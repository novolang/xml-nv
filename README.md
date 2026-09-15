# xml-nv

XML is a markup language for documents and data, defined by
[XML 1.0](https://www.w3.org/TR/xml/) and, for names carrying a prefix,
by [XML Namespaces 1.0](https://www.w3.org/TR/xml-names/). This package
reads and writes it in novo-lang, with no dependencies and no document
type definition: a pull parser whose events are byte ranges into the
caller's own string, a tree built from those events, named walks over
that tree, and a writer.

**Status: NOT IMPLEMENTED — interface only.** Every function is
declared with its full signature, but every body is a `todo()` that
panics when called. The package is published so its design can be
reviewed and depended on before it is implemented. Version 0.1.0 will
be the first working release.

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

Build and test with `novo pkg build` and `novo test`. Today `novo test`
fails on purpose: every test reaches a `not implemented:
xml-nv.<module>.<fn>` panic. The tests are the specification the
implementation will have to satisfy.

## What the package contains

| Module | Contents |
| --- | --- |
| `xmlparse` | The scanner: the events, the ranges, the limits, the decoder, and the line and column of an offset. |
| `xmltree` | The tree: the nodes as an arena of indices, the namespaces resolved, the attributes, the text, and the repairs a tolerant build recorded. |
| `xmlfind` | Named walks over a tree: by tag, by namespace and local name, by attribute, over children or over descendants, and upwards to an ancestor. |
| `xmlwrite` | Writing: a whole document or one node into a caller's buffer, three option sets, and each construct on its own. |
| `xmlerror` | Every way a document is not well-formed, each with the byte range, and which of them a tolerant build can repair. |

## How to choose an entry point

**`xmlparse.next_event` is the scanner.** A scanner value in, an event
and the next scanner out. Use it when the document is large, or when
you want one element out of it. The state is three integers and a stack
of open names, and no event allocates.

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

   | What | What happens |
   | --- | --- |
   | An end tag matching no open element | Closes up to the nearest ancestor that matches, or is dropped |
   | An end tag with nothing open | Dropped |
   | The document ending mid-element | Everything still open closes at the end of the source |
   | An undeclared namespace prefix | The name keeps its prefix and resolves to no namespace |

   Each repair records an `XmlIssue` on the document.
   `xmltree.issues_of` lists them, so a caller wanting strictness can
   require the list to be empty. `xmlerror.is_recoverable` is the same
   rule as a function.
3. **Anything else stops the build.** After a malformed entity, an
   unquoted attribute or a bad declaration the scanner cannot say what
   the next event is, and a tree built past one would be a guess.
4. **An event is a range, not a string.** `xmlparse.text_at` answers
   the bytes and `xmlparse.decode` answers them with the entities
   expanded. A scan looking for one tag in a large file calls neither.
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
   them first.
10. **Whitespace inside an element is content.** Without a schema there
    is nothing that could say otherwise, and `xml:space` and
    `xml:lang` are ordinary attributes here.
11. **Namespace matching is on the local name and the URI, never on
    the prefix.** A prefix is a spelling the document chose, and two
    feeds in one namespace may spell it `atom:` and `a:`. That is what
    every `_ns` function does; the plain functions match the qualified
    name as written, which is what a document with no namespaces
    wants.
12. **An unprefixed attribute is in no namespace.** Never in the
    default one. XML Namespaces 1.0 section 6.2.
    `<a xmlns="urn:x" id="1">` has an element in `urn:x` and an
    attribute in nothing.
13. **`xmlns` attributes stay in the attribute list.** A rewriter that
    dropped them would write a document whose prefixes no longer bind.
    `xmltree.is_namespace_decl` is how a walk over the attributes skips
    them.
14. **An empty tag stays one event.** Collapsing `<tag/>` into a start
    and an end would lose the one thing a rewriter needs to reproduce
    the source.
15. **The same attribute name twice on one element is refused.** XML
    1.0 section 3.1 forbids it outright.
16. **A document has exactly one root**, and content after it that is
    not a comment, a processing instruction or whitespace is
    `XmlTrailingContent`.
17. **A fault carries byte offsets, and lines are computed on demand.**
    `XmlFault.at` and `.to` are offsets into the source.
    `xmlparse.line_of` and `column_of` turn one into a place a person
    can go to.
18. **`xmlerror.kind_name` is stable across releases.** Programs quote
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
novo test --isolate tests/xmlparse_tests.nv   #  7 tests: the events and the refusals
novo test --isolate tests/xmltree_tests.nv    # 10 tests: the tree, the namespaces, the repairs
```

`quick-xml` in Rust is the reference for the event half, and Python's
`xml.etree.ElementTree` for the tree and the finds. The oracle is the
W3C XML Conformance Test Suite: its `valid` documents must scan to
`XmlEof` and its `not-wf` documents must answer a fault.
`tests/xmlparse_tests.nv` quotes the cases a reader can check against
that suite rather than against this package. The suite's `invalid`
collection is about DTD validity, which this package does not claim,
and is not an oracle here.

The suite asserts that an empty tag is one event, that a mismatched end
tag is fatal to the scanner and an issue to the tree, that a CDATA
section is not decoded, that an unprefixed attribute is in no
namespace, that an `xmlns` attribute stays in the attribute list, that
an undeclared prefix resolves to no namespace with an issue recorded,
that a non-UTF-8 encoding declaration is refused, and that a document
with two roots is refused.

The tests compile today and fail at run, each on the `not implemented`
panic that is its body. That is the expected state of an interface
release. They turn green one at a time as bodies land.

## Implementation status

Nothing is implemented, apart from the four constants. Every function
here is declared with its signature and its effect row, and every body
is a `todo()`.

| Item | Implemented |
| --- | --- |
| `xmlparse.PREDEFINED_ENTITIES`, `xmltree.XML_NO_NODE`, `.XML_NO_NAMESPACE`, `xmlfind.XML_ANY_TAG` | yes (they are constants) |
| `xmlerror.fault`, `.kind_name`, `.message`, `.is_recoverable` | no |
| `xmlparse.default_limits`, `.scanner`, `.scanner_with` | no |
| `xmlparse.next_event`, `.depth` | no |
| `xmlparse.text_at`, `.decode`, `.entity_value` | no |
| `xmlparse.is_xml_char`, `.is_name`, `.line_of`, `.column_of` | no |
| `xmltree.build`, `.build_with`, `.build_strict`, `.build_from` | no |
| `xmltree.root`, `.document_element`, `.count`, `.node`, `.is_element` | no |
| `xmltree.children`, `.element_children`, `.descendants` | no |
| `xmltree.tag_of`, `.local_of`, `.namespace_of`, `.name_of` | no |
| `xmltree.attrs_of`, `.attr`, `.attr_ns`, `.is_namespace_decl` | no |
| `xmltree.slice`, `.text_of`, `.inner_text`, `.namespace_uri` | no |
| `xmltree.issue_text`, `.issues_of` | no |
| `xmlfind.find`, `.findall`, `.find_ns`, `.findall_ns` | no |
| `xmlfind.find_descendant`, `.findall_descendants`, `.findall_descendants_ns` | no |
| `xmlfind.find_by_attr`, `.findall_by_attr`, `.find_with_attr` | no |
| `xmlfind.findall_descendants_by_attr` | no |
| `xmlfind.findtext`, `.findtext_ns`, `.ancestors`, `.closest`, `.matches` | no |
| `xmlwrite.canonical`, `.pretty`, `.preserve` | no |
| `xmlwrite.serialize`, `.serialize_node`, `.serialize_children`, `.serialize_str` | no |
| `xmlwrite.write_start_tag`, `.write_end_tag`, `.write_empty_tag` | no |
| `xmlwrite.write_text`, `.write_attr_value`, `.write_cdata` | no |
| `xmlwrite.write_comment`, `.write_pi`, `.write_declaration` | no |
| `xmlwrite.escape_overhead` | no |

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
