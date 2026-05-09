import pytest

import historia


@pytest.mark.ai_generated
def test_fetch_info_graphql() -> None:
    test_info, _ = historia.fetch_info_for_date(
        info_type="issues_opened",
        date="2026-01-05",
        username="codycbakerphd",
    )
    expected_info = ["https://github.com/con/nwb2bids/issues/252"]
    assert test_info == expected_info


# TODO: add tests for
# - ensuring empty day folders are not created
# - error message for github token
# - ensure overwrite=True creates new file (when current file is empty or partial or incorrect)
# - ensure overwrite=False does not overwrite existing file (even if incorrect)
# - CLI and tests for update API; will require a 'start from date' kwarg to make deterministic
