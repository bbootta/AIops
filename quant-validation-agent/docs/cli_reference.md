# CLI Reference

자동 생성 (`python -m quant_validation_agent docs-cli`). 직접 편집하지 말 것.

버전: `0.1.0`

## Top-level

```
usage: quant_validation_agent [-h] [--version]
                              {run,thresholds,check,validate,policy-governance,policy-lock,summary,version,docs-cli,note,report,validate-pd-calibration,validate-scenario}
                              ...

Quantitative validation agent — local-only CLI.

positional arguments:
  {run,thresholds,check,validate,policy-governance,policy-lock,summary,version,docs-cli,note,report,validate-pd-calibration,validate-scenario}
    run                 Read a validation request and print a plan.
    thresholds          Print threshold policy.
    check               Run permission/PII guards on input.
    validate            Run a small end-to-end validation pass on a local CSV.
    policy-governance   Audit threshold_policy governance: manifest approvals
                        + lock digest.
    policy-lock         Inspect or update threshold_policy.lock.json. Defaults
                        to dry-run.
    summary             Aggregate one-line RAG summary across multiple
                        validate* JSON outputs.
    version             Emit version metadata as JSON (package, version,
                        python, platform).
    docs-cli            Capture every subcommand --help into
                        docs/cli_reference.md.
    note                Append a recurring-finding note.
    report              Render a validate JSON report into the standard
                        9-section markdown.
    validate-pd-calibration
                        PD calibration validation (Brier, bias, Hosmer-
                        Lemeshow, Spiegelhalter Z, binomial).
    validate-scenario   Run the scenario regression pipeline on local CSV
                        inputs.

options:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
```

## `check`

```
usage: quant_validation_agent check [-h] (--path PATH | --text TEXT)

options:
  -h, --help   show this help message and exit
  --path PATH  Path to a text file to scan.
  --text TEXT  Inline text to scan.
```

## `docs-cli`

```
usage: quant_validation_agent docs-cli [-h] [--out OUT]

options:
  -h, --help  show this help message and exit
  --out OUT   Override output path (defaults to docs/cli_reference.md).
```

## `note`

```
usage: quant_validation_agent note [-h] --text TEXT [--model MODEL]
                                   [--path PATH]
                                   {add}

positional arguments:
  {add}

options:
  -h, --help     show this help message and exit
  --text TEXT    The note text (single line).
  --model MODEL  Model name or type for the note.
  --path PATH    Override target file path.
```

## `policy-governance`

```
usage: quant_validation_agent policy-governance [-h]
                                                [--policy-path POLICY_PATH]
                                                [--manifest-path MANIFEST_PATH]
                                                [--lock-path LOCK_PATH]
                                                [--require-lock] [--json-only]
                                                [--exit-on-yellow]

options:
  -h, --help            show this help message and exit
  --policy-path POLICY_PATH
  --manifest-path MANIFEST_PATH
  --lock-path LOCK_PATH
  --require-lock        Exit 7 when the lock is missing or drifted.
  --json-only           Emit compact single-line JSON for jq pipelines.
  --exit-on-yellow      Exit 1 when the lock is missing/drifted, even though
                        manifest approvals are intact. Useful as a CI
                        'warning' gate that does not block hard like
                        --require-lock (which exits 7).
```

## `policy-lock`

```
usage: quant_validation_agent policy-lock [-h] --change-id CHANGE_ID
                                          [--confirm]
                                          [--policy-path POLICY_PATH]
                                          [--lock-path LOCK_PATH]
                                          [--manifest-path MANIFEST_PATH]
                                          [--skip-manifest-check]

options:
  -h, --help            show this help message and exit
  --change-id CHANGE_ID
                        Approved change_id of the form CHG-####.
  --confirm             Required to actually write the lock file.
  --policy-path POLICY_PATH
  --lock-path LOCK_PATH
  --manifest-path MANIFEST_PATH
                        Path to change_manifest.json (defaults to
                        harness/change_manifest.json).
  --skip-manifest-check
                        Skip the manifest pre-check (advanced; not
                        recommended).
```

## `report`

