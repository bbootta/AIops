class GovernanceHarness:
    code_version = "0.1.0"
    prompt_version = "prototype-prompt-v1"
    data_contract_version = "risk-run-request-v1"
    template_version = "report-template-v1"

    def production_change_allowed(self, approved: bool) -> bool:
        return approved
