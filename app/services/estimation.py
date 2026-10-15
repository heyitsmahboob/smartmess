import math
from typing import Dict, Any

def calculate_meal_requirement(
    confirmed_eating: int,
    confirmed_not_eating: int,
    no_response: int,
    buffer_percent: float = 10.0,
    mode: str = "strict",
    no_response_ratio: float = 0.40
) -> Dict[str, Any]:
    """
    Calculate estimated meal requirement based on responses, mode, and safety buffer.

    Modes:
      - 'strict': Only confirmed eaters + buffer.
      - 'standard': Confirmed eaters + (partial no_response * ratio) + buffer.
      - 'conservative': Confirmed eaters + all no_response + buffer.
    """
    total_residents = confirmed_eating + confirmed_not_eating + no_response
    responded = confirmed_eating + confirmed_not_eating
    response_rate = round((responded / total_residents * 100), 1) if total_residents > 0 else 0.0

    buffer_factor = 1.0 + (buffer_percent / 100.0)

    if mode == "conservative":
        mode_label = "Conservative Mode"
        mode_desc = "Assumes all unresponded residents might eat, plus safety buffer."
        unresponded_eaters = no_response
        base_estimate = confirmed_eating + unresponded_eaters
        raw_servings = base_estimate * buffer_factor
        recommended = math.ceil(raw_servings) if raw_servings > 0 else 0
        buffer_servings = recommended - base_estimate
        formula = f"({confirmed_eating} confirmed + {no_response} no response) + {buffer_percent:.1f}% buffer = {recommended} servings"

    elif mode == "standard":
        mode_label = "Standard Mode"
        mode_desc = f"Assumes {int(no_response_ratio * 100)}% of unresponded residents will eat, plus safety buffer."
        unresponded_eaters = round(no_response * no_response_ratio)
        base_estimate = confirmed_eating + unresponded_eaters
        raw_servings = base_estimate * buffer_factor
        recommended = math.ceil(raw_servings) if raw_servings > 0 else 0
        buffer_servings = recommended - base_estimate
        formula = f"({confirmed_eating} confirmed + {unresponded_eaters} est. unresponded) + {buffer_percent:.1f}% buffer = {recommended} servings"

    else:  # 'strict'
        mode = "strict"
        mode_label = "Strict Response Mode"
        mode_desc = "Cooks strictly for confirmed eaters plus safety buffer."
        unresponded_eaters = 0
        base_estimate = confirmed_eating
        raw_servings = base_estimate * buffer_factor
        recommended = math.ceil(raw_servings) if raw_servings > 0 else 0
        buffer_servings = recommended - base_estimate
        formula = f"{confirmed_eating} confirmed eaters + {buffer_percent:.1f}% safety buffer = {recommended} servings"

    return {
        "confirmed_eating": confirmed_eating,
        "confirmed_not_eating": confirmed_not_eating,
        "no_response": no_response,
        "total_residents": total_residents,
        "response_rate": response_rate,
        "buffer_percent": buffer_percent,
        "mode": mode,
        "mode_label": mode_label,
        "mode_desc": mode_desc,
        "unresponded_eaters": unresponded_eaters,
        "base_estimate": base_estimate,
        "buffer_servings": buffer_servings,
        "recommended_servings": recommended,
        "formula_display": formula
    }
