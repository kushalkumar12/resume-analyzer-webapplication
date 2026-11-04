"""Alias-aware term matching and verbatim evidence verification."""

import re
from typing import List, Dict, Set, Tuple, Optional


# Canonical alias groups. Any member in a group is considered an alias of all others.
ALIAS_GROUPS: List[List[str]] = [
    ["k8s", "kubernetes"],
    ["js", "javascript"],
    ["ts", "typescript"],
    ["py", "python"],
    ["ml", "machine learning"],
    ["ai", "artificial intelligence", "genai", "generative ai"],
    ["dl", "deep learning"],
    ["nlp", "natural language processing"],
    ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
    ["aws", "amazon web services"],
    ["gcp", "google cloud platform", "google cloud"],
    ["azure", "microsoft azure"],
    ["react", "react.js", "reactjs"],
    ["node", "node.js", "nodejs"],
    ["vue", "vue.js", "vuejs"],
    ["angular", "angular.js", "angularjs"],
    ["postgres", "postgresql"],
    ["mongo", "mongodb"],
    ["tf", "terraform"],
    ["spring", "spring boot", "springboot"],
    ["rest", "restful", "rest api", "restful api", "rest apis", "restful apis"],
    ["graphql", "graph ql"],
    ["sql", "structured query language"],
    ["nosql", "no-sql"],
    ["kafka", "apache kafka"],
    ["spark", "apache spark"],
    ["airflow", "apache airflow"],
    ["bi", "business intelligence", "power bi", "powerbi"],
    ["excel", "ms excel", "microsoft excel"],
]

# Build bidirectional alias lookup dictionary
ALIAS_MAP: Dict[str, Set[str]] = {}
for group in ALIAS_GROUPS:
    normalized_group = [item.lower().strip() for item in group]
    for item in normalized_group:
        if item not in ALIAS_MAP:
            ALIAS_MAP[item] = set()
        for other in normalized_group:
            if other != item:
                ALIAS_MAP[item].add(other)


def get_aliases(term: str) -> Set[str]:
    """Returns all known aliases for a given term, plus the term itself."""
    clean_term = term.lower().strip()
    aliases = set(ALIAS_MAP.get(clean_term, set()))
    aliases.add(clean_term)
    return aliases


def build_term_regex(term: str) -> re.Pattern:
    """Builds a regex pattern for a term with strict boundaries.

    Handles special programming language symbols:
    - 'C' does not match 'C++' or 'C#'.
    - 'C++', 'C#', '.NET', 'Node.js' match reliably.
    """
    clean = term.strip()
    lower = clean.lower()

    if lower == "c":
        # 'c' as a standalone programming language: preceded and followed by non-word and non-plus/hash
        return re.compile(r"(?<![a-zA-Z0-9_+#])c(?![a-zA-Z0-9_+#])", re.IGNORECASE)
    elif lower in ["c++", "cpp"]:
        return re.compile(r"(?<![a-zA-Z0-9_])(c\+\+|cpp)(?![a-zA-Z0-9_])", re.IGNORECASE)
    elif lower in ["c#", "csharp"]:
        return re.compile(r"(?<![a-zA-Z0-9_])(c#|csharp)(?![a-zA-Z0-9_])", re.IGNORECASE)
    elif lower in [".net", "dotnet"]:
        return re.compile(r"(?<![a-zA-Z0-9_])(\.net|dotnet)(?![a-zA-Z0-9_])", re.IGNORECASE)
    elif lower in ["node.js", "nodejs", "node"]:
        if lower == "node":
            return re.compile(r"(?<![a-zA-Z0-9_])node(?:\.js)?(?![a-zA-Z0-9_])", re.IGNORECASE)
        return re.compile(r"(?<![a-zA-Z0-9_])(node\.js|nodejs)(?![a-zA-Z0-9_])", re.IGNORECASE)

    # General terms: handle plural variations e.g. api / apis, test / tests
    escaped = re.escape(clean)
    # Allow optional trailing 's' for simple nouns if not ending in special char or 's'
    if len(clean) > 2 and clean[-1].isalnum() and not clean.endswith("s"):
        pattern_str = rf"(?<![a-zA-Z0-9_]){escaped}s?(?![a-zA-Z0-9_])"
    else:
        pattern_str = rf"(?<![a-zA-Z0-9_]){escaped}(?![a-zA-Z0-9_])"

    return re.compile(pattern_str, re.IGNORECASE)


