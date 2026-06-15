class CalculationLogicRegistry:
    def __init__(self) -> None:
        self._approved = {
            "credit_model_engine": "0.1.0",
            "rwa_engine": "0.1.0",
            "bis_ratio_engine": "0.1.0",
            "delinquency_default_recovery_engine": "0.1.0",
            "limit_engine": "0.1.0",
            "rapm_engine": "0.1.0",
            "climate_risk_engine": "0.1.0",
            "ai_model_validation_engine": "0.1.0",
        }

    def is_approved(self, engine_id: str, version: str) -> bool:
        return self._approved.get(engine_id) == version
