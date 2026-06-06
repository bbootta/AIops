class RegulationPolicyRegistry:
    def __init__(self) -> None:
        self._mappings = {"basel-fss-sample-map-v1": {"status": "sample_configurable_mapping"}}

    def exists(self, mapping_id: str | None) -> bool:
        return bool(mapping_id and mapping_id in self._mappings)

    def candidate_validation_controls(self, change_summary: str) -> list[dict[str, str]]:
        return [
            {"candidate_type": "new_metric", "summary": change_summary},
            {"candidate_type": "new_rule_or_eligibility_check", "summary": change_summary},
            {"candidate_type": "new_data_attribute_or_lineage_check", "summary": change_summary},
            {"candidate_type": "new_reconciliation_check", "summary": change_summary},
            {"candidate_type": "new_disclosure_or_reporting_check", "summary": change_summary},
        ]
