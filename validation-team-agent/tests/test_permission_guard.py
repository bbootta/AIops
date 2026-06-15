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
    # PII / secret 비유출: findings 어디에도 raw 'AKIA…' 가 노출되지 않는다.
    for f in out:
        assert not hasattr(f, "matched")
        d = f.to_dict()
        assert "matched" not in d
        assert "AKIAABCDEFGHIJKLMNOP" not in str(d)


def test_finding_dict_shape():
    text = "rm -rf /tmp/foo"
    out = pg.detect_permission_violations(text)
    assert out, "expected at least one finding"
    d = out[0].to_dict()
    assert set(d.keys()) == {"category", "pattern", "length", "location"}
    assert isinstance(d["length"], int) and d["length"] > 0
    assert isinstance(d["location"], list) and len(d["location"]) == 2


def test_credential_secret_never_in_check_commands():
    secret = "AKIAABCDEFGHIJKLMNOP"
    out = pg.check_commands([f"export AWS_KEY={secret}"])
    assert out["clean"] is False
    # 명령 자체는 'command' 키에 그대로 남아도, finding payload(secret 매치)는
    # 어떤 곳에도 raw 값을 포함해서는 안 된다.
    for f in out["findings"]:
        assert "matched" not in f
        # length / location 만 노출.
        assert "length" in f and "location" in f


def test_clean_command_passes():
    out = pg.check_commands(["pytest -q", "ls -la"])
    assert out["clean"] is True
    assert out["findings"] == []
