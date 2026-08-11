"""Round 21 — v2 Phase 4 (CLI) + Phase 5 정책 인덱스."""



# ---------- policy index ----------

def test_list_policies_excludes_schema_and_manifest():
    from vta.policies import list_policies

    items = list_policies()
    names = {n for n, _ in items}
    # SSoT 정책들이 포함되어야 한다
    assert "orchestration_matrix" in names
    assert "permission_matrix" in names
    assert "capital_adequacy_thresholds" in names
    # schema / manifest 는 제외
    for n in names:
        assert not n.endswith(".schema")
        assert n != "change_manifest"


def test_list_policies_returns_existing_paths():
    from vta.policies import list_policies

    for name, path in list_policies():
        assert path.exists(), f"{name} → {path} 존재하지 않음"
        assert path.is_file()


def test_list_schemas_present():
    from vta.policies import list_schemas

    schemas = {n for n, _ in list_schemas()}
    assert "change_manifest" in schemas
    assert "orchestration_matrix" in schemas


# ---------- vta CLI ----------

def test_vta_cli_help_runs(capsys):
    from vta.cli.__main__ import main

    rc = main(["--help"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Available subcommands" in out


def test_vta_cli_no_args_prints_help(capsys):
    from vta.cli.__main__ import main

    rc = main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "subcommand" in out.lower()


def test_vta_cli_unknown_subcommand_returns_nonzero(capsys):
    from vta.cli.__main__ import main

    rc = main(["totallymadeupcmd"])
    err = capsys.readouterr().err
    assert rc != 0
    assert "unknown" in err.lower()


def test_vta_cli_policy_list_runs(capsys):
    from vta.cli.__main__ import main

    rc = main(["policy", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "orchestration_matrix" in out


def test_vta_cli_policy_show_runs(capsys):
    from vta.cli.__main__ import main

    rc = main(["policy", "show", "orchestration_matrix"])
    out = capsys.readouterr().out
    assert rc == 0
    assert '"steps"' in out


def test_vta_cli_policy_show_missing_name_fails(capsys):
    from vta.cli.__main__ import main

    rc = main(["policy", "show"])
    assert rc != 0


def test_vta_cli_dispatches_to_manifest_validate(capsys):
    from vta.cli.__main__ import main

    rc = main(["manifest", "validate"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "manifest" in out.lower()


def test_vta_cli_dispatches_to_classify(capsys):
    from vta.cli.__main__ import main

    rc = main(["classify", "classify", "--text", "PermissionError: denied"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "permission" in out.lower()


# ---------- v1 동작 보존 ----------

def test_v1_modules_still_directly_runnable():
    """v2 CLI 도입 후에도 v1 module 단독 실행이 동일해야."""
    import tools.manifest
    import tools.classify_error
    import tools.policy_lint

    # 모듈 import 만으로 동작 가능 (side effect 없음)
    assert hasattr(tools.manifest, "validate")
    assert hasattr(tools.classify_error, "classify")
    assert hasattr(tools.policy_lint, "lint_policies")
