"""Builds the output PDF from encoded layers using PyMuPDF's low-level API.

Image streams are written verbatim (JPEG / CCITT G4) so nothing is
re-encoded when the file is saved.
"""
from __future__ import annotations

import pymupdf

from .raster import Layer

PRODUCER = "DocFit"


class PdfAssembler:
    def __init__(self) -> None:
        self.doc = pymupdf.open()

    def _raw_stream(self, obj: str, data: bytes, filt: str, parms: str | None = None) -> int:
        xref = self.doc.get_new_xref()
        self.doc.update_object(xref, obj)
        self.doc.update_stream(xref, data, compress=False)
        # update_stream() drops the filter keys for raw data, so set them again.
        self.doc.xref_set_key(xref, "Filter", filt)
        if parms:
            self.doc.xref_set_key(xref, "DecodeParms", parms)
        return xref

    def _jpeg_xobject(self, layer: Layer, mask_xref: int | None = None) -> int:
        w, h = layer.size
        cs = "/DeviceGray" if layer.gray else "/DeviceRGB"
        mask = f"/Mask {mask_xref} 0 R" if mask_xref else ""
        obj = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
               f"/ColorSpace {cs} /BitsPerComponent 8 {mask} >>")
        return self._raw_stream(obj, layer.jpeg, "/DCTDecode")

    def _mask_xobject(self, layer: Layer) -> int:
        w, h = layer.mask_size
        obj = (f"<< /Type /XObject /Subtype /Image /Width {w} /Height {h} "
               f"/ImageMask true /BitsPerComponent 1 >>")
        return self._raw_stream(obj, layer.mask, "/CCITTFaxDecode",
                                f"<< /K -1 /Columns {w} /Rows {h} /BlackIs1 true >>")

    def add_layers_page(self, width_in: float, height_in: float, layers: list[Layer]) -> None:
        wpt, hpt = width_in * 72, height_in * 72
        page = self.doc.new_page(width=wpt, height=hpt)
        names, ops = [], []
        for i, layer in enumerate(layers):
            x0, y0, x1, y1 = layer.rect
            cm = f"{(x1 - x0) * 72:.3f} 0 0 {(y1 - y0) * 72:.3f} {x0 * 72:.3f} {hpt - y1 * 72:.3f} cm"
            name = f"/I{i}"
            if layer.kind == "image":
                xref = self._jpeg_xobject(layer)
                ops.append(f"q {cm} {name} Do Q")
            elif layer.kind == "masked":
                xref = self._jpeg_xobject(layer, self._mask_xobject(layer))
                ops.append(f"q {cm} {name} Do Q")
            elif layer.kind == "stencil":
                xref = self._mask_xobject(layer)
                fill = layer.fill or (0.0,)
                color = f"{fill[0]:.3f} g" if len(fill) == 1 else "{:.3f} {:.3f} {:.3f} rg".format(*fill)
                ops.append(f"q {color} {cm} {name} Do Q")
            else:
                raise ValueError(layer.kind)
            names.append(f"{name} {xref} 0 R")

        content = self.doc.get_new_xref()
        self.doc.update_object(content, "<< >>")
        self.doc.update_stream(content, "\n".join(ops).encode(), compress=True)
        self.doc.xref_set_key(page.xref, "Resources", f"<< /XObject << {' '.join(names)} >> >>")
        self.doc.xref_set_key(page.xref, "Contents", f"{content} 0 R")

    def add_pdf_page(self, src: pymupdf.Document, pno: int) -> None:
        self.doc.insert_pdf(src, from_page=pno, to_page=pno)

    @property
    def page_count(self) -> int:
        return self.doc.page_count

    def tobytes(self) -> bytes:
        self.doc.set_metadata({"producer": PRODUCER, "creator": PRODUCER})
        return self.doc.tobytes(garbage=3, deflate=True, use_objstms=1)

    def close(self) -> None:
        self.doc.close()
