#!/usr/bin/env python3
"""
gen_pdf_seeds.py — build hand-crafted PDF documents that exercise every
code path Atril's PDF backend (backend/pdf/ev-poppler.cc) drives:

  * document info / XMP metadata  -> pdf_document_parse_metadata(),
                                     pdf_document_get_format_from_metadata(),
                                     pdf_document_get_license_from_metadata()
  * page labels + page tree       -> ev_document_find_page_by_label()
  * outline tree                  -> pdf_document_links_get_links_model()
  * link annotations              -> ev_link_from_action(), tip_from_link()
  * Launch / URI actions          -> ev-window launch_action(),
                                     launch_external_uri()
  * named destinations            -> ev_document_links_find_link_dest()
  * text / highlight / file-attachment annotations
  * AcroForm fields               -> pdf_document_forms_get_form_fields()
  * embedded files                -> pdf_document_attachments_get_attachments()
  * page geometry extremes        -> cairo surface sizes in pdf_page_render()
  * transitions / layers

Each seed is deliberately "almost valid": poppler accepts it, so control
reaches Atril. That is what radamsa then mutates.

Usage:
    ./gen_pdf_seeds.py <outdir>
"""

import os
import sys
import zlib


def pdf_escape(s: bytes) -> bytes:
    return s.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class PDF:
    def __init__(self):
        # 1-based object bodies; entry None means "free"
        self.objects = [None]

    def add(self, body: bytes) -> int:
        self.objects.append(body)
        return len(self.objects) - 1

    def reserve(self) -> int:
        self.objects.append(None)
        return len(self.objects) - 1

    def set(self, num: int, body: bytes):
        self.objects[num] = body

    def stream(self, dict_body: bytes, data: bytes, compress=False) -> bytes:
        if compress:
            data = zlib.compress(data)
            dict_body = dict_body + b" /Filter /FlateDecode"
        return (b"<< " + dict_body + b" /Length " + str(len(data)).encode() +
                b" >>\nstream\n" + data + b"\nendstream")

    def build(self, root: int) -> bytes:
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0] * len(self.objects)
        for i in range(1, len(self.objects)):
            offsets[i] = len(out)
            body = self.objects[i]
            if body is None:
                body = b"null"
            out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
        xref = len(out)
        n = len(self.objects)
        out += b"xref\n0 " + str(n).encode() + b"\n"
        out += b"0000000000 65535 f \n"
        for i in range(1, n):
            out += ("%010d 00000 n \n" % offsets[i]).encode()
        out += (b"trailer\n<< /Size " + str(n).encode() +
                b" /Root " + str(root).encode() + b" 0 R >>\nstartxref\n" +
                str(xref).encode() + b"\n%%EOF\n")
        return bytes(out)


def base_page(pdf: PDF, parent: int, media=b"[0 0 612 792]",
              contents: bytes = b"", extra: bytes = b"",
              resources: bytes = b"<< >>") -> int:
    """Create a page object and return its object number."""
    content_obj = pdf.add(pdf.stream(b"", contents))
    page = pdf.add(
        b"<< /Type /Page /Parent " + str(parent).encode() +
        b" 0 R /MediaBox " + media +
        b" /Resources " + resources +
        b" /Contents " + str(content_obj).encode() + b" 0 R" + extra + b" >>")
    return page


def simple_doc(pages, root_extra=b"", catalog_extra=b"", xmp=None,
               info=b"", names_extra=b"", extra_objects=None):
    """Assemble a catalog + page tree from page object numbers."""
    pdf = PDF()
    pages_obj = pdf.reserve()
    catalog = pdf.reserve()

    kids = b" ".join(str(p).encode() + b" 0 R" for p in pages)
    pdf.set(pages_obj, b"<< /Type /Pages /Kids [" + kids +
            b"] /Count " + str(len(pages)).encode() + b" " + root_extra + b" >>")

    cat = b"<< /Type /Catalog /Pages " + str(pages_obj).encode() + b" 0 R "
    if xmp is not None:
        meta_obj = pdf.add(pdf.stream(
            b"/Type /Metadata /Subtype /XML", xmp))
        cat += b" /Metadata " + str(meta_obj).encode() + b" 0 R "
    cat += catalog_extra
    if names_extra:
        cat += b" /Names " + names_extra
    cat += b" >>"
    pdf.set(catalog, cat)

    if info:
        info_obj = pdf.add(info)
        # stored for caller via attribute
        pdf._info_obj = info_obj

    if extra_objects:
        extra_objects(pdf)
    return pdf, catalog


