/**
 * DOCX utilities (frontend). Mirrors rag-be/app/utils/docx.py.
 *
 * WHAT THE FRONTEND DOES FOR WORD FILES
 *   1. pre-upload check ...... checkDocx(file)   zip header + "is it really a Word doc?" (looks inside the zip)
 *   2. metadata .............. fetchDocInfo(name) from pdf.ts (title, author, tables — extracted by the backend)
 *   3. open .................. browsers cannot render .docx, so openDocument() downloads it
 * Text extraction (headings, tables) happens on the backend; nothing to parse in the browser.
 *
 * Renamed .xlsx/.pptx are also zip files starting with "PK", so the header alone is not enough: a .docx zip
 * always lists "word/document.xml" among its entries. We find that name in the zip's central directory,
 * which stores file names as plain ASCII, without needing a zip library.
 */
import { sniff, startsWith } from "./filetypes";
import type { CheckResult } from "./pdf";

const ZIP_MAGIC = [0x50, 0x4b, 0x03, 0x04];

export async function checkDocx(file: File): Promise<CheckResult> {
  if (!startsWith(await sniff(file, 4), ZIP_MAGIC)) return { ok: false, reason: "not a real .docx (missing zip header)" };
  // the central directory sits at the end of the archive; 64 KB covers it for typical documents
  const tail = new Uint8Array(await file.slice(Math.max(0, file.size - 65536)).arrayBuffer());
  const text = new TextDecoder("latin1").decode(tail);
  if (!text.includes("word/document.xml")) {
    return { ok: false, reason: "zip archive is not a Word document (maybe .xlsx/.pptx renamed?)" };
  }
  return { ok: true };
}
