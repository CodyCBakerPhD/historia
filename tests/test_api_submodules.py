import pytest

import historia
import historia._cli
import historia.data
import historia.project


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("attribute_name", "is_exposed"),
    [
        ("data", True),
        ("github", True),
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
    ("module", "attribute_name", "is_exposed"),
    [
        (historia, "github", True),
        (historia.data, "dump_info_for_date", False),
        (historia.data, "dump_specific_info", False),
        (historia.data, "fetch_info_for_date", False),
        (historia.data, "update", False),
        (historia.github, "dump_info_for_date", True),
        (historia.github, "dump_specific_info", True),
        (historia.github, "fetch_info_for_date", True),
        (historia.github, "update", True),
        (historia.project, "add_to_project", True),
        (historia.project, "create_project_page", True),
        (historia.project, "transition_status", True),
        (historia.project, "update_project_item_dates", True),
    ],
)
def test_submodule_exports_remain_available(module: object, attribute_name: str, is_exposed: bool) -> None:
    assert hasattr(module, attribute_name) == is_exposed
