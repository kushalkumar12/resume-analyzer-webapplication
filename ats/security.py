"""Security, validation, PII masking, sanitization, and rate limiting utilities."""

import re
import io
import time
import zipfile
import html
from typing import Tuple, Optional, List, Dict

# Regex for Google AI Studio API Key pattern
API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{35}")

# Regex for prompt injection attempts in resume or user inputs
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+(instructions?|prompt)", re.IGNORECASE),
    re.compile(r"give\s+(this\s+resume\s+)?(a\s+)?(100%|perfect|full)\s+score", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"override\s+scoring\s+rules?", re.IGNORECASE),
    re.compile(r"rate\s+this\s+as\s+(100|perfect|an?\s+ideal\s+candidate)", re.IGNORECASE),
    re.compile(r"<!--.*?instructions?.*?-->", re.IGNORECASE),
]

# Unicode bidirectional override and control characters to strip
BIDI_AND_CONTROL_PATTERN = re.compile(r"[\u202a-\u202e\u2066-\u2069\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def scrub_sensitive_keys(text: str, custom_key: Optional[str] = None) -> str:
    """Removes API keys from error messages, logs, or UI strings."""
    if not text:
        return ""
    scrubbed = API_KEY_PATTERN.sub("[REDACTED_API_KEY]", str(text))
    if custom_key and len(custom_key.strip()) >= 10:
        scrubbed = scrubbed.replace(custom_key.strip(), "[REDACTED_API_KEY]")
    return scrubbed


def validate_api_key_format(key: str) -> Tuple[bool, str]:
    """Validates API key shape without network calls."""
    if not key or not isinstance(key, str):
        return False, "API key cannot be empty."
    clean = key.strip()
    if " " in clean:
        return False, "API key must not contain whitespace."
    if len(clean) < 20:
        return False, "API key is too short to be valid."
    return True, ""


def sanitize_input_text(text: str) -> str:
    """Strips control chars and bidirectional override characters."""
    if not text:
        return ""
    # Normalize carriage returns and strip malicious control/bidi markers
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    return BIDI_AND_CONTROL_PATTERN.sub("", cleaned)


def escape_literal_text(text: str) -> str:
    """Escapes dangerous HTML tags and markdown link syntax without converting quotes into entity codes."""
    if not text:
        return ""
    # Unescape any preexisting entities (e.g. &#x27;, &quot;) so they don't render as raw symbols
    clean_text = html.unescape(text)
    # Escape HTML angle brackets and ampersands without transforming quotes into &#x27;
    escaped = html.escape(clean_text, quote=False)
    # Neutralize markdown link brackets to prevent markdown link injection
    for char in ["[", "]"]:
        escaped = escaped.replace(char, f"\\{char}")
    return escaped


def detect_prompt_injection(text: str) -> Tuple[bool, List[str]]:
    """Detects whether text contains prompt-injection instructions."""
    if not text:
        return False, []
    matches = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            matches.append(match.group(0))
    return bool(matches), matches


def mask_pii(resume_text: str) -> str:
    """Masks PII (email, phone, URLs, government IDs, candidate name line).

    Carefully preserves date ranges (e.g. 2017 - 2019) and metrics (e.g. 10 TB, 100k, 50%).
    """
    if not resume_text:
        return ""

    text = resume_text

    # 1. Emails
    email_regex = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    text = email_regex.sub("[EMAIL]", text)

    # 2. URLs (LinkedIn, GitHub, Portfolios, http/https/www)
    url_regex = re.compile(
        r"(https?://[^\s]+|www\.[^\s]+|(?:linkedin\.com|github\.com)/[A-Za-z0-9_-]+)",
        re.IGNORECASE
    )
    text = url_regex.sub("[LINK]", text)

    # 3. Government IDs: SSN (###-##-####) or 12-digit Aadhaar (#### #### ####)
    ssn_regex = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    text = ssn_regex.sub("[GOV_ID]", text)
    aadhaar_regex = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")
    text = aadhaar_regex.sub("[GOV_ID]", text)

    # 4. Phone Numbers:
    # Match strings with country code / parenthesized area codes or phone patterns,
    # without masking dates like "2018 - 2022" or numbers like "1,000,000".
    phone_regex = re.compile(
        r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b|"
        r"\b\+?\d{1,3}[-.\s]?\d{10}\b"
    )
    text = phone_regex.sub("[PHONE]", text)

    # 5. Mask candidate name (heuristic: first non-empty line if short and no colons/headings)
    lines = text.split("\n")
    masked_lines = []
    name_masked = False
    for line in lines:
        stripped = line.strip()
        if not name_masked and stripped:
            words = stripped.split()
            # If line is 1-4 words and doesn't look like a header or contact line
            is_header = any(h in stripped.lower() for h in ["resume", "curriculum", "summary", "profile", "contact", "[email]", "[phone]"])
            if 1 <= len(words) <= 4 and not is_header and ":" not in stripped:
                masked_lines.append("[CANDIDATE NAME]")
                name_masked = True
                continue
            name_masked = True  # Stop attempting after first content line
        masked_lines.append(line)

    return "\n".join(masked_lines)


class UploadSecurityError(Exception):
    """Raised when an uploaded file violates security or integrity rules."""
    pass


def validate_uploaded_file(file_name: str, file_bytes: bytes, max_mb: int = 5) -> Tuple[bool, str]:
    """Validates file extension, size, magic bytes, and checks for zip-bombs or corruption.

    Max upload size: 5 MB.
    PDF: Magic bytes '%PDF', must not be encrypted.
    DOCX: Magic bytes 'PK\x03\x04', zip-bomb limits, must contain 'word/document.xml'.
    """
    if not file_name or not file_bytes:
        return False, "File is empty or missing."

    # Size limit
    max_bytes = max_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return False, f"File exceeds maximum allowed size of {max_mb} MB ({len(file_bytes) / (1024*1024):.2f} MB)."

    ext = file_name.lower().split(".")[-1]
    if ext not in ["pdf", "docx"]:
        return False, f"Unsupported file extension .{ext}. Only PDF and DOCX files are allowed."

    if ext == "pdf":
        if not file_bytes.startswith(b"%PDF"):
            return False, "Invalid PDF: missing '%PDF' header magic bytes."

        # Verify PDF can be read and is not encrypted
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            if reader.is_encrypted:
                return False, "Encrypted or password-protected PDFs are not supported. Please upload an unlocked PDF."
            if len(reader.pages) > 12:
                return False, f"Resume exceeds maximum allowed page count (12 pages limit, found {len(reader.pages)})."
        except Exception as e:
            return False, f"Malformed or corrupted PDF file: {scrub_sensitive_keys(str(e))}"

    elif ext == "docx":
        if not file_bytes.startswith(b"PK\x03\x04"):
            return False, "Invalid DOCX: missing ZIP magic bytes header."

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
                infos = zf.infolist()

                # Zip bomb protections
                if len(infos) > 500:
                    return False, f"Suspicious DOCX structure: too many archive entries ({len(infos)})."

                total_uncompressed = sum(info.file_size for info in infos)
                max_uncompressed = 25 * 1024 * 1024  # 25 MB max uncompressed
                if total_uncompressed > max_uncompressed:
                    return False, "Suspicious DOCX archive: uncompressed size exceeds 25 MB limit."

                compressed_size = max(len(file_bytes), 1)
                ratio = total_uncompressed / compressed_size
                if ratio > 100.0:
                    return False, f"Suspicious compression ratio ({ratio:.1f}:1). Potential decompression bomb."

                # Verify actual Word document structure
                if "word/document.xml" not in zf.namelist():
                    return False, "Invalid DOCX: missing required 'word/document.xml' part."

        except zipfile.BadZipFile:
            return False, "Malformed or corrupted DOCX archive."
        except Exception as e:
            return False, f"Error validating DOCX file: {scrub_sensitive_keys(str(e))}"

    return True, ""


class SessionRateLimiter:
    """In-memory rate limiter per session.

    Enforces minimum interval (default 8s) and max requests per hour (default 15).
    """
    def __init__(self, min_interval_seconds: float = 8.0, max_per_hour: int = 15):
        self.min_interval = min_interval_seconds
        self.max_per_hour = max_per_hour
        self.history: List[float] = []
        self.last_run_time: float = 0.0

    def check(self) -> Tuple[bool, str]:
        now = time.time()

        # Check interval between consecutive completed runs
        elapsed = now - self.last_run_time
        if self.last_run_time > 0 and elapsed < self.min_interval:
            wait_time = max(1, int(self.min_interval - elapsed) + 1)
            return False, f"Please wait {wait_time} seconds before submitting another analysis."

        # Prune runs older than 1 hour (3600 seconds)
        one_hour_ago = now - 3600.0
        self.history = [t for t in self.history if t > one_hour_ago]

        if len(self.history) >= self.max_per_hour:
            return False, f"Hourly limit reached ({self.max_per_hour} analyses/hour). Please try again later."

        return True, ""

    def record_run(self):
        now = time.time()
        self.last_run_time = now
        self.history.append(now)

    def reset_cooldown(self):
        """Clears short interval cooldown without erasing the hourly usage history."""
        self.last_run_time = 0.0

