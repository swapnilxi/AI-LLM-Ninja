# About the rag-data folder

Each folder inside `rag-data/` is a **profile** (for example `rag-data/company1/`). This `common/` folder is special:
its documents are shared with every profile that has "include common" switched on.

Put documents (.txt, .md, .pdf, .csv, .json, .html, .docx) in a profile folder, or create a profile in the
**Profiles** tab, then click **Sync now** in the Documents tab. New and changed files are embedded; deleted
files are removed. A chat only ever searches the active profile plus this common folder.

You can delete this sample file once you add your own documents.
