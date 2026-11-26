"""v1/F-02 — Build evaluation set T-01 from the demo requests in SRC-01."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from backend.config import Settings
from evals.build_eval_set import MIN_TAG_COUNTS, build_eval_set
from evals.case_schema import load_case
from tests.conftest import FakeVolumeRepository

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN_CASE = json.loads((FIXTURES_DIR / "case_GE-001.json").read_text(encoding="utf-8"))
GOLDEN_MESSAGE = (FIXTURES_DIR / "golden_message_M1.txt").read_bytes()
ATTACHMENT_NAME = "BE25112601_RAIL-DIN 35MM X 7.5MM.pdf"

# Tags rotated over the SYN copies so that every MIN_TAG_COUNTS minimum is met.
ROTATED_TAGS = ["injection", "not_pir_sl", "multilingual", "both_pir_and_sl", "scanned"]


class FakeSqlRunner:
    """Records every executed statement; answers the three DQ queries for ``rows`` rows."""

    def __init__(self, rows: int = 0) -> None:
        self.rows = rows
        self.statements: list[tuple[str, dict[str, Any]]] = []

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> list[tuple[Any, ...]]:
        self.statements.append((sql, dict(params or {})))
        text = " ".join(sql.split()).upper()
        if not text.startswith("SELECT"):
            return []
        if "COUNT(DISTINCT CASE_ID)" in text:
            return [(True,)]
        if "IS NULL" in text:
            return [(0,)]
        return [(self.rows,)]

    def kinds(self) -> list[str]:
        return [" ".join(sql.split()).split(" ")[0].upper() for sql, _ in self.statements]


def _put_case(
    files: FakeVolumeRepository, root: str, case: dict[str, Any], attachment: bool = True
) -> str:
    case_dir = f"{root}/{case['case_id']}"
    files.put(f"{case_dir}/case.json", json.dumps(case).encode("utf-8"))
    files.put(f"{case_dir}/message_01.txt", GOLDEN_MESSAGE)
    if attachment:
        files.put(f"{case_dir}/{ATTACHMENT_NAME}", b"%")
    return case_dir


def _put_cases(files: FakeVolumeRepository, root: str, n_copies: int) -> None:
    _put_case(files, root, GOLDEN_CASE)
    for i in range(n_copies):
        case = copy.deepcopy(GOLDEN_CASE)
        case["case_id"] = f"SYN-{i + 1:03d}"
        case["tags"] = ["synthetic", ROTATED_TAGS[i % len(ROTATED_TAGS)]]
        case["is_synthetic"] = True
        _put_case(files, root, case)


def _normalised(sql: str) -> str:
    return " ".join(sql.split())


def test_f02_ac1_load_golden_case(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    case_dir = _put_case(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, GOLDEN_CASE)

    case = load_case(case_dir, fake_volume_repository)

    assert case.case_id == "GE-001"
    assert case.expected_request_type == "update_pir"
    assert case.tags == ["golden", "demo", "conflict", "computed"]
    assert len(case.expected_line_items) == 2
    assert case.attachment_paths == [f"{case_dir}/{ATTACHMENT_NAME}"]
    assert case.messages[0].startswith("Could you update PIR data")
    assert json.loads(case.messages_json) == [{"text": case.messages[0]}]


def test_f02_ac2_build_writes_rows(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    _put_cases(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, 33)
    sql = FakeSqlRunner(rows=34)

    written = build_eval_set(settings, 1, sql, fake_volume_repository)

    assert written == 34
    assert sql.kinds() == ["CREATE", "DELETE", "INSERT", "SELECT", "SELECT", "SELECT"]
    create_sql = _normalised(sql.statements[0][0])
    assert create_sql.startswith(
        "CREATE TABLE IF NOT EXISTS sandbox_others.sco_001_poc.eval_pir_sl_extraction_chat"
    )
    delete_sql, delete_params = sql.statements[1]
    assert _normalised(delete_sql) == f"DELETE FROM {settings.EVAL_TABLE} WHERE version = :v"
    assert delete_params == {"v": 1}
    insert_sql, insert_params = sql.statements[2]
    assert _normalised(insert_sql).startswith(f"INSERT INTO {settings.EVAL_TABLE}")
    assert _normalised(insert_sql).count("current_date()") == 34
    case_ids = sorted(v for k, v in insert_params.items() if k.startswith("case_id_"))
    assert case_ids == ["GE-001"] + [f"SYN-{i:03d}" for i in range(1, 34)]
    assert {v for k, v in insert_params.items() if k.startswith("version_")} == {1}
    dq = [(_normalised(dq_sql), dq_params) for dq_sql, dq_params in sql.statements[3:]]
    assert [params for _, params in dq] == [{"v": 1}] * 3
    dq_sql_texts = [text for text, _ in dq]
    assert dq_sql_texts.count(f"SELECT COUNT(*) FROM {settings.EVAL_TABLE} WHERE version = :v") == 1
    grain = [t for t in dq_sql_texts if "COUNT(*) = COUNT(DISTINCT case_id)" in t]
    nulls = [t for t in dq_sql_texts if "case_id IS NULL OR expected_request_type IS NULL" in t]
    assert len(grain) == 1
    assert len(nulls) == 1
    for text in grain + nulls:
        assert f"FROM {settings.EVAL_TABLE} WHERE version = :v" in text


def test_f02_ac3_too_few_cases(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    _put_cases(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, 11)
    sql = FakeSqlRunner()

    with pytest.raises(ValueError) as error:
        build_eval_set(settings, 1, sql, fake_volume_repository)

    assert str(error.value) == "Evaluation set needs at least 30 cases, found 12"
    assert "INSERT" not in sql.kinds()
    assert sql.statements == []


def test_f02_ac4_personal_data_rejected(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    case = copy.deepcopy(GOLDEN_CASE)
    case["expected_line_items"][0]["fields"]["supplier"] = "kim@vendor.com"
    case_dir = _put_case(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, case)

    with pytest.raises(ValueError, match="must not contain personal data") as error:
        load_case(case_dir, fake_volume_repository)

    assert str(error.value) == "GE-001: expected values must not contain personal data"


# --- §7 edge cases ---------------------------------------------------------------------------


def test_f02_edge_empty_volume(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    sql = FakeSqlRunner()

    with pytest.raises(ValueError) as error:
        build_eval_set(settings, 1, sql, fake_volume_repository)

    assert str(error.value) == f"No case folders found under {settings.VOLUME_DEMO_REQUESTS}"
    assert sql.statements == []


def test_f02_edge_missing_tag_minimum(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    root = settings.VOLUME_DEMO_REQUESTS
    _put_case(fake_volume_repository, root, GOLDEN_CASE)
    for i in range(33):
        case = copy.deepcopy(GOLDEN_CASE)
        case["case_id"] = f"SYN-{i + 1:03d}"
        tags = [t for t in ROTATED_TAGS if t != "injection"]
        case["tags"] = ["synthetic", tags[i % len(tags)]]
        _put_case(fake_volume_repository, root, case)
    sql = FakeSqlRunner()

    with pytest.raises(ValueError) as error:
        build_eval_set(settings, 1, sql, fake_volume_repository)

    assert str(error.value) == "Tag injection needs at least 3 cases, found 0"
    assert sql.statements == []


def test_f02_edge_invalid_request_type(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    case = copy.deepcopy(GOLDEN_CASE)
    case["expected_request_type"] = "update"
    case_dir = _put_case(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, case)

    with pytest.raises(ValueError) as error:
        load_case(case_dir, fake_volume_repository)

    assert str(error.value).startswith("GE-001: expected_request_type must be one of ")


def test_f02_edge_invalid_case_id(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    case = copy.deepcopy(GOLDEN_CASE)
    case["case_id"] = "GE-1"
    case_dir = _put_case(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, case)

    with pytest.raises(ValueError, match="case_id"):
        load_case(case_dir, fake_volume_repository)


def test_f02_edge_field_key_not_in_doc_type(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    case = copy.deepcopy(GOLDEN_CASE)
    case["expected_line_items"][0]["fields"]["fixed_vendor"] = "X"  # SL-only field on a PIR line
    case_dir = _put_case(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, case)

    with pytest.raises(ValueError, match="fixed_vendor"):
        load_case(case_dir, fake_volume_repository)


def test_f02_edge_messages_in_lexical_order(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    case_dir = _put_case(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, GOLDEN_CASE)
    fake_volume_repository.put(f"{case_dir}/message_02.txt", b"Sorry, amount is 7,100")

    case = load_case(case_dir, fake_volume_repository)

    assert len(case.messages) == 2
    assert case.messages[1] == "Sorry, amount is 7,100"
    assert case.attachment_paths == [f"{case_dir}/{ATTACHMENT_NAME}"]


def test_f02_edge_rerun_same_version(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    _put_cases(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, 33)
    sql = FakeSqlRunner(rows=34)

    first = build_eval_set(settings, 1, sql, fake_volume_repository)
    second = build_eval_set(settings, 1, sql, fake_volume_repository)

    assert first == second == 34
    assert sql.kinds() == ["CREATE", "DELETE", "INSERT", "SELECT", "SELECT", "SELECT"] * 2


class DirAwareVolume(FakeVolumeRepository):
    """FakeVolumeRepository that also knows directories, including empty ones (like the volume)."""

    def __init__(self) -> None:
        super().__init__()
        self.dirs: set[str] = set()

    def list_dirs(self, prefix: str) -> list[str]:
        prefix = prefix.rstrip("/")
        derived = {
            f"{prefix}/{p[len(prefix) + 1 :].split('/', 1)[0]}"
            for p in self.files
            if p.startswith(prefix + "/") and "/" in p[len(prefix) + 1 :]
        }
        return sorted(derived | {d for d in self.dirs if d.rsplit("/", 1)[0] == prefix})


def test_f02_edge_folder_without_case_json(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    root = settings.VOLUME_DEMO_REQUESTS
    _put_cases(fake_volume_repository, root, 33)
    fake_volume_repository.put(f"{root}/DEMO-099/message_01.txt", GOLDEN_MESSAGE)
    sql = FakeSqlRunner(rows=34)

    with pytest.raises(ValueError) as error:
        build_eval_set(settings, 1, sql, fake_volume_repository)

    assert str(error.value) == f"{root}/DEMO-099: case.json not found"
    assert sql.statements == []


def test_f02_edge_empty_case_folder(settings: Settings) -> None:
    root = settings.VOLUME_DEMO_REQUESTS
    files = DirAwareVolume()
    _put_cases(files, root, 33)
    files.dirs.add(f"{root}/DEMO-098")
    sql = FakeSqlRunner(rows=34)

    with pytest.raises(ValueError) as error:
        build_eval_set(settings, 1, sql, files)

    assert str(error.value) == f"{root}/DEMO-098: case.json not found"
    assert sql.statements == []


def test_f02_edge_dir_aware_volume_builds(settings: Settings) -> None:
    files = DirAwareVolume()
    _put_cases(files, settings.VOLUME_DEMO_REQUESTS, 33)
    sql = FakeSqlRunner(rows=34)

    assert build_eval_set(settings, 1, sql, files) == 34


def test_f02_edge_case_id_trailing_newline(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    case = copy.deepcopy(GOLDEN_CASE)
    case["case_id"] = "GE-001\n"
    case_dir = _put_case(fake_volume_repository, settings.VOLUME_DEMO_REQUESTS, case)

    with pytest.raises(ValueError, match="case_id must match"):
        load_case(case_dir, fake_volume_repository)


def test_f02_edge_case_id_differs_from_folder(
    settings: Settings, fake_volume_repository: FakeVolumeRepository
) -> None:
    root = settings.VOLUME_DEMO_REQUESTS
    fake_volume_repository.put(f"{root}/DEMO-001/case.json", json.dumps(GOLDEN_CASE).encode())
    fake_volume_repository.put(f"{root}/DEMO-001/message_01.txt", GOLDEN_MESSAGE)

    with pytest.raises(ValueError, match="must equal the folder name"):
        load_case(f"{root}/DEMO-001", fake_volume_repository)


def test_f02_min_tag_counts_cover_ex_v1_3() -> None:
    assert MIN_TAG_COUNTS == {
        "golden": 1,
        "injection": 3,
        "not_pir_sl": 3,
        "multilingual": 3,
        "conflict": 1,
        "computed": 1,
        "both_pir_and_sl": 1,
        "scanned": 1,
    }
