from pipeline.common import mask_account


def test_mask_account_masks_long_identifier():
    assert mask_account("ACC-1001") == "...1001"


def test_mask_account_returns_short_identifier_unmasked():
    assert mask_account("A1") == "A1"


def test_mask_account_handles_empty_value():
    assert mask_account(None) == "****"
    assert mask_account("") == "****"
