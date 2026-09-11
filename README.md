# xml-nv

**Status: NOT IMPLEMENTED — interface only.**

Every public function below is published with its signature and its
effect row, and every body is `todo()`.  Installing this package works;
calling it panics with `not implemented`.

## What this is

XML 1.0, read without reading a DTD.  A pull parser whose events are
byte ranges into the string the caller still holds, a tree built from
those same events, and a writer that puts a tree back out.  It is what
you reach for when something hands you a feed, a SOAP envelope, an
`.xlsx` part, an Android layout or a twenty-year-old configuration
file, and you would rather not install a C library to read it.

Five modules, and a reader should know which one they are on.

| surface | module | reach for it when |
| --- | --- | --- |
| the **events** | `xmlparse` | the document is large, or you want one element out of it |
| the **tree** | `xmltree` | the document fits in memory and you will ask it several questions |
| the **finds** | `xmlfind` | you know the tag or the attribute you are after |
| the **writer** | `xmlwrite` | you are producing XML, or changing part of a document |
| the **faults** | `xmlerror` | you are reporting what was wrong with somebody's file |

## Adding it, and checking it

```bash
novo pkg add xml-nv           # into your novo.toml
novo pkg build                # type- and effect-check the package
novo test --isolate tests/xmlparse_tests.nv
```

`novo test` is red today and that is the point of the release: every
assertion fails with `not implemented: xml-nv.<module>.<fn>`.  They turn
green one at a time as bodies land.

## The one example that will work

```novo
use xmltree
use xmlfind

fn main() [io]
    let doc = xmltree.build("<feed><item><title>hello</title></item></feed>")
    for item in xmlfind.findall_descendants(doc, 1, "item")
        println(xmlfind.findtext(doc, item, "title", "(untitled)"))
    // hello
```

## The load-bearing interface

`xmlparse.next_event` — a scanner value in, an event and the next
scanner out.

```novo norun:pseudo
pub fn next_event(s: XmlScanner) -> Result<XmlStep, xmlerror.XmlFault> []
```

Everything else in the package is built on it.  `xmltree.build` is that
loop with an arena under it.  `xmlwrite` is its inverse.  `xmlfind` is
arithmetic over what the arena holds.  And a caller streaming a 400 MB
export calls it and nothing else, because the state is three integers
and a stack of open-element ranges, and no event allocates.

The second decision the rest follows from is that **every event is a
byte range, never a copy**.  A start tag says where its name is and
where each attribute's name and value are.  `&amp;` is not a substring
of the document, so decoding is a separate call that a caller makes when
it wants the text and skips when it only wants to know an element was
seen — which, for a scan looking for one tag in a large file, is always.

## Where the tolerance is, and where it is not

The package's row on the grid asks for "a pull parser and a tolerant
tree", and the two halves differ on purpose.

**The scanner is draconian**, because XML 1.0 § 1.2 says a
well-formedness error is fatal and a conforming processor must not
continue past one.  `next_event` answers `Err` and the scan is over.
That is not this package being strict; it is the difference between XML
and HTML, and it is why html-nv — otherwise this package's twin — has no
error type at all.

**`xmltree.build` is tolerant of four named things**, and of nothing
else:

| what | what happens |
| --- | --- |
| an end tag that matches no open element | closes up to the nearest ancestor that does, or is dropped |
| an end tag with nothing open | dropped |
| the document ending mid-element | everything still open is closed at the end of the source |
| an undeclared namespace prefix | the name keeps its prefix and resolves to no namespace |

Each one records an `XmlIssue` on the document, so a caller that wanted
strictness can ask for `doc.issues` to be empty — or call
`xmltree.build_strict`, which is XML 1.0's own behaviour and the right
choice for a validator or a signature check.

Everything else stops the build: a malformed entity, an unquoted
attribute, a bad declaration.  After one of those the scanner cannot say
what the next event even is, and a tree built past it would be a guess
dressed as a document.  `xmlerror.is_recoverable` is that rule as a
function, public because it decides which half of this package a caller
is in.

## What is outside XML 1.0 here

Named, because a parser that half-implements a specification is worse
than one that says where it stops.

**The DTD, past the five predefined entities.**  `&lt;` `&gt;` `&amp;`
`&apos;` `&quot;` and the numeric references `&#nn;` / `&#xNN;` are
expanded.  Nothing else is: a document that declares `<!ENTITY mine
"...">` in an internal subset and then writes `&mine;` gets
`XmlBadEntity`.  The `<!DOCTYPE ...>` itself is not refused — it arrives
as one `XmlDoctype` event carrying the whole declaration, internal
subset included, unparsed — so a caller that needs the subset has the
bytes and can read them itself.

One consequence worth having on purpose: **there is no billion-laughs
attack surface**, because there is no entity expansion to recurse.  The
`XmlLimits` bounds are about nesting and attribute counts, not about
expansion depth.

