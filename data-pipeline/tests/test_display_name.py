"""Tests for src/utils/display_name.py (curation overlay contract #2)."""

from src.utils.display_name import to_display_name


class TestAllCapsNormalization:
    def test_plain_all_caps_title_cased(self):
        assert to_display_name("ISLAMIC RELIEF USA") == "Islamic Relief USA"

    def test_acronym_only_name_kept_uppercase(self):
        assert to_display_name("UNRWA USA") == "UNRWA USA"

    def test_particles_lowercased_when_not_first(self):
        assert (
            to_display_name("HELPING HAND FOR RELIEF AND DEVELOPMENT")
            == "Helping Hand for Relief and Development"
        )

    def test_hyphen_segments_title_cased_separately(self):
        assert to_display_name("AL-ANON FAMILY GROUP") == "Al-Anon Family Group"

    def test_apostrophe_segments_title_cased_separately(self):
        assert to_display_name("SANTA CLARA VALLEY O'BRIEN") == "Santa Clara Valley O'Brien"

    def test_inc_special_case(self):
        assert to_display_name("FEEDING AMERICA INC.") == "Feeding America Inc."

    def test_tokens_with_digits_pass_through(self):
        assert to_display_name("EXAMPLE 501(C)(3) FUND") == "Example 501(C)(3) Fund"

    def test_internal_period_token_passes_through(self):
        assert to_display_name("U.S. RELIEF FUND") == "U.S. Relief Fund"

    def test_parenthesized_token_gets_titled_at_first_alpha(self):
        assert to_display_name("UNITED RELIEF (GROUP)") == "United Relief (Group)"


class TestPassthrough:
    def test_mixed_case_input_unchanged(self):
        assert to_display_name("Zakat Foundation of America") == "Zakat Foundation of America"

    def test_mixed_case_with_acronym_unchanged(self):
        assert to_display_name("HHRD (Helping Hand for Relief and Development)") == (
            "HHRD (Helping Hand for Relief and Development)"
        )

    def test_empty_string(self):
        assert to_display_name("") == ""
