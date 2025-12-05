# Import our packages
import os
import re
import json
import asyncio
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import aiohttp
import fitz
import pandas as pd
import streamlit as st

# Import prompts from separate file
from prompts import (
    MAP_SYSTEM,
    MAP_USER_PREFIX,
    REDUCE_SYSTEM,
    REDUCE_USER_PREFIX,
    REDUCE_USER_INSTRUCTIONS
)

# Import the Pydantic library (used to clean and validate data). We use v2 validator, and fall back to v1 if needed.
from pydantic import BaseModel, Field, ValidationError
try:
    from pydantic import field_validator as _field_validator
except Exception:
    from pydantic import validator as _field_validator      

#  Credentials from NHH 
API_KEY = "x"
API_URL = "x"
MODEL_NAME = "gpt-5-mini"

# Package to help count tokens, check so it's installed, see "requirements.txt". 
import tiktoken
TOK = tiktoken.get_encoding("cl100k_base")

# Config parameters for the model
MAX_CONTEXT_TOKENS = 128_000
CHUNK_TARGET_TOKENS = 5_000  # See our report 
CHUNK_OVERLAP_TOKENS = 300  # Only used when a single paragraph is larger than the target size.
REQUEST_TIMEOUT_SEC = 120
MAX_CONCURRENT_REQUESTS = 10  # Parallel execution limit, to avoid overwhelming the API
LOW_TEXT_THRESHOLD = 2_000  # warn if PDF has little selectable text so its not a scanned document

# Streamlit UI, to make the report uploading easier/nicer 
st.set_page_config(page_title="GPFG-Compliant ESG Classifier", layout="centered")
st.title("GPFG-Compliant ESG Classifier")
st.caption("Aligned with Guidelines §3-4 (2022)")
files = st.file_uploader("Upload PDF annual reports", type=["pdf"], accept_multiple_files=True)
run_btn = st.button("Run classification")



# The Pydantic model, which make sure the data structured and formatted + data normalization
class ESGResult(BaseModel):
    company: str = ""
    industry: str = ""
    classification: str
    reasoning: str
    criteria_triggered: list = Field(default_factory=list)
    key_evidence: list = Field(default_factory=list)
    forward_looking_assessment: str = ""
    coal_transition_timeline: str = ""
    confidence_score: float = 0.0  # 0–100 confidence in final classification
    flagged_lean: str = ""         # "Approved", "Excluded", or "Neutral" - mainly for "Flagged" cases
    flagged_reasoning: str = ""    # Short explanation for Flagged cases

    @_field_validator('classification')
    def validate_classification(cls, v):
        v = v.strip() if isinstance(v, str) else str(v)
        if v not in ["Approved", "Flagged", "Excluded"]:
            v_lower = v.lower()
            if "excluded" in v_lower:
                return "Excluded"
            elif "flagged" in v_lower or "observation" in v_lower:
                return "Flagged"
            else:
                return "Approved"
        return v

    @_field_validator('confidence_score')
    def validate_confidence_score(cls, v):
        # Making sure the confidence score is between 0-100.
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        if v < 0:
            return 0.0
        if v > 100:
            return 100.0
        return v



# Count tokens using tiktoken (make sure it's installed)
def count_tokens(text: str) -> int:
    return len(TOK.encode(text))


# Convert PDF file into clean text + remove potential weird formatting (one string for the whole document).
def pdf_bytes_to_text(file_bytes: bytes) -> str:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    parts = [p.get_text("text") for p in doc]
    doc.close()
    text = "\n".join(parts)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def smart_chunk(text: str, target: int, overlap: int):
    """
    Paragraph-aware chunking, were we use: 
    - Splits text into paragraphs.
    - Groups paragraphs into chunks up to our "target" tokens (10k).
    - If a single paragraph is <10k tokens, then split by tokens with overlaped tokens to keep context.
    """
    paragraphs = text.split('\n\n')
    chunks, current_chunk, current_tokens = [], [], 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = count_tokens(para)

        # If one paragraph alone is too big, split it by tokens
        if para_tokens > target:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk, current_tokens = [], 0

            # hard-split the long paragraph using tiktoken
            ids = TOK.encode(para)
            i = 0
            while i < len(ids):
                j = min(i + target, len(ids))
                chunks.append(TOK.decode(ids[i:j]))
                if j >= len(ids):
                    break
                i = max(0, j - overlap)

        # If adding this paragraph would overflow the current chunk, start a new chunk
        elif current_tokens + para_tokens > target:
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            current_chunk, current_tokens = [para], para_tokens
            continue
        else:
            current_chunk.append(para)
            current_tokens += para_tokens

    # Add any remaining paragraphs as the last chunk
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))

    return chunks or [text]


