GPFG-Compliant ESG Classifier
This project is a Streamlit-based tool that uses a MAP–REDUCE LLM pipeline to classify companies according to the GPFG exclusion guidelines (§3–4). Users upload annual report PDFs, the system extracts text, splits it into chunks, sends each chunk to the LLM (MAP), merges the signals, and then produces a final classification (REDUCE).
Features:
Upload and process PDF annual reports
Paragraph-aware chunking for long documents
ESG signal extraction using structured prompts
Final classification: Approved, Flagged, or Excluded
CSV export of results
