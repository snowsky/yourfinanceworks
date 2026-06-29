from core.services.invoice_render.config import (
    build_config, InvoiceTemplateConfig,
    ALLOWED_FONTS, ALLOWED_LOGO_PLACEMENTS, ALLOWED_LOGO_SIZES,
    ALLOWED_SECTIONS, DEFAULT_SECTION_ORDER, ALLOWED_CUSTOM_FIELDS_LAYOUTS,
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


def test_section_order_allowed_set_and_default():
    assert ALLOWED_SECTIONS == ("billto", "custom", "items", "totals", "notes")
    assert DEFAULT_SECTION_ORDER == ["billto", "custom", "items", "totals", "notes"]


def test_build_config_default_section_order_when_absent():
    assert build_config({}).section_order == DEFAULT_SECTION_ORDER


def test_build_config_reads_valid_section_order():
    order = ["notes", "totals", "items", "custom", "billto"]
    assert build_config({"section_order": order}).section_order == order


def test_build_config_drops_unknown_section_ids():
    c = build_config({"section_order": ["notes", "bogus", "items"]})
    # unknown dropped, then missing appended in canonical order
    assert c.section_order == ["notes", "items", "billto", "custom", "totals"]


def test_build_config_dedupes_section_order():
    c = build_config({"section_order": ["items", "items", "billto"]})
    assert c.section_order == ["items", "billto", "custom", "totals", "notes"]


def test_build_config_appends_missing_sections():
    c = build_config({"section_order": ["totals"]})
    assert c.section_order == ["totals", "billto", "custom", "items", "notes"]


def test_build_config_section_order_non_list_falls_back_to_default():
    assert build_config({"section_order": "items,billto"}).section_order == DEFAULT_SECTION_ORDER


def test_default_columns_and_layout_when_absent():
    c = build_config({})
    assert c.columns == {"quantity": True, "unit_price": True, "unit_of_measure": False}
    assert c.custom_fields_layout == "list"


def test_build_config_reads_column_flags():
    c = build_config({
        "show_col_quantity": False,
        "show_col_unit_price": True,
        "show_col_unit_of_measure": True,
    })
    assert c.columns == {"quantity": False, "unit_price": True, "unit_of_measure": True}


def test_build_config_coerces_column_flags_to_bool():
    c = build_config({"show_col_quantity": 0, "show_col_unit_of_measure": 1})
    assert c.columns["quantity"] is False
    assert c.columns["unit_of_measure"] is True
    assert c.columns["unit_price"] is True  # untouched default


def test_build_config_reads_valid_layout():
    assert build_config({"custom_fields_layout": "grid"}).custom_fields_layout == "grid"


def test_build_config_clamps_unknown_layout_to_list():
    assert build_config({"custom_fields_layout": "fancy"}).custom_fields_layout == "list"


def test_allowed_layouts_constant():
    assert ALLOWED_CUSTOM_FIELDS_LAYOUTS == ("list", "grid")
