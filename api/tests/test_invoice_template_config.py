from core.services.invoice_render.config import (
    build_config, InvoiceTemplateConfig,
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES,
)


def test_allowed_sets_are_the_documented_values():
    assert ALLOWED_FONTS == ("sans", "serif", "mono")
    assert ALLOWED_LOGO_PLACEMENTS == ("left", "center", "right")
    assert ALLOWED_LOGO_SIZES == ("small", "medium", "large")


def test_build_config_defaults_when_empty():
    c = build_config({})
    assert isinstance(c, InvoiceTemplateConfig)
    assert c.font_family == "sans"
    assert c.logo_placement == "left"
    assert c.logo_size == "medium"
    assert c.brand_color == "#1e3a8a"
    assert c.accent_color == "#3b82f6"
    assert c.footer_text == ""
    assert c.show == {"logo": True, "notes": True, "custom_fields": True, "footer": True}


def test_build_config_reads_valid_values():
    c = build_config({"font_family": "serif", "logo_placement": "center",
                      "logo_size": "large", "brand_color": "#abcdef",
                      "accent_color": "#123456", "footer_text": "Thanks"})
    assert c.font_family == "serif"
    assert c.logo_placement == "center"
    assert c.logo_size == "large"
    assert c.brand_color == "#abcdef"
    assert c.accent_color == "#123456"
    assert c.footer_text == "Thanks"


def test_build_config_clamps_invalid_enums_to_defaults():
    c = build_config({"font_family": "comic", "logo_placement": "diagonal", "logo_size": "huge"})
    assert c.font_family == "sans"
    assert c.logo_placement == "left"
    assert c.logo_size == "medium"


def test_build_config_clamps_invalid_color():
    c = build_config({"brand_color": "red", "accent_color": "#xyz"})
    assert c.brand_color == "#1e3a8a"
    assert c.accent_color == "#3b82f6"


def test_build_config_reads_show_toggles():
    c = build_config({"show_logo": False, "show_notes": False,
                      "show_custom_fields": False, "show_footer": False})
    assert c.show == {"logo": False, "notes": False, "custom_fields": False, "footer": False}