# Normalize formatting from the LLM 
def parse_first_json(text: str, default=None):
    """Extract the first valid JSON object from a model response (handles ```json fences)."""
    if not text:
        return default
    s = text.strip()
    # Strip a leading ``` or ```json fence, if present
    s = re.sub(r'^\s*```(?:json)?', '', s, flags=re.IGNORECASE)
    # Strip a trailing ``` fence, if present
    s = re.sub(r'```?\s*$', '', s)
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(s):
        if ch in '{[':
            try:
                obj, _ = decoder.raw_decode(s[idx:])
                return obj
            except json.JSONDecodeError:
                continue
    return default

# It helps avoid repeated signals before we run the REDUCE step.
def deduplicate_signals(signals):
    """Keep unique signals by first 100 chars of normalized evidence."""
    if not signals:
        return []
    seen = set()
    unique = []
    for s in signals:
        e = (s.get("evidence") or "").strip().lower()
        if not e:
            continue
        key = e[:100]
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


# Custom error message, so we might know what went wrong if the LLM fails. 
class RetryableHTTPError(Exception):
    pass


def _retry_after_seconds(resp: aiohttp.ClientResponse):
    """Parse the Retry-After header from an aiohttp response."""
    retry_after = resp.headers.get("Retry-After")
    if not retry_after:
        return None

    # Header can be either a delay in seconds or as an HTTP-date
    try:
        delay = int(retry_after)
        return max(0, delay)
    except (TypeError, ValueError):
        pass

    try:
        dt = parsedate_to_datetime(retry_after)
    except (TypeError, ValueError):
        dt = None

    if not dt:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return max(0, (dt - datetime.now(timezone.utc)).total_seconds())



# Send our requests to the LLM, with retries if the server is busy (a common approach)
async def llm_chat_async(messages, model, url, key, session, timeout=REQUEST_TIMEOUT_SEC):
    """Low-level chat call with Azure compatibility and retries."""
    is_azure = ("azure.com" in url.lower()) or ("openai.azure.com" in url.lower())
    headers = {"Content-Type": "application/json"}

    if is_azure:
        payload = {"messages": messages, "max_completion_tokens": 10000}  # Max text output is 10000, more than enough. 
        headers["api-key"] = key
    else:
        payload = {"model": model, "messages": messages, "max_tokens": 10000}
        headers["Authorization"] = f"Bearer {key}"

    max_retries = 5
    for attempt in range(max_retries):
        try:
            async with session.post(url, headers=headers, json=payload, timeout=timeout) as resp:
                if resp.status in (429, 500, 502, 503, 504):
                    if attempt < max_retries - 1:
                        ra = _retry_after_seconds(resp)
                        wait_time = ra if ra else min(2 ** attempt, 20)
                        await asyncio.sleep(wait_time)
                        continue
                    raise RetryableHTTPError(f"HTTP {resp.status} after {max_retries} retries")
                
                if resp.status >= 400:
                    txt = await resp.text()
                    raise aiohttp.ClientError(f"HTTP {resp.status}: {txt[:200]}")
                
                data = await resp.json()
                return data["choices"][0]["message"]["content"]
        
        except asyncio.TimeoutError:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    
    raise RetryableHTTPError(f"Failed after {max_retries} attempts")


# The core of our model: This sends ONE chunk of text to the LLM and asks it to extract ESG "signals". Use the prompt in "prompts.py". 
# If none found it still sends a empty list so the chain don't break.  
async def map_extract_signals_async(chunk, key, model, url, session):
    msgs = [{"role": "system", "content": MAP_SYSTEM},
            {"role": "user", "content": MAP_USER_PREFIX + chunk}]
    try:
        raw = await llm_chat_async(msgs, model, url, key, session)
        out = parse_first_json(raw, default={"signals": []})
        if not isinstance(out, dict) or "signals" not in out:
            return {"signals": []}
        return out
    except aiohttp.ClientError as e:
        # IF the provided content filter triggers (in the API call), like "war" mentions, return a special signal so the LLM can treat it as a soft flag essentially. 
        msg = str(e).lower()
        if "content" in msg and ("filter" in msg or "trigger" in msg):
            st.warning("Content filter triggered during MAP")
            return {"signals": [{"criterion": "content_filter_triggered", "evidence": "map"}]}
        st.warning(f"MAP extraction failed: {str(e)[:100]}")
        return {"signals": []}
    except Exception as e:
        st.warning(f"MAP extraction failed: {str(e)[:100]}")
        return {"signals": []}


