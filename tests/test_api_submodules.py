import pytest

import historia
import historia.data
import historia.project
import historia.project.update


@pytest.mark.ai_generated
def test_global_init_exposes_submodules() -> None:
    assert hasattr(historia, "data")
    assert hasattr(historia, "project")


@pytest.mark.ai_generated
def test_global_init_does_not_expose_bound_functions() -> None:
    assert hasattr(historia, "add_to_project") is False
    assert hasattr(historia, "dump_info_for_date") is False
    assert hasattr(historia, "fetch_info_for_date") is False
    assert hasattr(historia, "update") is False


@pytest.mark.ai_generated
def test_submodule_exports_remain_available() -> None:
    assert hasattr(historia.data, "dump_info_for_date")
    assert hasattr(historia.data, "dump_specific_info")
    assert hasattr(historia.data, "fetch_info_for_date")
    assert hasattr(historia.data, "update")
    assert hasattr(historia.project, "add_to_project")
    assert hasattr(historia.project, "create_project_page")
    assert hasattr(historia.project, "move_done_to_history")
    assert hasattr(historia.project.update, "update_project_item_dates")