def set_pages_parent_fix(pdf, page_objs, pages_obj):
    for p in page_objs:
        pdf.set(p, pdf.objects[p].replace(
            b"/Parent " + str(pdf.objects[p]).encode(), b""))  # no-op guard


# ---------------------------------------------------------------------------
# Seed generators
# ---------------------------------------------------------------------------

def seed_minimal():
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p = base_page(pdf, pages, contents=b"BT /F1 24 Tf 72 700 Td (Hello Atril) Tj ET")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R] /Count 1 >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_xmp_full():
    """Every field pdf_document_get_license_from_metadata() reads, with a
    non-ASCII language tag, plus nested Alt entries."""
    xmp = b"""<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"
    xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:cc="http://creativecommons.org/ns#"
    pdfaid:part="1" pdfaid:conformance="B">
   <xmpRights:Marked>True</xmpRights:Marked>
   <dc:rights>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">All rights reserved</rdf:li>
     <rdf:li xml:lang="en-US">English terms</rdf:li>
     <rdf:li xml:lang="en">en terms</rdf:li>
     <rdf:li xml:lang="pt-BR">termos</rdf:li>
    </rdf:Alt>
   </dc:rights>
   <cc:license rdf:resource="https://example.org/license?a=1&amp;b=2"/>
   <xmpRights:WebStatement>https://example.org/terms</xmpRights:WebStatement>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p = base_page(pdf, pages, contents=b"BT (xmp) Tj ET")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R] /Count 1 >>")
    meta = pdf.add(pdf.stream(b"/Type /Metadata /Subtype /XML", xmp))
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() +
            b" 0 R /Metadata " + str(meta).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_xmp_hostile():
    """Attribute-form PDF/A ids plus a deeply nested / huge rdf:li[lang()]
    value, and an XPath metacharacter-language string."""
    xmp = b"""<x:xmpmeta xmlns:x="adobe:ns:meta/">
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" pdfaid:part="2" pdfaid:conformance="U"
 xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/"
 xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
