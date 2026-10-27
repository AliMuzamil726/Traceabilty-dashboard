"""Identifier normalisation and validation: CNIC, hemp ID, phones, postcodes, names."""

from __future__ import annotations

import pytest

from core.errors import ValidationAppError
from module_2.services.validators import (
    format_cnic,
    format_hemp_id,
    mask_id_number,
    mask_phone,
    normalise_farm_name,
    normalise_id_number,
    normalise_licence_no,
    normalise_person_name,
    normalise_phone,
    normalise_postcode,
    normalise_village,
    sanitise_text,
    title_case_name,
    validate_crop,
)


class TestCnic:
    @pytest.mark.parametrize(
        "raw",
        ["3520212345671", "35202-1234567-1", " 35202 1234567 1 ", "35202.1234567.1"],
    )
    def test_accepts_every_written_form(self, raw: str) -> None:
        norm, display = normalise_id_number(raw, "cotton")
        assert norm == "3520212345671"
        assert display == "35202-1234567-1"

    @pytest.mark.parametrize("raw", ["352021234567", "35202123456712", "", "abcdefghijklm"])
    def test_rejects_wrong_length_or_letters(self, raw: str) -> None:
        with pytest.raises(ValidationAppError):
            normalise_id_number(raw, "cotton")

    def test_formatting(self) -> None:
        assert format_cnic("3520212345671") == "35202-1234567-1"


class TestHempId:
    @pytest.mark.parametrize(
        ("raw", "expected_norm", "expected_display"),
        [
            ("123456789", "123456789", "123 456 789"),
            ("12 34 56 789", "123456789", "123 456 789"),
            ("1234567890123", "1234567890123", "123 456 789 0123"),
        ],
    )
    def test_accepts_range(self, raw: str, expected_norm: str, expected_display: str) -> None:
        norm, display = normalise_id_number(raw, "hemp")
        assert (norm, display) == (expected_norm, expected_display)

    @pytest.mark.parametrize("raw", ["12345678", "12345678901234", "ABC123456"])
    def test_rejects_out_of_range_or_non_numeric(self, raw: str) -> None:
        with pytest.raises(ValidationAppError):
            normalise_id_number(raw, "hemp")

    def test_grouping_never_leaves_a_single_trailing_digit(self) -> None:
        for length in range(9, 14):
            display = format_hemp_id("1" * length)
            assert len(display.split(" ")[-1]) >= 2


class TestPhone:
    @pytest.mark.parametrize(
        "raw", ["03001234567", "0300-1234567", "+92 300 1234567", "0092 300 1234567"]
    )
    def test_pakistani_forms_normalise_to_e164(self, raw: str) -> None:
        assert normalise_phone(raw, "PK") == ("+923001234567", "0300-1234567")

    @pytest.mark.parametrize("raw", ["0400-1234567", "0300-123456", "123"])
    def test_rejects_non_mobile_pakistani(self, raw: str) -> None:
        with pytest.raises(ValidationAppError):
            normalise_phone(raw, "PK")

    @pytest.mark.parametrize("raw", ["07700900123", "07700 900123", "+44 7700 900123"])
    def test_uk_forms_normalise_to_e164(self, raw: str) -> None:
        assert normalise_phone(raw, "GB") == ("+447700900123", "07700 900123")

    @pytest.mark.parametrize("raw", ["01632960123", "07700 90012"])
    def test_rejects_non_mobile_uk(self, raw: str) -> None:
        with pytest.raises(ValidationAppError):
            normalise_phone(raw, "GB")

    def test_blank_is_allowed_when_optional(self) -> None:
        assert normalise_phone(None, "PK") == (None, None)
        assert normalise_phone("  ", "GB") == (None, None)

    def test_blank_is_rejected_when_required(self) -> None:
        with pytest.raises(ValidationAppError):
            normalise_phone("", "PK", required=True)


class TestPostcode:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ln43qp", "LN4 3QP"),
            ("LN4 3QP", "LN4 3QP"),
            (" cb23  6dp ", "CB23 6DP"),
            ("sw1a1aa", "SW1A 1AA"),
            ("m11ae", "M1 1AE"),
        ],
    )
    def test_normalises_case_and_spacing(self, raw: str, expected: str) -> None:
        assert normalise_postcode(raw) == expected

    @pytest.mark.parametrize("raw", ["", "NOTAPOSTCODE", "12345", "LN4"])
    def test_rejects_invalid(self, raw: str) -> None:
        with pytest.raises(ValidationAppError):
            normalise_postcode(raw)


class TestNames:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("muhammad imran khan", "Muhammad Imran Khan"),
            ("ALI RAZA", "Ali Raza"),
            ("o'neill", "O'neill"),
            ("McDonald Smith", "McDonald Smith"),
            ("  double   spaces ", "Double Spaces"),
        ],
    )
    def test_title_cases_without_destroying_internal_capitals(
        self, raw: str, expected: str
    ) -> None:
        assert normalise_person_name(raw, field="name", label="Name") == expected

    @pytest.mark.parametrize("raw", ["ab", "", "Imran123", "Imran@Khan", "x" * 61])
    def test_rejects_short_long_and_illegal_characters(self, raw: str) -> None:
        with pytest.raises(ValidationAppError):
            normalise_person_name(raw, field="name", label="Name")

    def test_keeps_non_latin_scripts(self) -> None:
        assert normalise_person_name("محمد عمران", field="name", label="Name") == "محمد عمران"

    def test_title_case_helper_is_idempotent(self) -> None:
        once = title_case_name("ali raza")
        assert title_case_name(once) == once

    def test_farm_and_village(self) -> None:
        assert normalise_farm_name(" Fen End Farm ") == "Fen End Farm"
        assert normalise_village("Basti Malook") == "Basti Malook"
        with pytest.raises(ValidationAppError):
            normalise_village("a")
        with pytest.raises(ValidationAppError):
            normalise_farm_name("")


class TestLicence:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("ho-hemp-2026-0041", "HO-HEMP-2026-0041"), (" HO 123456 ", "HO123456")],
    )
    def test_uppercases_and_strips(self, raw: str, expected: str) -> None:
        assert normalise_licence_no(raw) == expected

    @pytest.mark.parametrize("raw", ["", "HO12", "HO_1234567", "X" * 31])
    def test_rejects_invalid(self, raw: str) -> None:
        with pytest.raises(ValidationAppError):
            normalise_licence_no(raw)


class TestMaskingAndSanitising:
    def test_cnic_mask_keeps_the_last_four_and_the_shape(self) -> None:
        assert mask_id_number("35202-1234567-1") == "*****-****567-1"

    def test_hemp_id_mask(self) -> None:
        # Nine digits, the last four kept: "6 789" stays, the first five are masked.
        assert mask_id_number("123 456 789") == "*** **6 789"

    def test_phone_mask_keeps_the_prefix_and_last_three(self) -> None:
        assert mask_phone("0300-1234567") == "0300-****567"
        assert mask_phone(None) is None

    def test_sanitise_strips_control_characters_and_collapses_space(self) -> None:
        assert sanitise_text("Basti​  Malook\n") == "Basti Malook"
        assert sanitise_text("   ") is None
        assert sanitise_text(None) is None

    def test_crop_validation(self) -> None:
        assert validate_crop("Cotton") == "cotton"
        assert validate_crop("hemp") == "hemp"
        with pytest.raises(ValidationAppError):
            validate_crop("wheat")