**Validation.**  No DTD validation, no XML Schema, no RelaxNG.  A
document is well-formed or it is not, and whether it matches a schema is
schema-nv's question about a different tree or somebody else's package
about this one.

**The external subset, and every other thing that would be fetched.**  A
`SYSTEM` identifier is bytes in the doctype event and nothing follows
it.  This is a `core` package: it has no `[net]` and no `[fs]` to follow
one with, which makes XXE not a vulnerability that was mitigated but a
capability that does not exist.

**Encodings other than UTF-8.**  novo-lang's `Str` is UTF-8, so the
scanner reads UTF-8, and `<?xml encoding="ISO-8859-1"?>` is
`XmlUnsupportedEncoding` rather than a transcode — a `core` package has
no encoding tables, and answering Latin-1 bytes as though they were
UTF-8 would corrupt text silently instead of refusing loudly.  A caller
holding other bytes decodes them first.

**XInclude, XPointer, XPath, XSLT, canonical XML.**  None of them.
`xmlfind` is deliberately not an XPath subset — see below.

**`xml:space` and `xml:lang`.**  Not interpreted.  They are ordinary
attributes here; whitespace inside an element is content, because
without a schema there is nothing that could say otherwise.

## Why `xmlfind` is not an XPath subset

ElementTree ships a "limited XPath subset", and the limits are the
problem.  It has `//`, `[@attr='v']`, `[position()]` and `..`; it
silently does not have axes, functions, unions, or anything else.  So a
caller who knows XPath writes an expression that *parses* and answers
the wrong nodes, and finds out in production.

Every function here is a named walk instead — `find`, `findall`,
`find_descendant`, `findall_by_attr`, `ancestors`, `closest` — so the
signature says what it does and a reader can see that this is not a path
language.  A caller who genuinely wants one over a tree wants a package
that says XPath on the tin.

The other thing made explicit rather than implied: **matching is on the
local name and the namespace, never on the prefix**, in every `_ns`
function.  A prefix is a spelling the document chose, and two feeds in
one namespace may spell it `atom:` and `a:`.  The plain functions match
the qualified name as written, which is what a caller with a
namespace-free document wants and what keeps the common case to one
argument.

## Namespaces are resolved on the tree, not on the events

An `xmlns:` declaration is scoped to the element it is written on, so
resolving a prefix needs the stack of open elements — state a pull
parser would have to carry for every caller, including everyone scanning
a document with no namespaces in it.  So `xmlparse` hands over qualified
names as written and `xmltree` splits them once, into an index into
`doc.namespaces`.

Two details that follow, and that libraries get wrong:

- **An unprefixed attribute is in no namespace**, never in the default
  one (XML Namespaces 1.0 § 6.2).  `<a xmlns="urn:x" id="1">` has an
  element in `urn:x` and an attribute in nothing.
- **`xmlns` attributes stay in the attribute list.**  A rewriter that
  dropped them would write a document whose prefixes no longer bind.
  `xmltree.is_namespace_decl` is how a caller walking attributes skips
  them.

## The layer, and why

`core`.  A scan over a string the caller already holds, an arena of
indices, and a serialiser that appends to the caller's buffer.  No
function declares an effect, and the two places one could have crept in
are refusals rather than omissions: an external DTD subset is never
fetched, and a non-UTF-8 encoding declaration is answered rather than
transcoded.

**No device claim.**  There is no `tests/embedded_probe.nv`, and that is
a claim not made rather than a claim skipped: the tree is an allocation
per document and the scanner speaks `Str`.  cbor-nv is the format
package on this grid with a half that compiles for a microcontroller,
and it says so.

## The reference implementation

`quick-xml` (Rust, MIT) for the event half — its `Event` enum is the
shape `XmlEventKind` has, minus the borrowed-vs-owned distinction that
novo-lang's ranges make unnecessary — and Python's
`xml.etree.ElementTree` (PSF) for the tree and the finds.  The oracle is
the **W3C XML Conformance Test Suite**: its `valid` documents must scan
to `XmlEof`, its `not-wf` documents must answer a fault, and
`tests/xmlparse_tests.nv` quotes the cases a reader can check against
the suite rather than against this package.  The `invalid` collection is
deliberately not an oracle here — it is about DTD validity, which this
package does not claim.

libxml2 is **not** on [the bindings shelf](https://novo-lang.org/docs/orbit-map.html)
and is not the reference: this is a native port, it builds for wasm, and
a consumer who takes it does not take a C toolchain.

## What depends on this

`rss-nv` — RSS and Atom, read and written over these events — is the
first consumer on the grid, and it is the reason `xmlfind`'s
namespace-aware half exists: an Atom feed puts everything in
`http://www.w3.org/2005/Atom` and every publisher spells the prefix
differently.

## Status

| function | implemented |
| --- | --- |
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
