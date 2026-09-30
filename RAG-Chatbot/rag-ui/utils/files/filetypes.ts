/**
 * File-type registry for the UI. MIRRORS rag-be/app/utils/filetypes.py — keep the two in sync.
 *
 * HOW TO ADD A FILE TYPE (frontend)
 *   1. add an entry to FILE_TYPES (extensions, label, magic bytes if the format has a header);
 *   2. if it needs special pre-upload checks, add utils/files/<type>.ts (see pdf.ts / docx.ts);
 *   3. add the same type on the backend (rag-be/app/utils/filetypes.py).
 * The server stays the source of truth (it re-validates every upload); these checks only give instant feedback.
 */
export type FileKind = {
  id: string;
  label: string;
  ext: string[];
  /** first bytes of a real file of this type, if the format has a signature */
  magic?: number[];
  /** can the browser show it inline in a new tab? otherwise we download it */
  inline: boolean;
};

export const FILE_TYPES: FileKind[] = [
  { id: "pdf", label: "PDF", ext: [".pdf"], magic: [0x25, 0x50, 0x44, 0x46], inline: true }, // %PDF
  { id: "docx", label: "Word", ext: [".docx"], magic: [0x50, 0x4b, 0x03, 0x04], inline: false }, // PK zip
  { id: "text", label: "Text", ext: [".txt", ".log"], inline: true },
  { id: "markdown", label: "Markdown", ext: [".md", ".markdown", ".rst"], inline: true },
  { id: "html", label: "HTML", ext: [".html", ".htm"], inline: false },
  { id: "csv", label: "CSV", ext: [".csv"], inline: false },
  { id: "json", label: "JSON", ext: [".json"], inline: true },
];

export const DEFAULT_MAX_MB = 25;

export const extOf = (name: string): string => {
  const i = name.lastIndexOf(".");
  return i < 0 ? "" : name.slice(i).toLowerCase();
};

export const kindOf = (name: string): FileKind | undefined => FILE_TYPES.find((t) => t.ext.includes(extOf(name)));

/** value for <input type="file" accept="...">. Pass the server's list (/api/status) when you have it. */
export const acceptAttr = (exts?: string[]): string => (exts ?? FILE_TYPES.flatMap((t) => t.ext)).join(",");

export const formatSize = (bytes: number): string =>
  bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : bytes >= 1024 ? `${Math.round(bytes / 1024)} KB` : `${bytes} B`;

/** Read the first `n` bytes of a file (cheap: does not load the whole file). */
export async function sniff(file: Blob, n = 1024): Promise<Uint8Array> {
  return new Uint8Array(await file.slice(0, n).arrayBuffer());
}

export const startsWith = (bytes: Uint8Array, magic: number[]): boolean => magic.every((b, i) => bytes[i] === b);

export type Rejection = { name: string; reason: string };
export type ValidationResult = { accepted: File[]; rejected: Rejection[]; warnings: Rejection[] };

/**
 * Pre-upload validation of a batch: extension, empty, size, real header, then type-specific checks
 * (PDF: encrypted warning; DOCX: zip header). Never throws; returns what to upload and what to explain.
 */
export async function validateFiles(
  files: FileList | File[],
  opts: { allowedExts?: string[]; maxMB?: number } = {},
): Promise<ValidationResult> {
  const { checkPdf } = await import("./pdf"); // lazy: keeps the type modules decoupled from this registry
  const { checkDocx } = await import("./docx");
  const allowed = new Set(opts.allowedExts ?? FILE_TYPES.flatMap((t) => t.ext));
  const maxBytes = (opts.maxMB ?? DEFAULT_MAX_MB) * 1048576;
  const res: ValidationResult = { accepted: [], rejected: [], warnings: [] };

  for (const file of Array.from(files)) {
    const kind = kindOf(file.name);
    const reject = (reason: string) => res.rejected.push({ name: file.name, reason });
    if (!allowed.has(extOf(file.name)) || !kind) reject(`unsupported type (allowed: ${Array.from(allowed).join(" ")})`);
    else if (file.size === 0) reject("file is empty");
    else if (file.size > maxBytes) reject(`larger than ${opts.maxMB ?? DEFAULT_MAX_MB} MB (${formatSize(file.size)})`);
    else {
      const head = await sniff(file);
      if (kind.magic && !startsWith(head, kind.magic)) reject(`not a real ${kind.label} file (wrong header)`);
      else {
        const check = kind.id === "pdf" ? await checkPdf(file) : kind.id === "docx" ? await checkDocx(file) : { ok: true };
        if (!check.ok) reject(check.reason!);
        else {
          if (check.warning) res.warnings.push({ name: file.name, reason: check.warning });
          res.accepted.push(file);
        }
      }
    }
  }
  return res;
}
