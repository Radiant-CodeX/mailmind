"""
Tests for the PII / privacy masking layer (app/services/pii.py).

Verifies the masking rubric: only private information specific enough to
identify or harm a small set of individuals is masked; generic, public, or
anonymized information is left untouched. Masking must be fully reversible and
must never leak raw PII into logs.
"""

import logging

import pytest

from app.services.pii import PIIEntity, detect_pii, mask_text, restore_text


# ── Hard identifiers ──────────────────────────────────────────────────────────

def test_email_masking():
    masked, mapping = mask_text("Contact me at jane.doe@example.com please.")
    assert "jane.doe@example.com" not in masked
    assert "[EMAIL_1]" in masked
    assert mapping["[EMAIL_1]"] == "jane.doe@example.com"


def test_phone_masking():
    masked, mapping = mask_text("Call +91 9876543210 after 5pm.")
    assert "9876543210" not in masked
    assert any(k.startswith("[PHONE_") for k in mapping)


def test_name_masking():
    # Greeting context ensures detection in both Presidio and regex-fallback modes.
    masked, mapping = mask_text("Hi John Smith, thanks for the update.")
    assert "John Smith" not in masked
    assert any(k.startswith("[PERSON_") for k in mapping)


def test_address_masking():
    masked, mapping = mask_text("Ship it to 1600 Pennsylvania Avenue right away.")
    assert "1600 Pennsylvania Avenue" not in masked
    assert any(k.startswith("[ADDRESS_") for k in mapping)


def test_api_key_and_token_masking():
    text = (
        "Here is the api_key=sk-ABCDEF1234567890ghijkl and a bearer "
        "Bearer abcdef1234567890ABCDEF token."
    )
    masked, mapping = mask_text(text)
    assert "sk-ABCDEF1234567890ghijkl" not in masked
    assert "abcdef1234567890ABCDEF" not in masked
    assert any(k.startswith("[SECRET_") for k in mapping)


def test_financial_card_masking():
    # 4111 1111 1111 1111 is a Luhn-valid Visa test number.
    masked, mapping = mask_text("My card is 4111 1111 1111 1111, expiry 12/27.")
    assert "4111 1111 1111 1111" not in masked
    assert any(k.startswith("[FIN_ID_") for k in mapping)


def test_government_id_masking():
    masked, mapping = mask_text("PAN ABCDE1234F and SSN 123-45-6789 on file.")
    assert "ABCDE1234F" not in masked
    assert "123-45-6789" not in masked
    assert any(k.startswith("[GOV_ID_") for k in mapping)
    assert any(k.startswith("[FIN_ID_") for k in mapping)


def test_vehicle_and_device_id_masking():
    masked, mapping = mask_text("Vehicle KA01AB1234 with IMEI 490154203237518 reported.")
    assert "KA01AB1234" not in masked
    assert "490154203237518" not in masked
    assert any(k.startswith("[DEVICE_ID_") for k in mapping)


# ── Golden Rule: things that must NOT be masked ───────────────────────────────

def test_generic_demographic_not_masked():
    text = "Many customers in their thirties prefer mobile apps over desktop."
    masked, mapping = mask_text(text)
    assert mapping == {}
    assert masked == text


def test_public_figure_in_public_context_not_masked():
    text = "Narendra Modi addressed the parliament about the new policy."
    masked, mapping = mask_text(text)
    assert "Narendra Modi" in masked
    assert not any(v == "Narendra Modi" for v in mapping.values())


# ── Reversibility & detection API ─────────────────────────────────────────────

def test_restore_text_returns_original():
    original = "Hi John Smith, email jane.doe@example.com or call +91 9876543210."
    masked, mapping = mask_text(original)
    assert restore_text(masked, mapping) == original


def test_restore_text_tolerant_to_llm_reformatting():
    # Simulate an LLM lightly reshaping the tokens in its output.
    original = "Hi John Smith, email jane.doe@example.com."
    _, mapping = mask_text(original)
    # The model wrote "[person 1]" and "[ EMAIL-1 ]" instead of exact tokens.
    llm_output = "Reply: Hello [person 1], I will write to [ EMAIL-1 ] shortly."
    restored = restore_text(llm_output, mapping)
    assert "John Smith" in restored
    assert "jane.doe@example.com" in restored
    assert "[" not in restored  # no leftover tokens


def test_detect_pii_returns_entities():
    entities = detect_pii("Email jane.doe@example.com now.")
    assert isinstance(entities, list)
    assert all(isinstance(e, PIIEntity) for e in entities)
    assert any(e.entity_type == "EMAIL" for e in entities)


def test_empty_text():
    assert mask_text("") == ("", {})
    assert detect_pii("") == []


# ── Safety: no raw PII in logs ────────────────────────────────────────────────

def test_no_raw_pii_logged(caplog):
    secret_email = "very.secret.person@private.com"
    secret_key = "sk-TOPSECRETKEY1234567890"
    with caplog.at_level(logging.DEBUG, logger="app.services.pii"):
        mask_text(f"Reach {secret_email} with key api_key={secret_key}")
    assert secret_email not in caplog.text
    assert secret_key not in caplog.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
