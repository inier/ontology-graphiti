from fastapi import APIRouter, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import List

from .schemas import WhatIfScenario, WhatIfResult, WhatIfComparison
from .sandbox import get_simulation_sandbox

router = APIRouter(prefix="/api/simulation/whatif", tags=["simulation-sandbox"])


@router.post("/simulate", response_model=WhatIfResult)
async def simulate_whatif(scenario: WhatIfScenario,
    user=Depends(get_current_user)):
    sandbox = get_simulation_sandbox()
    return await sandbox.simulate(scenario)


@router.post("/compare", response_model=WhatIfComparison)
async def compare_scenarios(scenarios: List[WhatIfScenario],
    user=Depends(get_current_user)):
    sandbox = get_simulation_sandbox()
    return await sandbox.compare(scenarios)
