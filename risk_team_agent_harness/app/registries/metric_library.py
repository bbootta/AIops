class MetricLibrary:
    SAMPLE_METRICS = {
        "credit_model": ["pd_stability", "calibration_backtest"],
        "rwa": ["rwa_reperformance", "crm_eligibility"],
        "bis_ratio": ["bis_ratio_reconciliation"],
        "ddr": ["delinquency_rate", "default_rate", "recovery_rate"],
        "limit": ["limit_utilization", "threshold_proximity"],
        "rapm": ["risk_adjusted_return", "capital_cost"],
        "climate_risk": ["scenario_coverage", "transition_risk_sensitivity"],
        "ai_model_validation": ["fairness_stability", "drift_monitoring"],
    }
