"""Tests verifying that public API functions enforce input types via beartype."""

import pathlib

import beartype.roar
import pytest

import historia


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "kwargs",
    [
        # `info_type` must be a Literal of allowed strings, not an arbitrary string
        {"info_type": "not_a_real_info_type", "date": "2026-01-05", "username": "codycbakerphd"},
        # `date` must be a str, not an int
        {"info_type": "issues_opened", "date": 20260105, "username": "codycbakerphd"},
        # `username` must be a str, not None
        {"info_type": "issues_opened", "date": "2026-01-05", "username": None},
    ],
)
def test_fetch_info_for_date_rejects_bad_input_types(kwargs: dict) -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.github.fetch_info_for_date(**kwargs)


@pytest.mark.ai_generated
def test_dump_specific_info_rejects_string_directory(tmp_path: pathlib.Path) -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.github.dump_specific_info(
            directory=str(tmp_path),
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )


@pytest.mark.ai_generated
def test_dump_info_for_date_rejects_string_directory(tmp_path: pathlib.Path) -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.github.dump_info_for_date(
            directory=str(tmp_path),
            date="2026-01-05",
            username="codycbakerphd",
        )


@pytest.mark.ai_generated
def test_update_rejects_string_for_int_past_number_of_days(tmp_path: pathlib.Path) -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.github.update(
            directory=tmp_path,
            username="codycbakerphd",
            past_number_of_days="3",
        )


@pytest.mark.ai_generated
def test_update_rejects_string_directory(tmp_path: pathlib.Path) -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.github.update(
            directory=str(tmp_path),
            username="codycbakerphd",
            past_number_of_days=3,
        )


@pytest.mark.ai_generated
def test_add_to_project_rejects_string_directory() -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.project.add_to_project(
            directory="/some/path",
            project_url="https://github.com/users/codycbakerphd/projects/1",
        )


@pytest.mark.ai_generated
def test_add_to_project_rejects_string_for_int_end_date_placeholder_days(tmp_path: pathlib.Path) -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/codycbakerphd/projects/1",
            end_date_placeholder_days="180",
        )


@pytest.mark.ai_generated
def test_add_to_project_rejects_non_mapping_extra_field_values(tmp_path: pathlib.Path) -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/codycbakerphd/projects/1",
            extra_field_values=["Member:Cody"],
        )


@pytest.mark.ai_generated
def test_update_project_item_dates_rejects_non_string_url() -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.project.update_project_item_dates(project_url=12345)


@pytest.mark.ai_generated
def test_transition_status_rejects_non_string_status() -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.project.transition_status(
            project_url="https://github.com/users/codycbakerphd/projects/1",
            current_status="DONE",
            new_status=42,
        )


@pytest.mark.ai_generated
def test_create_project_page_rejects_non_string_owner() -> None:
    with pytest.raises(beartype.roar.BeartypeCallHintParamViolation):
        historia.project.create_project_page(owner=None, title="My Project")