def matches_term_in_text(term: str, text: str, additional_synonyms: Optional[List[str]] = None) -> bool:
    """Checks if a term or any of its known aliases/synonyms is mentioned in the text."""
    if not term or not text:
        return False

    candidates = get_aliases(term)
    if additional_synonyms:
        for syn in additional_synonyms:
            if syn and syn.strip():
                candidates.add(syn.lower().strip())
                candidates.update(get_aliases(syn))

    for candidate in candidates:
        if not candidate:
            continue
        pat = build_term_regex(candidate)
        if pat.search(text):
            return True

    return False


def verify_evidence_quote(evidence: str, resume_text: str, threshold: float = 0.85) -> bool:
    """Verifies whether an evidence quote actually appears in the resume text.

    Requires:
    1. Direct substring match (case-insensitive, normalized spaces), OR
    2. At least 85% token coverage in a local context window within the resume.
    """
    if not evidence or not evidence.strip() or not resume_text:
        return False

    # Normalize whitespace
    clean_ev = re.sub(r"\s+", " ", evidence.strip()).lower()
    clean_resume = re.sub(r"\s+", " ", resume_text.strip()).lower()

    # 1. Exact substring check
    if clean_ev in clean_resume:
        return True

    # 2. Token overlap check
    # Strip punctuation from evidence words
    ev_tokens = [re.sub(r"[^\w]", "", w) for w in clean_ev.split()]
    ev_tokens = [w for w in ev_tokens if len(w) > 1]

    if not ev_tokens:
        return False

    resume_tokens = [re.sub(r"[^\w]", "", w) for w in clean_resume.split()]
    resume_token_set = set(w for w in resume_tokens if len(w) > 1)

    matched_tokens = [w for w in ev_tokens if w in resume_token_set]
    coverage = len(matched_tokens) / len(ev_tokens)

    if coverage < threshold:
        return False

    # Also verify token sequence proximity: matched tokens shouldn't be scattered across unrelated pages
    # Check if a sliding window in resume of length (len(ev_tokens) * 2 + 5) contains the matched tokens
    window_size = min(len(resume_tokens), max(len(ev_tokens) * 2 + 5, 20))
    for i in range(0, max(1, len(resume_tokens) - window_size + 1), max(1, window_size // 4)):
        window = set(resume_tokens[i:i + window_size])
        win_matches = sum(1 for w in ev_tokens if w in window)
        if (win_matches / len(ev_tokens)) >= threshold:
            return True

    return False


def is_skill_in_standalone_list_only(term: str, resume_text: str) -> bool:
    """Checks if a skill only appears in a 'Skills' section and not in 'Experience' or 'Projects'."""
    lower_resume = resume_text.lower()

    # Locate common section headers
    exp_pos = -1
    for h in ["experience", "work history", "employment", "professional experience"]:
        pos = lower_resume.find(h)
        if pos != -1 and (exp_pos == -1 or pos < exp_pos):
            exp_pos = pos

    proj_pos = -1
    for h in ["projects", "personal projects", "key projects"]:
        pos = lower_resume.find(h)
        if pos != -1 and (proj_pos == -1 or pos < proj_pos):
            proj_pos = pos

    skill_pos = -1
    for h in ["skills", "technical skills", "core competencies", "technologies"]:
        pos = lower_resume.find(h)
        if pos != -1 and (skill_pos == -1 or pos < skill_pos):
            skill_pos = pos

    # If experience or projects sections exist, check if term appears within them
    in_exp = False
    in_proj = False

    aliases = get_aliases(term)
    for alias in aliases:
        pat = build_term_regex(alias)

        if exp_pos != -1:
            # Experience section ends at next major section
            next_sections = [p for p in [proj_pos, skill_pos] if p > exp_pos]
            exp_end = min(next_sections) if next_sections else len(lower_resume)
            exp_text = lower_resume[exp_pos:exp_end]
            if pat.search(exp_text):
                in_exp = True
                break

        if proj_pos != -1:
            next_sections = [p for p in [exp_pos, skill_pos] if p > proj_pos]
            proj_end = min(next_sections) if next_sections else len(lower_resume)
            proj_text = lower_resume[proj_pos:proj_end]
            if pat.search(proj_text):
                in_proj = True
                break

    # If it was found in experience or projects, it is not listed-only
    if in_exp or in_proj:
        return False

    return True
