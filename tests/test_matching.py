"""Tests for alias matching, term boundaries, and evidence verification."""

import pytest
from ats.matching import (
    matches_term_in_text, verify_evidence_quote,
    build_term_regex, is_skill_in_standalone_list_only
)


def test_alias_matching_bidirectional():
    """Verify bidirectional alias matching for common tech terms."""
    # k8s and kubernetes
    assert matches_term_in_text("Kubernetes", "Deployed microservices on k8s cluster.")
    assert matches_term_in_text("k8s", "Managed distributed applications on Kubernetes.")

    # JavaScript and JS
    assert matches_term_in_text("JavaScript", "Built interactive UI in JS and React.")
    assert matches_term_in_text("js", "Modern JavaScript development experience.")

    # CI/CD
    assert matches_term_in_text("CI/CD", "Automated deployment with continuous integration pipelines.")

    # AWS
    assert matches_term_in_text("AWS", "Deployed cloud services on Amazon Web Services.")


def test_programming_language_boundaries():
    """Verify that 'C' does not match 'C++' or 'C#', and special symbols work."""
    cpp_text = "Proficient in C++ and Modern C++20."
    csharp_text = "Experienced with C# and .NET framework."
    c_text = "System programming in C and Linux kernel drivers."

    # 'C' should NOT match 'C++' or 'C#'
    assert not matches_term_in_text("C", cpp_text)
    assert not matches_term_in_text("C", csharp_text)

    # 'C' should match standalone 'C'
    assert matches_term_in_text("C", c_text)

    # 'C++' matches C++ text
    assert matches_term_in_text("C++", cpp_text)
    assert not matches_term_in_text("C++", c_text)

    # 'C#' and '.NET'
    assert matches_term_in_text("C#", csharp_text)
    assert matches_term_in_text(".NET", csharp_text)

    # 'Node.js'
    node_text = "Backend developed with Node.js and Express."
    assert matches_term_in_text("Node.js", node_text)
    assert matches_term_in_text("Node", node_text)


def test_evidence_verification_exact_substring():
    """Verifies that authentic verbatim quotes from the resume pass verification."""
    resume = "Architected 12 Python microservices using Docker and Kubernetes, processing 15M daily requests."
    ev_exact = "Architected 12 Python microservices using Docker and Kubernetes"
    assert verify_evidence_quote(ev_exact, resume)


def test_evidence_verification_token_overlap():
    """Verifies that quotes with slight punctuation differences pass token coverage >= 85%."""
    resume = "Architected 12 Python microservices using Docker and Kubernetes, processing 15M daily requests."
    ev_minor = "Architected twelve Python microservices using Docker and Kubernetes"
    # Even if one word changes, token overlap is high (>85%)
    assert verify_evidence_quote(ev_minor, resume, threshold=0.80)


def test_evidence_verification_hallucination_fails():
    """Verifies that hallucinated or non-existent quotes return False."""
    resume = "Architected 12 Python microservices using Docker and Kubernetes."
    hallucinated_ev = "Led executive data science division using TensorFlow and PyTorch for neural networks."
    assert not verify_evidence_quote(hallucinated_ev, resume)
    assert not verify_evidence_quote("", resume)


def test_skill_in_standalone_list_only():
    """Detects when a skill is only in skills section vs in experience."""
    skills_only_resume = """
    John Doe | Engineer
    
    SKILLS
    - Python, Docker, Rust, Kafka
    
    EXPERIENCE
    Software Engineer | Tech Corp
    - Built web apps using Python and Docker.
    """
    # Rust and Kafka are only in SKILLS, not in EXPERIENCE
    assert is_skill_in_standalone_list_only("Rust", skills_only_resume)
    assert is_skill_in_standalone_list_only("Kafka", skills_only_resume)

    # Python is in both SKILLS and EXPERIENCE
    assert not is_skill_in_standalone_list_only("Python", skills_only_resume)