# See the omment in the code
async def process_chunks_parallel(chunks, key, model, url, max_concurrent, session, progress_callback=None):
    """Process multiple chunks at the same time, but never more than max_concurrent in parallel."""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_task(chunk, chunk_num, total):
        async with semaphore:
            if progress_callback:
                progress_callback(f"Processing chunk {chunk_num}/{total}")
            return await map_extract_signals_async(chunk, key, model, url, session)
    
    tasks = [bounded_task(chunk, i+1, len(chunks)) for i, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out if a chunck failed and then adds ALL "signals" to a list. 
    all_signals = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            st.warning(f"Chunk {i+1} failed: {str(result)[:100]}")
            continue
        if isinstance(result, dict) and "signals" in result:
            all_signals.extend(result.get("signals", []))
    
    return deduplicate_signals(all_signals)



# If the company name is not found, use the file name. 
def robust_name(v, fallback):
    return v if v and v.strip() not in {"", "Unknown", "N/A"} else fallback


# Same idea but here's it says Unknown Industry instead. 
def robust_industry(v):
    return v if v and v.strip().lower() not in {"", "unknown", "n/a"} else "Unknown Industry"


# The combined signals is send to the second AI prompt to evaluate the final ESG classification. 
async def reduce_classify_async(signals, fallback_company, doc_header, key, model, url, session):
    msgs = [{"role": "system", "content": REDUCE_SYSTEM},
            {"role": "user", "content": REDUCE_USER_PREFIX + f"{doc_header[:3000]}\n\n" +
             REDUCE_USER_INSTRUCTIONS + json.dumps({"signals": signals}, ensure_ascii=False)}]
    default = {
        "company": fallback_company,
        "industry": "Unknown Industry",
        "classification": "Flagged",
        "reasoning": "Fallback REDUCE result: parsing issue or incomplete model response. Manual review required.",
        "criteria_triggered": ["Fallback_Review"],
        "key_evidence": [],
        "forward_looking_assessment": "",
        "coal_transition_timeline": "",
        "confidence_score": 0.0,
        "flagged_lean": "",  # NEW field for direction if "Flagged"
        "flagged_reasoning": ""
    }
    try:
        raw = await llm_chat_async(msgs, model, url, key, session)
        out = parse_first_json(raw, default=default) or default

        # IF any content filter tripped in MAP, that the LLM sometimes dont want to process --> force flagg it 
        if any((isinstance(s, dict) and s.get("criterion") == "content_filter_triggered") for s in signals):
            out["classification"] = "Flagged"
            out["reasoning"] = (out.get("reasoning", "") +
                                " Content filter triggered; manual review required.").strip()
            out.setdefault("criteria_triggered", []).append("content_filter_triggered")

        out["company"] = robust_name(out.get("company"), fallback_company)
        out["industry"] = robust_industry(out.get("industry"))

        # Validate/normalize final text output from the LLM
        return ESGResult(**out).model_dump()
    except Exception as e:
        default["reasoning"] = f"REDUCE error: {str(e)[:150]}"
        default.setdefault("confidence_score", 0.0)
        return default


# See code comment again 
async def process_single_file_async(file_name, file_data, key, model, url, max_concurrent, session, status_callback=None):
    """Process a single PDF file at a time."""
    try:
        if status_callback:
            status_callback(f"Processing: {file_name}")
        
        text = pdf_bytes_to_text(file_data)
        if len(text) < LOW_TEXT_THRESHOLD:
            st.warning(f"{file_name}: Saftely measure, if theree's very little selectable text. Run OCR first.")

        chunks = smart_chunk(text, CHUNK_TARGET_TOKENS, CHUNK_OVERLAP_TOKENS)
        if status_callback:
            status_callback(f"{file_name}: {len(chunks)} Chunks are processed in parallel, according to set limits")

        # Run MAP at the same time, in parallel. Warns if there's an error. 
        try:
            signals = await process_chunks_parallel(
                chunks, key, model, url, max_concurrent, session,
                lambda msg: status_callback(f"{file_name}: {msg}") if status_callback else None
            )
        except Exception as async_err:
            st.error(f"Async processing error for {file_name}: {str(async_err)[:200]}")
            signals = []

        # Create a short header for each company
        header = "\n\n".join(chunks[:5]) if len(chunks) >= 5 else chunks[0]

        # Run REDUCE (step 2), and build the final results (+CSV) from the LLM outputs. Also, catches any potential errors. 
        try:
            final = await reduce_classify_async(
                signals, os.path.splitext(file_name)[0], header,
                key, model, url, session
            )
        except Exception as reduce_err:
            st.error(f"Classification error for {file_name}: {str(reduce_err)[:200]}")
            final = {
                "company": os.path.splitext(file_name)[0],
                "industry": "Unknown Industry",
                "classification": "Flagged",
                "criteria_triggered": ["Processing_Error"],
                "reasoning": f"Reduce phase error: {str(reduce_err)[:200]}",
                "key_evidence": [],
                "forward_looking_assessment": "",
                "coal_transition_timeline": "",
                "confidence_score": 0.0,
                "flagged_lean": ""
            }

        return {
            "file": file_name,
            "company": final.get("company", ""),
            "industry": final.get("industry", ""),
            "classification": final.get("classification", ""),
            "criteria_triggered": ", ".join(final.get("criteria_triggered", [])),
            "reasoning": final.get("reasoning", ""),
            "key_evidence": " | ".join(final.get("key_evidence", [])),
            "forward_looking": final.get("forward_looking_assessment", ""),
            "coal_transition": final.get("coal_transition_timeline", ""),
            "chunks_processed": len(chunks),
            "signals_found": len(signals),
            "confidence_score": final.get("confidence_score", 0.0),
            "flagged_lean": final.get("flagged_lean", ""),
            "flagged_reasoning": final.get("flagged_reasoning", "")
        }


    except Exception as e:
        return {
            "file": file_name,
            "company": os.path.splitext(file_name)[0],
            "industry": "Unknown Industry",
            "classification": "Flagged",
            "criteria_triggered": "Processing_Error",
            "reasoning": f"Processing error: {str(e)[:200]}",
            "key_evidence": "",
            "forward_looking": "",
            "coal_transition": "",
            "chunks_processed": 0,
            "signals_found": 0,
            "confidence_score": 0.0,
            "flagged_lean": ""
        }



# We use the ClientSession to keep all API calls within the same session (also a common practice for efficiency). 
async def process_all_files_async(files, key, model, url, max_concurrent, progress_bar, status_widget):
    """Process files sequentially (but chunks within each file in parallel) using a shared ClientSession."""
    file_data_list = [(f.name, f.read()) for f in files]
    
    connector = aiohttp.TCPConnector(
        limit=max_concurrent * 2,  # Allow enough connections for parallel chunks + we set an timeout for requests (safety)
        limit_per_host=max_concurrent * 2,
        force_close=False,
        enable_cleanup_closed=True
    )
    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC * 2)
    
    processed_results = []
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        # Process reports sequentially (but chunks in parallel within each file, as previsouly stated)
        for i, (file_name, file_data) in enumerate(file_data_list):
            try:
                result = await process_single_file_async(
                    file_name, file_data, key, model, url, max_concurrent, session,
                    lambda msg: status_widget.info(msg)
                )
                processed_results.append(result)
            except Exception as e:  # IF an error happen to an individual file, still produce/include it in the output.  
                processed_results.append({
                    "file": file_name,
                    "company": os.path.splitext(file_name)[0],
                    "industry": "Unknown Industry",
                    "classification": "Flagged",
                    "criteria_triggered": "Processing_Error",
                    "reasoning": f"Unexpected error: {str(e)[:200]}",
                    "key_evidence": "",
                    "forward_looking": "",
                    "coal_transition": "",
                    "chunks_processed": 0,
                    "signals_found": 0,
                    "confidence_score": 0.0,
                    "flagged_lean": ""
                })
            progress_bar.progress((i + 1) / len(file_data_list))  # Update the progress bar after each file processed
    
    return processed_results  # List of the results



# More Streamlit UI
if run_btn:
    if not files:
        st.warning("Please upload at least one PDF.")
        st.stop()

    progress = st.progress(0)
    status = st.empty()
    status.info(f"Processing {len(files)} file(s) in parallel...")

    # Process all files concurrently using a single event loop as defined
    try:
        results = asyncio.run(process_all_files_async(
            files, API_KEY, MODEL_NAME, API_URL, MAX_CONCURRENT_REQUESTS,
            progress, status
        ))
    except Exception as e:
        st.error(f"Critical error during parallel processing: {str(e)[:200]}")
        results = []

    status.success("Done.")
    df = pd.DataFrame(results)
    st.subheader("Results")
    st.dataframe(df, use_container_width=True)  # Show the results in an interactive table.
    st.download_button(
        "Download CSV",
        df.to_csv(index=False).encode("utf-8"),
        "gpfg_results.csv",
        "text/csv"
    )

    # Allow the user to download the results as a CSV file. DONE!!!


