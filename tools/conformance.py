#!/usr/bin/env python3
"""Write tests/conformance_tests.nv from the W3C XML Conformance Test
Suite, with Python's expat as a second opinion.

The suite, xmlts20130923, is James Clark's `xmltest` collection among
others; each document is marked well-formed or not.  This script takes
the `xmltest` documents this package can judge:

- every `not-wf/sa` document with no document type declaration, since
  a document whose fault is inside a DTD is one this package reads as
  opaque bytes;
- every `valid/sa` document whose content refers to no entity but the
  five predefined ones, since this package does not expand the ones a
  DTD declares.

For each, expat's verdict must agree with the suite's, or the script
stops.  For a well-formed document the file also records what
expat reads from it: the text inside the root element, joined, and
the number of elements.

Run from the package root:
    python3 tools/conformance.py [path/to/xmlconf]
With no argument the suite is fetched from w3.org.  The output is
passed through `novo fmt`.
"""
import io
import os
import re
import subprocess
import sys
import tarfile
import urllib.request
import xml.parsers.expat

URL = 'https://www.w3.org/XML/Test/xmlts20130923.tar.gz'
PREDEFINED = {'lt', 'gt', 'amp', 'apos', 'quot'}


def load(root):
    """Map a path under xmltest/ to its bytes."""
    files = {}
    if root:
        base = os.path.join(root, 'xmltest')
        for sub in ('valid/sa', 'not-wf/sa'):
            for name in os.listdir(os.path.join(base, sub)):
                if name.endswith('.xml'):
                    files[sub + '/' + name] = open(os.path.join(base, sub, name), 'rb').read()
        return files
    tar = tarfile.open(fileobj=io.BytesIO(urllib.request.urlopen(URL).read()))
    for m in tar.getmembers():
        for sub in ('valid/sa', 'not-wf/sa'):
            prefix = 'xmlconf/xmltest/' + sub + '/'
            if m.name.startswith(prefix) and m.name.endswith('.xml') and '/' not in m.name[len(prefix):]:
                files[sub + '/' + m.name[len(prefix):]] = tar.extractfile(m).read()
    return files


def expat_ok(data):
    p = xml.parsers.expat.ParserCreate()
    try:
        p.Parse(data, True)
        return True
    except xml.parsers.expat.ExpatError:
        return False


def read(data):
    """The text inside the root element, joined, and the number of
    elements, as expat reports them with namespaces off."""
    parts, count = [], [0]
    p = xml.parsers.expat.ParserCreate()
    p.CharacterDataHandler = parts.append

    def start(name, attrs):
        count[0] += 1
    p.StartElementHandler = start
    p.Parse(data, True)
    return ''.join(parts), count[0]


def content_after_doctype(text):
    m = re.search(r'<!DOCTYPE', text)
    if not m:
        return text
    depth, quote, i = 0, None, m.end()
    while i < len(text):
        c = text[i]
        if quote:
            if c == quote:
                quote = None
        elif c in '"\'':
            quote = c
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
        elif c == '>' and depth == 0:
            return text[i + 1:]
        i += 1
    return ''


def nv(s):
    out = []
    for ch in s:
        o = ord(ch)
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '$':
            out.append('\\$')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\r':
            out.append('\\r')
        elif ch == '\t':
            out.append('\\t')
        elif o < 32 or o == 127:
            out.append('\\x%02x' % o)
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def main():
    files = load(sys.argv[1] if len(sys.argv) > 1 else None)
    wf, not_wf, skipped = [], [], 0
    for path in sorted(files):
        data = files[path]
        try:
            text = data.decode('utf-8')
        except UnicodeDecodeError:
            skipped += 1
            continue
        if path.startswith('not-wf/'):
            if '<!DOCTYPE' in text:
                skipped += 1
                continue
            assert not expat_ok(data), path + ': expat reads a not-wf document'
            not_wf.append((path, text))
        else:
            refs = set(re.findall(r'&([A-Za-z_:][\w.:-]*);', content_after_doctype(text)))
            if refs - PREDEFINED:
                skipped += 1
                continue
            assert expat_ok(data), path + ': expat refuses a valid document'
            inner, count = read(data)
            wf.append((path, text, inner, count))
    lines = [
        '// conformance_tests.nv — documents from the W3C XML Conformance Test',
        '// Suite, xmlts20130923, with Python\'s expat as a second opinion.',
        '//',
        '// Written by tools/conformance.py; do not edit by hand.  The',
        '// `xmltest` collection\'s `not-wf/sa` documents with no document type',
        '// declaration must be refused, and its `valid/sa` documents that refer',
        '// to no entity but the five predefined ones must be read, with the text',
        '// and the element count expat reads, and written back unchanged with',
        '// `xmlwrite.preserve()`.  %d documents of the two' % skipped,
        '// directories are left out: a not-wf one whose fault is in a DTD, a',
        '// valid one that uses an entity its DTD declares, or one that is not',
        '// UTF-8.',
        '',
        'use std.test',
        'use xmlerror',
        'use xmlfind',
        'use xmltree',
        'use xmlwrite',
        '',
        '// The well-formed documents: the suite\'s path, the document, the text',
        '// of its root element and its number of elements.',
        'fn well_formed() -> [(Str, Str, Str, Int)]',
        '    [',
    ]
    for path, text, inner, count in wf:
        lines.append('        (%s, %s, %s, %d),' % (nv(path), nv(text), nv(inner), count))
    lines[-1] = lines[-1].rstrip(',')
    lines += ['    ]', '',
              '// The documents that are not well-formed: the suite\'s path and the',
              '// document.',
              'fn not_well_formed() -> [(Str, Str)]',
              '    [']
    for path, text in not_wf:
        lines.append('        (%s, %s),' % (nv(path), nv(text)))
    lines[-1] = lines[-1].rstrip(',')
    lines += ['    ]', '',
              '@test',
              'fn test_every_well_formed_document_is_read_as_expat_reads_it() [io]',
              '    for (path, doc, text, elements) in well_formed()',
              '        test.case(path)',
              '        match xmltree.build_strict(doc)',
              '            Err(_) =>',
              '                test.assert(false)',
              '            Ok(t)  =>',
              '                match xmltree.document_element(t)',
              '                    Some(r) =>',
              '                        test.assert(xmltree.inner_text(t, r) == text)',
              '                        test.assert(list.len(xmlfind.findall_descendants(t, 0, "*")) == elements)',
              '                        test.assert(xmlwrite.serialize_str(t, xmlwrite.preserve()) == doc)',
              '                    None    =>',
              '                        test.assert(false)',
              '',
              '@test',
              'fn test_every_document_that_is_not_well_formed_is_refused() [io]',
              '    for (path, doc) in not_well_formed()',
              '        test.case(path)',
              '        match xmltree.build_strict(doc)',
              '            Ok(_)  => test.assert(false)',
              '            Err(f) => test.assert(xmlerror.kind_name(f.kind) != "")',
              '']
    path = 'tests/conformance_tests.nv'
    open(path, 'w').write('\n'.join(lines))
    subprocess.run(['novo', 'fmt', path], check=True, capture_output=True)
    print('%d well-formed, %d not well-formed, %d left out -> %s' % (len(wf), len(not_wf), skipped, path))


if __name__ == '__main__':
    main()
