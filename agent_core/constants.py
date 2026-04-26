# Mapeamento de faixa etária para faixas adjacentes (tolerância ±1).
# Permite buscar perfis de clientes próximos em idade, não apenas exatamente iguais.
_FAIXAS_ADJACENTES: dict[str, list[str]] = {
    "18-25": ["18-25", "26-35"],
    "26-35": ["18-25", "26-35", "36-45"],
    "36-45": ["26-35", "36-45", "46-55"],
    "46-55": ["36-45", "46-55", "56-65"],
    "56-65": ["46-55", "56-65", "66+"],
    "66+": ["56-65", "66+"],
}