<xmpRights:Marked>True</xmpRights:Marked>
<dc:rights><rdf:Alt>
<rdf:li xml:lang="x-default">AAAA%s</rdf:li>
</rdf:Alt></dc:rights>
</rdf:Description></rdf:RDF></x:xmpmeta>""" % (b"A" * 4096)
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p = base_page(pdf, pages, contents=b"BT (xmp2) Tj ET")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R] /Count 1 >>")
    meta = pdf.add(pdf.stream(b"/Type /Metadata /Subtype /XML", xmp))
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() +
            b" 0 R /Metadata " + str(meta).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_outline_and_links():
    """Outline entries whose titles contain pango markup, plus GoTo,
    GoToR, URI and Launch actions."""
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p = base_page(pdf, pages, contents=b"BT (links) Tj ET")
    page2 = base_page(pdf, pages, contents=b"BT (page2) Tj ET")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() + b" 0 R " +
            str(page2).encode() + b" 0 R] /Count 2 >>")

    # Link annotations with every action class.
    def link(rect, action):
        return pdf.add(
            b"<< /Type /Annot /Subtype /Link /Rect " + rect +
            b" /Border [0 0 0] /A " + action + b" >>")

    la = [
        link(b"[72 700 200 720]",
             b"<< /S /URI /URI (https://example.org/?q=%s%n%x) >>"),
        link(b"[72 650 200 670]",
             b"<< /S /Launch /F (../../../../tmp/atril-evil.sh) "
             b"/Win << /F (cmd.exe) /P (/c calc) >> >>"),
        link(b"[72 600 200 620]",
             b"<< /S /GoTo /D [1 0 R /XYZ -100 99999 8] >>"),
        link(b"[72 550 200 570]",
             b"<< /S /GoToR /F (other%2e%2e/evil.pdf) /D [0 /Fit] >>"),
        link(b"[72 500 200 520]",
             b"<< /S /Named /N (Print) >>"),
        link(b"[72 450 200 470]",
             b"<< /S /URI /URI (www.example.org/<script>) >>"),
    ]

    pdf.set(p, pdf.objects[p].replace(
        b" >>", b" /Annots [" + b" ".join(
            str(x).encode() + b" 0 R" for x in la) + b"] >>"))

    # Outline: markup injection + a named destination + a remote file.
    outl = pdf.reserve()
    o1 = pdf.add(b"<< /Title (\\<b\\>Owned\\</b\\> \\&amp; <i>x</i>) "
                 b"/Parent " + str(outl).encode() + b" 0 R "
                 b"/A << /S /GoTo /D [1 0 R /Fit] >> >>")
    o2 = pdf.add(b"<< /Title (%s) /Parent " % (b"A" * 2000) +
                 str(outl).encode() + b" 0 R "
                 b"/A << /S /GoTo /D (named.dest) >> >>")
    o3 = pdf.add(b"<< /Title (Launch) /Parent " + str(outl).encode() + b" 0 R "
                 b"/A << /S /Launch /F (/bin/sh) >> >>")
    pdf.set(outl, b"<< /Type /Outlines /First " + str(o1).encode() + b" 0 R "
            b"/Last " + str(o3).encode() + b" 0 R /Count 3 >>")
    pdf.set(o1, pdf.objects[o1] + b" /Next " + str(o2).encode() + b" 0 R")
    pdf.set(o2, pdf.objects[o2] + b" /Next " + str(o3).encode() + b" 0 R "
            b"/Prev " + str(o1).encode() + b" 0 R")
    pdf.set(o3, pdf.objects[o3] + b" /Prev " + str(o2).encode() + b" 0 R")

    # Named destinations, including one with a weird name.
    dests = pdf.add(b"<< /named.dest [1 0 R /FitH 99999] "
                    b"/%2e%2e%2fetc [0 0 R /XYZ null null null] >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R "
            b"/Outlines " + str(outl).encode() + b" 0 R "
            b"/Dests " + str(dests).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_page_labels():
    """Number tree page labels with huge/negative/odd prefixes."""
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    objs = [base_page(pdf, pages, contents=b"BT (p%d) Tj ET" % i)
            for i in range(6)]
    pdf.set(pages, b"<< /Type /Pages /Kids [" +
            b" ".join(str(o).encode() + b" 0 R" for o in objs) +
            b"] /Count 6 >>")

    nums = pdf.add(b"<< /Nums [0 << /S /D /St 1 >> "
                   b"1 << /S /R /St 2147483647 >> "
                   b"2 << /S /r >> "
                   b"3 << /S /A /P (AAAA%s) /St -1 >> "
                   b"4 << /S /D /P (\\050\\051) >> "
                   b"5 << /S /D /P () >>] >>" % (b"Z" * 512))
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R "
            b"/PageLabels " + str(nums).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_annotations():
    """Text/markup/file-attachment annotations whose /Contents and /T are
    rendered in the sidebar and tooltips (markup + long strings)."""
    embed_data = b"#!/bin/sh\necho pwned\n"

    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    ef = pdf.add(pdf.stream(b"/Type /EmbeddedFile", embed_data))
    fs = pdf.add(b"<< /Type /Filespec /F (evil.sh) /UF (evil.sh) "
                 b"/Desc (desc) /EF << /F " + str(ef).encode() + b" 0 R >> >>")
    annots = [
        pdf.add(b"<< /Type /Annot /Subtype /Text /Rect [72 700 92 720] "
                b"/Contents (hello \\<b\\>bold\\</b\\> %n %s) "
                b"/T (author\\<i\\>) /Name /Comment /Open true >>"),
        pdf.add(b"<< /Type /Annot /Subtype /FileAttachment /Rect [72 650 92 670] "
                b"/Contents (attach) /FS " + str(fs).encode() + b" 0 R "
                b"/Name /Paperclip >>"),
        pdf.add(b"<< /Type /Annot /Subtype /Highlight /Rect [72 600 200 620] "
                b"/Contents (%s) /T (h) "
                b"/QuadPoints [72 620 200 620 72 600 200 600] "
                b"/C [32768 0 0] >>" % (b"H" * 3000)),
        pdf.add(b"<< /Type /Annot /Subtype /Text /Rect [72 550 92 570] "
                b"/Contents (popup) /Name /Note >>"),
    ]
    pg = base_page(pdf, pages, contents=b"BT (annots) Tj ET",
                   extra=b" /Annots [" + b" ".join(
                       str(x).encode() + b" 0 R" for x in annots) + b"]")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(pg).encode() +
            b" 0 R] /Count 1 >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_attachments():
    """Embedded files with hostile names: traversal, absolute path, quotes,
    NUL-ish bytes, and a huge payload."""
    payload = b"PK\x03\x04" + b"A" * (256 * 1024)
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p = base_page(pdf, pages, contents=b"BT (att) Tj ET")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R] /Count 1 >>")

    ef = pdf.add(pdf.stream(b"/Type /EmbeddedFile /Subtype /text#2Fplain",
                            payload))
    names = [
        b"../../../../home/user/.config/autostart/evil.desktop",
        b"/etc/cron.d/evil",
        b"..\\..\\..\\windows\\system32\\evil.exe",
        b"quote\\\"name\\'s.XXXXXX",
        b"A" * 4000,
        b"evil.sh",
    ]
    fs_refs = []
    for n in names:
        fs = pdf.add(b"<< /Type /Filespec /F (" + pdf_escape(n)[:8000] +
                     b") /UF (" + pdf_escape(n)[:8000] + b") "
                     b"/Desc (" + pdf_escape(b"D" * 500) + b") "
                     b"/EF << /F " + str(ef).encode() + b" 0 R >> >>")
        fs_refs.append(fs)

    efnames = pdf.add(
        b"<< /Names [" +
        b" ".join(pdf_escape(n)[:1000] + b" " + str(f).encode() + b" 0 R"
                  for n, f in zip(names, fs_refs)) +
        b"] >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() +
            b" 0 R /Names << /EmbeddedFiles " + str(efnames).encode() +
            b" 0 R >> >>")
    return pdf.build(cat)


def seed_forms():
    """AcroForm with text/choice/button fields, including a choice field
    with an enormous option list and an editable value."""
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    fields = []

    fields.append(pdf.add(
        b"<< /Type /Annot /Subtype /Widget /FT /Tx /T (txt) /V (" +
        pdf_escape(b"T" * 4000) + b") /Rect [72 700 300 720] /DA (/Helv 12 Tf) "
        b"/MaxLen 2147483647 /Ff 0 >>"))
    opts = b" ".join(b"(opt%d)" % i for i in range(400))
    fields.append(pdf.add(
        b"<< /Type /Annot /Subtype /Widget /FT /Ch /T (ch) /Rect [72 650 300 690] "
        b"/Opt [" + opts + b"] /V (opt1) /Ff 0 /DA (/Helv 12 Tf) >>"))
    fields.append(pdf.add(
        b"<< /Type /Annot /Subtype /Widget /FT /Btn /T (btn) /Rect [72 600 92 620] "
        b"/V /Yes /AS /Yes /AP << /N << /Yes 2 0 R /Off 2 0 R >> >> >>"))
    fields.append(pdf.add(
        b"<< /Type /Annot /Subtype /Widget /FT /Sig /T (sig) "
        b"/Rect [72 550 200 590] >>"))

    p = base_page(pdf, pages, contents=b"BT (forms) Tj ET",
                  extra=b" /Annots [" + b" ".join(
                      str(x).encode() + b" 0 R" for x in fields) + b"]")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R] /Count 1 >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() +
            b" 0 R /AcroForm << /Fields [" +
            b" ".join(str(x).encode() + b" 0 R" for x in fields) +
            b"] /DA (/Helv 12 Tf) /DR << /Font << /Helv << /Type /Font "
            b"/Subtype /Type1 /BaseFont /Helvetica >> >> >> >> >>")
    return pdf.build(cat)


def seed_geometry():
    """Extreme MediaBox / UserUnit values: drives width*scale computations
    in pdf_document_render() and pdf_selection_render_selection()."""
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    objs = []
    boxes = [
        b"[0 0 1 1]",
        b"[0 0 200000 200000]",
        b"[0 0 0.0001 0.0001]",
        b"[-100000 -100000 100000 100000]",
        b"[0 0 612 792] /UserUnit 75000",
        b"[0 0 14400 14400] /Rotate 90",
        b"[0 0 14400 14400] /Rotate 450",
    ]
    for i, b in enumerate(boxes):
        objs.append(base_page(pdf, pages, media=b, contents=b"BT (g) Tj ET"))
    pdf.set(pages, b"<< /Type /Pages /Kids [" +
            b" ".join(str(o).encode() + b" 0 R" for o in objs) +
            b"] /Count " + str(len(objs)).encode() + b" >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_page_tree_hostile():
    """/Count that disagrees with /Kids, a dangling /Kids entry, and a
    self-referencing page tree node."""
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p = base_page(pdf, pages, contents=b"BT (tree) Tj ET")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R 9999 0 R] /Count -1 >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_text_bomb():
    """Huge text content and a font with a broken encoding: text extraction,
    layout and find all walk this."""
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    lines = []
    for i in range(4000):
        lines.append(b"BT /F1 6 Tf 10 %d Td (line %d with text) Tj ET" % (10 + (i % 700), i))
    contents = b"\n".join(lines)
    font = pdf.add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                   b"/Encoding /WinAnsiEncoding >>")
    p = base_page(pdf, pages, contents=contents,
                  resources=b"<< /Font << /F1 " + str(font).encode() + b" 0 R >> >>")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R] /Count 1 >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R >>")
    return pdf.build(cat)


def seed_transitions_and_layers():
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p1 = base_page(pdf, pages, contents=b"BT (t1) Tj ET",
                   extra=b" /Trans << /S /Split /D 5 /Dm /H >>")
    p2 = base_page(pdf, pages, contents=b"BT (t2) Tj ET",
                   extra=b" /Trans << /S /Glitter /D -1 /Dm /V >>")
    p3 = base_page(pdf, pages, contents=b"BT (t3) Tj ET",
                   extra=b" /Trans << /S /Fly /D 0 >>")
    pdf.set(pages, b"<< /Type /Pages /Kids [" +
            b" ".join(str(o).encode() + b" 0 R" for o in [p1, p2, p3]) +
            b"] /Count 3 >>")
    ocg = pdf.add(b"<< /Type /OCG /Name (layer) >>")
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() + b" 0 R "
            b"/PageMode /UseOC /OCProperties << /OCGs [" +
            str(ocg).encode() + b" 0 R] /D << /ON [" + str(ocg).encode() +
            b" 0 R] >> >> >>")
    return pdf.build(cat)


def seed_info_strings():
    pdf = PDF()
    pages = pdf.reserve()
    cat = pdf.reserve()
    p = base_page(pdf, pages, contents=b"BT (info) Tj ET")
    pdf.set(pages, b"<< /Type /Pages /Kids [" + str(p).encode() +
            b" 0 R] /Count 1 >>")
    info = pdf.add(b"<< /Title (" + pdf_escape(b"<b>T</b>" + b"t" * 3000) +
                   b") /Author (" + pdf_escape(b"A" * 3000) +
                   b") /Subject (\\376\\377\\000A\\000B) /Keywords (k1, k2) "
                   b"/Creator (c) /Producer (p) "
                   b"/CreationDate (D:99999999999999+99'99') "
                   b"/ModDate (D:00000000000000Z) >>")
    pdf.set(pages, pdf.objects[pages])
    pdf.set(cat, b"<< /Type /Catalog /Pages " + str(pages).encode() +
            b" 0 R /PageLayout /TwoPageRight /PageMode /FullScreen >>")
    out = pdf.build(cat)
    # inject /Info into the trailer
    return out.replace(b"trailer\n<< /Size", b"trailer\n<< /Info " +
                       str(info).encode() + b" 0 R /Size")


SEEDS = {
    "minimal": seed_minimal,
    "xmp_full": seed_xmp_full,
    "xmp_hostile": seed_xmp_hostile,
    "outline_links": seed_outline_and_links,
    "page_labels": seed_page_labels,
    "annotations": seed_annotations,
    "attachments": seed_attachments,
    "forms": seed_forms,
    "geometry": seed_geometry,
    "page_tree": seed_page_tree_hostile,
    "text_bomb": seed_text_bomb,
    "transitions": seed_transitions_and_layers,
    "info_strings": seed_info_strings,
}


# ---------------------------------------------------------------------------
# Image XObject seeds: the poppler -> decoder path
# ---------------------------------------------------------------------------

def _image_doc(width, height, dict_body, data):
    """One page whose only content draws one image XObject."""
    pdf = PDF()
    pages_obj = pdf.reserve()
    catalog = pdf.reserve()
    img = pdf.add(b"<< " + dict_body + b" /Width " + str(width).encode() +
                  b" /Height " + str(height).encode() + b" /Length " +
                  str(len(data)).encode() + b" >>\nstream\n" + data +
                  b"\nendstream")
    content = (b"q " + str(width).encode() + b" 0 0 " +
               str(height).encode() + b" 0 0 cm /Im0 Do Q")
    content_obj = pdf.add(pdf.stream(b"", content))
    page = pdf.add(
        b"<< /Type /Page /Parent " + str(pages_obj).encode() +
        b" 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im0 " +
        str(img).encode() + b" 0 R >> >> /Contents " +
        str(content_obj).encode() + b" 0 R >>")
    pdf.set(pages_obj, b"<< /Type /Pages /Kids [" + str(page).encode() +
            b" 0 R] /Count 1 >>")
    pdf.set(catalog, b"<< /Type /Catalog /Pages " + str(pages_obj).encode() +
            b" 0 R >>")
    return pdf.build(catalog)


def _seed_bytes(name):
    here = os.path.dirname(os.path.abspath(__file__))
    for d in ("seeds_images",):
        path = os.path.join(here, d, name)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    return None


def seed_image_dct():
    """JPEG inside DCTDecode: poppler hands the bytes to libjpeg."""
    jpg = _seed_bytes("pil_jpeg.jpg") or b"\xff\xd8\xff\xd9"
    return _image_doc(64, 64, b"/Type /XObject /Subtype /Image "
                               b"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                               b"/Filter /DCTDecode", jpg)


def seed_image_jpx():
    """JPEG 2000 inside JPXDecode: poppler hands the bytes to openjpeg."""
    jp2 = _seed_bytes("wrap.jp2") or b"\xff\x4f\xff\xd9"
    return _image_doc(32, 32, b"/Type /XObject /Subtype /Image "
                               b"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                               b"/Filter /JPXDecode", jp2)


def seed_image_jbig2():
    """JBIG2Decode: poppler hands the globals + segment data to libjbig."""
    jb = _seed_bytes("wrap.jbig2") or b"\0" * 16
    return _image_doc(64, 64, b"/Type /XObject /Subtype /Image "
                               b"/ColorSpace /DeviceGray /BitsPerComponent 1 "
                               b"/Filter /JBIG2Decode", jb)


def seed_image_ccitt():
    """CCITTFaxDecode G4: poppler hands the bitstream to its CCITT decoder."""
    cc = _seed_bytes("wrap.ccitt") or b"\0\x10\x01" * 6
    return _image_doc(64, 64, b"/Type /XObject /Subtype /Image "
                               b"/ColorSpace /DeviceGray /BitsPerComponent 1 "
                               b"/Filter /CCITTFaxDecode /DecodeParms << "
                               b"/K -1 /Columns 64 /Rows 64 >>", cc)


def seed_image_flate_predict():
    """FlateDecode with a PNG predictor: exercises the predictor filter, which
    is Atril-side only in the sense that poppler must size the output."""
    import zlib as _z
    w = h = 32
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # predictor tag: none
        raw += bytes([x * 8 % 256 for x in range(w)])
        raw += bytes([y * 8 % 256 for y in range(w)])
        raw += bytes([100] * w)
    return _image_doc(w, h, b"/Type /XObject /Subtype /Image "
                             b"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                             b"/Filter /FlateDecode /DecodeParms << "
                             b"/Predictor 15 /Colors 3 /BitsPerComponent 8 "
                             b"/Columns 32 >>", _z.compress(bytes(raw)))


def seed_image_smask():
    """An image with a soft mask: poppler composites two decodes."""
    jpg = _seed_bytes("pil_jpeg.jpg") or b"\xff\xd8\xff\xd9"
    return _image_doc(64, 64, b"/Type /XObject /Subtype /Image "
                               b"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
                               b"/Filter /DCTDecode", jpg)


SEEDS.update({
    "image_dct": seed_image_dct,
    "image_jpx": seed_image_jpx,
    "image_jbig2": seed_image_jbig2,
    "image_ccitt": seed_image_ccitt,
    "image_flate_predict": seed_image_flate_predict,
    "image_smask": seed_image_smask,
})

def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    outdir = sys.argv[1]
    os.makedirs(outdir, exist_ok=True)
    for name, fn in SEEDS.items():
        data = fn()
        path = os.path.join(outdir, name + ".pdf")
        with open(path, "wb") as f:
            f.write(data)
        print("%-16s %8d bytes  %s" % (name, len(data), path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
