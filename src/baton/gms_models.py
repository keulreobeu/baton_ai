"""Approved GMS IDs and credit rates verified in the provider guide 2026-10-14."""
from decimal import Decimal, ROUND_CEILING

MODELS = {
    "gpt-6.1-sol": {"difficulty": "complex", "input_rate": "0.02", "output_rate": "0.1"},
    "gpt-6-luna": {"difficulty": "simple", "input_rate": "0.001", "output_rate": "0.005"},
}


def select_model(difficulty=None, model=None):
    if difficulty is not None and difficulty not in ("simple", "complex"):
        raise ValueError("작업 난이도는 simple 또는 complex여야 합니다.")
    if model is not None and (not isinstance(model, str) or model not in MODELS):
        raise ValueError("GMS 모델은 gpt-6.1-sol 또는 gpt-6-luna만 허용합니다.")
    if model is None:
        model = "gpt-6-luna" if difficulty == "simple" else "gpt-6.1-sol"
    if difficulty is not None and MODELS[model]["difficulty"] != difficulty:
        raise ValueError("작업 난이도와 선택 모델이 일치하지 않습니다.")
    return {"model": model, **MODELS[model]}


def cost_cents(model, inputs, outputs):
    rates = select_model(model=model)
    value = Decimal(inputs) * Decimal(rates["input_rate"]) + Decimal(outputs) * Decimal(rates["output_rate"])
    return int((value * 100).to_integral_value(rounding=ROUND_CEILING))


def reservation_cents(model, inputs, outputs):
    """Allow the observed provider's rounding to whole credits at billing."""
    cents = cost_cents(model, inputs, outputs)
    return ((cents + 99) // 100) * 100
