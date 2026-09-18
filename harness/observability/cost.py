from dataclasses import dataclass

@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    output_per_million: float

class CostCalculator:
    def __init__(self, prices: dict[str, ModelPrice]) -> None:
        self.prices = prices

    def calculate(self, *, model: str, input_tokens: int, output_tokens: int) -> float | None:
        price = self.prices.get(model)
        if price is None:
            return None
        return (
            input_tokens / 1_000_000 * price.input_per_million
            + output_tokens / 1_000_000 * price.output_per_million
        )


