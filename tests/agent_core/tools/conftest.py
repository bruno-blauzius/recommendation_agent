"""
Configura mocks de módulo para os testes das tools antes de qualquer import.

O decorator `@function_tool` do SDK `agents` transforma funções async em objetos
`FunctionTool` que não expõem a função original. Para testar a lógica de negócio
diretamente, substituímos `function_tool` por uma função identidade aqui —
antes que `recommendation_tools` seja carregado pelo Python.
"""

import sys
from unittest.mock import MagicMock

if "agents" not in sys.modules:
    agents_mock = MagicMock()
    agents_mock.function_tool = lambda f: f
    sys.modules["agents"] = agents_mock
else:
    # Garante que function_tool seja identidade mesmo se agents já foi importado
    sys.modules["agents"].function_tool = lambda f: f

# Garante que o módulo das tools seja recarregado sem cache da sessão anterior
for mod in list(sys.modules):
    if "recommendation_tools" in mod:
        del sys.modules[mod]
