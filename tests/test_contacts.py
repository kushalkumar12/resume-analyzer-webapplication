"""Tests for recruiter contact extraction and search query generation."""

import pytest
from ats.contacts import extract_jd_contact_details, generate_recruiter_search_queries
from ats.models import JDContactDetails


def test_extract_emails_and_phones_from_jd():
    """Extracts explicit emails, phones, and application links from JD text."""
    jd_with_contacts = """
    Job Title: Senior Cloud Engineer
    Company: TechCorp
    
    About the role:
    We are looking for a cloud engineer.
    
    How to apply:
    Please send your resume to careers@techcorp.example.com or hr-recruiting@techcorp.example.com.
    You can also call our talent team at (555) 482-1920.
    Direct application link: https://careers.techcorp.example.com/apply/10294
    Contact: Sarah Connor, Lead Technical Recruiter
    """
    contacts = extract_jd_contact_details(jd_with_contacts)

    assert "careers@techcorp.example.com" in contacts.emails
    assert "hr-recruiting@techcorp.example.com" in contacts.emails
    assert any("482-1920" in p for p in contacts.phone_numbers)
    assert any("careers.techcorp.example.com" in link for link in contacts.application_links)
    assert any("Sarah Connor" in name for name in contacts.recruiter_names)


def test_jd_without_contacts_returns_empty_gracefully():
    """When JD has no emails or phones, returns clean empty structure without errors."""
    jd_no_contacts = """
    Senior Python Developer needed.
    Requirements: 4+ years of Python, Docker, Kubernetes.
    """
    contacts = extract_jd_contact_details(jd_no_contacts)
    assert len(contacts.emails) == 0
    assert len(contacts.phone_numbers) == 0
    assert len(contacts.recruiter_names) == 0


def test_generate_recruiter_search_queries():
    """Generates valid LinkedIn search queries for hiring team discovery."""
    queries = generate_recruiter_search_queries("Backend Engineer", "Stripe")
    assert len(queries) >= 2
    assert any("Stripe" in q["query"] for q in queries)
    assert any("Recruiter" in q["query"] for q in queries)
    assert all("linkedin.com" in q["query"] for q in queries)