```
usage: quant_validation_agent report [-h] [--input INPUT]
                                     [--scenario-input SCENARIO_INPUT]
                                     [--threshold-overrides THRESHOLD_OVERRIDES]
                                     [--include-stationarity-rag]
                                     [--max-rows MAX_ROWS] [--out OUT]

options:
  -h, --help            show this help message and exit
  --input INPUT         Path to a validate JSON report (scoring/PD/LGD/EAD).
  --scenario-input SCENARIO_INPUT
                        Path to a validate-scenario JSON report.
  --threshold-overrides THRESHOLD_OVERRIDES
                        Optional path to an alternative threshold_policy.json.
                        Always schema-validated before use.
  --include-stationarity-rag
                        Opt-in: emit a stationarity RAG block (target
                        stationary => Green; any non-stationary feature =>
                        Yellow; non-stationary target => Red). Sample-size
                        sensitive — see CLAUDE.md limitations.
  --max-rows MAX_ROWS   Truncate every table in the report to this many rows.
                        A note is appended indicating the number of truncated
                        rows.
  --out OUT             Optional path to write the markdown report.
```

## `run`

```
usage: quant_validation_agent run [-h] --request REQUEST

options:
  -h, --help         show this help message and exit
  --request REQUEST  Path to a request markdown file.
```

## `summary`

```
usage: quant_validation_agent summary [-h] --input INPUT [--fail-on-red]
                                      [--json-only] [--out OUT]

options:
  -h, --help     show this help message and exit
  --input INPUT  Repeatable. JSON file produced by validate / validate-pd-
                 calibration / validate-scenario.
  --fail-on-red  Exit 6 when any input is Red.
  --json-only    Compact single-line JSON for jq pipelines.
  --out OUT      Optional path to write the summary JSON.
```

## `thresholds`

```
usage: quant_validation_agent thresholds [-h] [--metric METRIC]
                                         [--model-type MODEL_TYPE]
                                         [--segment SEGMENT] [--path PATH]

options:
  -h, --help            show this help message and exit
  --metric METRIC       Single metric to look up.
  --model-type MODEL_TYPE
                        List metrics for a model type.
  --segment SEGMENT     Apply segment-level overrides if present.
  --path PATH           Override path to threshold_policy.json.
```

## `validate`

```
usage: quant_validation_agent validate [-h] --data DATA --model-type
                                       {scoring,pd,lgd,ead} [--target TARGET]
                                       [--score SCORE] [--actual ACTUAL]
                                       [--predicted PREDICTED]
                                       [--higher-is-worse]
                                       [--dataset-col DATASET_COL]
                                       [--baseline-value BASELINE_VALUE]
                                       [--segment SEGMENT] [--decile-rag]
                                       [--ead-normalizer {mean_realized,mean_predicted,total_exposure}]
                                       [--segment-detail]
                                       [--segment-col SEGMENT_COL] [--out OUT]
                                       [--log-dir LOG_DIR]

options:
  -h, --help            show this help message and exit
  --data DATA           Path to the CSV file.
  --model-type {scoring,pd,lgd,ead}
  --target TARGET       Target column (scoring/pd).
  --score SCORE         Score or PD column (scoring/pd).
  --actual ACTUAL       Realized column (lgd/ead).
  --predicted PREDICTED
                        Predicted column (lgd/ead).
  --higher-is-worse     Set when higher score implies higher risk (default
                        off).
  --dataset-col DATASET_COL
                        Column splitting baseline vs current for PSI.
  --baseline-value BASELINE_VALUE
                        Value of dataset-col denoting baseline (e.g., dev).
  --segment SEGMENT     Segment label for threshold overrides.
  --decile-rag          Also emit RAG for the top-decile lift (scoring/PD
                        only).
  --ead-normalizer {mean_realized,mean_predicted,total_exposure}
                        Override the EAD-error normalizer from
                        threshold_policy.json.
  --segment-detail      LGD/EAD: emit per-segment MAE/RMSE/bias under
                        report.segment_detail.
  --segment-col SEGMENT_COL
                        Column to group by for --segment-detail.
  --out OUT             Optional path to write the JSON report.
  --log-dir LOG_DIR     Optional directory to write a run-log JSON via
                        middleware.run_logger.
```

## `validate-pd-calibration`

