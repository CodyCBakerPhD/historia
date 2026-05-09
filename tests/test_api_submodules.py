import pytest

import historia
import historia._cli
import historia.data
import historia.project
import historia.project.update


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("attribute_name", "is_exposed"),
    [
        ("data", True),
        ("historia_cli", True),
        ("project", True),
        ("add_to_project", False),
        ("dump_info_for_date", False),
        ("fetch_info_for_date", False),
        ("update_project_item_dates", False),
        ("update", False),
    ],
)
def test_global_init_exports(attribute_name: str, is_exposed: bool) -> None:
    assert hasattr(historia, attribute_name) == is_exposed


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("module", "attribute_name"),
    [
        (historia.data, "dump_info_for_date"),
        (historia.data, "dump_specific_info"),
        (historia.data, "fetch_info_for_date"),
        (historia.data, "update"),
        (historia.project, "add_to_project"),
        (historia.project, "create_project_page"),
        (historia.project, "move_done_to_history"),
        (historia.project, "update"),
        (historia.project, "update_project_item_dates"),
        (historia.project.update, "update_project_item_dates"),
    ],
)
def test_submodule_exports_remain_available(module: object, attribute_name: str) -> None:
    assert hasattr(module, attribute_name)
