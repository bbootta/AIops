from middleware import permission_guard as pg


def test_detects_rm_rf():
    out = pg.check_commands(["rm -rf /tmp/foo"])
    assert out["clean"] is False
    assert any(f["category"] == "destructive_fs" for f in out["findings"])


def test_detects_force_push_and_no_verify():
    out = pg.check_commands(
        [
            "git push --force origin main",
            "git commit -m 'x' --no-verify",
        ]
    )
    cats = {f["category"] for f in out["findings"]}
    assert "force_push" in cats
    assert "skip_hook" in cats


def test_detects_db_destructive_sql():
    out = pg.check_commands(["DROP TABLE customers;", "TRUNCATE TABLE accounts"])
    cats = {f["category"] for f in out["findings"]}
    assert "ops_db" in cats


def test_detects_credential_exposure():
    text = "AWS_KEY=AKIAABCDEFGHIJKLMNOP"
    out = pg.detect_permission_violations(text)
    assert any(f.category == "credential_exposure" for f in out)


def test_clean_command_passes():
    out = pg.check_commands(["pytest -q", "ls -la"])
    assert out["clean"] is True
    assert out["findings"] == []