```
usage: quant_validation_agent validate-pd-calibration [-h] --data DATA
                                                      --pred-col PRED_COL
                                                      --default-col
                                                      DEFAULT_COL
                                                      [--count-col COUNT_COL]
                                                      [--bucket-col BUCKET_COL]
                                                      [--hl-bins HL_BINS]
                                                      [--hl-min-per-bin HL_MIN_PER_BIN]
                                                      [--binomial-alpha BINOMIAL_ALPHA]
                                                      [--hl-rag]
                                                      [--decile-rag]
                                                      [--segment SEGMENT]
                                                      [--out OUT]
                                                      [--out-pattern OUT_PATTERN]
                                                      [--log-dir LOG_DIR]

options:
  -h, --help            show this help message and exit
  --data DATA           Path to the CSV file.
  --pred-col PRED_COL   Column with predicted PD (0-1).
  --default-col DEFAULT_COL
                        Column with realized default count or 0/1 flag.
  --count-col COUNT_COL
                        If set, treat data as pre-aggregated and expand to row
                        level.
  --bucket-col BUCKET_COL
                        Optional bucket column for the per-bucket binomial
                        test.
  --hl-bins HL_BINS
  --hl-min-per-bin HL_MIN_PER_BIN
                        If set, use greedy min-per-bin packing instead of
                        quantile bins.
  --binomial-alpha BINOMIAL_ALPHA
  --hl-rag              Opt-in: also assign RAG to HL and Spiegelhalter
                        p-values. Output is sample-size sensitive; do not use
                        alone for adequacy.
  --decile-rag          Opt-in: also emit RAG for the top-decile lift of
                        pred_pd vs default.
  --segment SEGMENT     Segment label for threshold overrides.
  --out OUT             Optional path to write the JSON report.
  --out-pattern OUT_PATTERN
                        Optional path with strftime tokens; auto-replaces {ts}
                        with the current YYYYMMDD_HHMMSS_ffffff. Useful for
                        accumulating reports.
  --log-dir LOG_DIR     Optional directory for run-log JSON via
                        middleware.run_logger.
```

## `validate-scenario`

```
usage: quant_validation_agent validate-scenario [-h] --hist-data HIST_DATA
                                                --scenario-data SCENARIO_DATA
                                                --target TARGET --features
                                                FEATURES
                                                [--scenario-col SCENARIO_COL]
                                                [--period-col PERIOD_COL]
                                                [--pred-col-in-scenario PRED_COL_IN_SCENARIO]
                                                [--expected-signs EXPECTED_SIGNS]
                                                [--multiplier-floors MULTIPLIER_FLOORS]
                                                [--direction {higher_is_worse,lower_is_worse}]
                                                [--autocorr-lags AUTOCORR_LAGS]
                                                [--skip-stationarity]
                                                [--stationarity-alpha STATIONARITY_ALPHA]
                                                [--max-predictions MAX_PREDICTIONS]
                                                [--include-stationarity-rag]
                                                [--out OUT]
                                                [--out-pattern OUT_PATTERN]
                                                [--log-dir LOG_DIR]

options:
  -h, --help            show this help message and exit
  --hist-data HIST_DATA
                        Historical data CSV for OLS fitting.
  --scenario-data SCENARIO_DATA
                        Scenario data CSV with base/adverse/severe rows.
  --target TARGET       Target column in hist data.
  --features FEATURES   Comma-separated feature column names.
  --scenario-col SCENARIO_COL
                        Scenario label column in scenario data.
  --period-col PERIOD_COL
                        Optional period column for time-aligned severity
                        check.
  --pred-col-in-scenario PRED_COL_IN_SCENARIO
                        If set, use this column instead of model prediction.
  --expected-signs EXPECTED_SIGNS
                        Optional comma-separated expected signs, e.g.
                        gdp=-,unemp=+
  --multiplier-floors MULTIPLIER_FLOORS
                        Optional comma-separated floors per scenario, e.g.
                        base=1.0,severe=1.0
  --direction {higher_is_worse,lower_is_worse}
  --autocorr-lags AUTOCORR_LAGS
                        Lags for Breusch-Godfrey and ARCH tests (default 1).
  --skip-stationarity   Skip ADF stationarity check.
  --stationarity-alpha STATIONARITY_ALPHA
                        Alpha for ADF test (default 0.05).
  --max-predictions MAX_PREDICTIONS
                        Truncate the predictions list to this many rows in the
                        output JSON. Truncated count is reported under
                        'predictions_truncated'.
  --include-stationarity-rag
                        Opt-in: derive stationarity_rag from the ADF results
                        and fold into overall_rag. Sample-size sensitive; see
                        CLAUDE.md limitations.
  --out OUT             Optional path to write the JSON report.
  --out-pattern OUT_PATTERN
                        Optional path with the literal token {ts}; auto-
                        replaces with the current YYYYMMDD_HHMMSS_ffffff
                        timestamp.
  --log-dir LOG_DIR     Optional directory to write a run-log JSON via
                        middleware.run_logger.
```

## `version`

```
usage: quant_validation_agent version [-h] [--json-only]

options:
  -h, --help   show this help message and exit
  --json-only  Compact single-line JSON.
```

