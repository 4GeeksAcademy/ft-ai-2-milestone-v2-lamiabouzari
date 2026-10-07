"""Department generators. Only the active department module is called."""

from __future__ import annotations

from collections.abc import Callable

from data.pipelines.rfp_response.generators import lastmile, reverse, warehouse
from data.pipelines.rfp_response.schemas import GenerationInput

Generator = Callable[[GenerationInput], str]

GENERATORS: dict[str, Generator] = {
    "warehouse": warehouse.generate,
    "lastmile": lastmile.generate,
    "reverse": reverse.generate,
}


def generate(brief: GenerationInput) -> str:
    """Run the generator for this department and no other."""
    generator = GENERATORS.get(brief.department_id)
    if generator is None:
        raise KeyError(brief.department_id)
    return generator(brief)
