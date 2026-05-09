import pytest

import historia
import historia.data
import historia.project
import historia.project.update


@pytest.mark.ai_generated
def test_data_submodule_matches_top_level_api() -> None:
    assert historia.data.dump_info_for_date is historia.dump_info_for_date
    assert historia.data.dump_specific_info is historia.dump_specific_info
    assert historia.data.fetch_info_for_date is historia.fetch_info_for_date
    assert historia.data.update is historia.update


@pytest.mark.ai_generated
def test_project_submodule_matches_top_level_api() -> None:
    assert historia.project.add_to_project is historia.add_to_project
    assert historia.project.create_project_page is historia.create_project_page
    assert historia.project.move_done_to_history is historia.move_done_to_history
    assert historia.project.update.update_project_item_dates is historia.update_project_item_dates
