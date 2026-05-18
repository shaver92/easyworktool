"""将 PDF 按页拆成单页 PDF 字节列表（用于逐页 OCR）。"""

from io import BytesIO

from pypdf import PdfReader, PdfWriter


def split_pdf_to_single_page_pdfs(pdf_bytes: bytes) -> list[bytes]:
    reader = PdfReader(BytesIO(pdf_bytes))
    n = len(reader.pages)
    if n == 0:
        return []
    out: list[bytes] = []
    for i in range(n):
        writer = PdfWriter()
        writer.add_page(reader.pages[i])
        buf = BytesIO()
        writer.write(buf)
        out.append(buf.getvalue())
    return out
