import pytest
from pydantic import ValidationError

from schemas.recommendation import ProdutoRecomendado, RecomendacaoOutput

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PRODUTO_VALIDO = {
    "produto": "Seguro Auto",
    "ramo": "auto",
    "seguradora": "Porto Seguro",
    "score_relevancia": 0.85,
    "valor": "R$ 150/mês",
    "justificativa": "65% dos clientes da região sul contrataram este produto",
}

_OUTPUT_VALIDO = {
    "cliente_descricao": "Homem, 34 anos, região sul, interesse em auto",
    "perfil_identificado": "26-35_masculino_sul",
    "recomendacoes": [_PRODUTO_VALIDO],
}


# ---------------------------------------------------------------------------
# ProdutoRecomendado — instanciação válida
# ---------------------------------------------------------------------------


def test_produto_recomendado_instancia_com_dados_validos():
    p = ProdutoRecomendado(**_PRODUTO_VALIDO)
    assert p.produto == "Seguro Auto"
    assert p.ramo == "auto"
    assert p.seguradora == "Porto Seguro"
    assert p.score_relevancia == 0.85
    assert p.valor == "R$ 150/mês"
    assert "65%" in p.justificativa


def test_produto_recomendado_valor_obrigatorio_ausente_levanta_erro():
    dados = {k: v for k, v in _PRODUTO_VALIDO.items() if k != "valor"}
    with pytest.raises(ValidationError, match="valor"):
        ProdutoRecomendado(**dados)


def test_produto_recomendado_valor_aceita_string_formatada():
    p = ProdutoRecomendado(**{**_PRODUTO_VALIDO, "valor": "R$ 299,90/mês"})
    assert p.valor == "R$ 299,90/mês"


def test_produto_recomendado_score_limite_inferior():
    p = ProdutoRecomendado(**{**_PRODUTO_VALIDO, "score_relevancia": 0.0})
    assert p.score_relevancia == 0.0


def test_produto_recomendado_score_limite_superior():
    p = ProdutoRecomendado(**{**_PRODUTO_VALIDO, "score_relevancia": 1.0})
    assert p.score_relevancia == 1.0


def test_produto_recomendado_score_abaixo_do_minimo_levanta_erro():
    with pytest.raises(ValidationError, match="greater than or equal to 0"):
        ProdutoRecomendado(**{**_PRODUTO_VALIDO, "score_relevancia": -0.1})


def test_produto_recomendado_score_acima_do_maximo_levanta_erro():
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        ProdutoRecomendado(**{**_PRODUTO_VALIDO, "score_relevancia": 1.1})


def test_produto_recomendado_campo_obrigatorio_ausente_levanta_erro():
    dados = {k: v for k, v in _PRODUTO_VALIDO.items() if k != "seguradora"}
    with pytest.raises(ValidationError, match="seguradora"):
        ProdutoRecomendado(**dados)


# ---------------------------------------------------------------------------
# RecomendacaoOutput — instanciação válida
# ---------------------------------------------------------------------------


def test_recomendacao_output_instancia_com_dados_validos():
    out = RecomendacaoOutput(**_OUTPUT_VALIDO)
    assert out.cliente_descricao == "Homem, 34 anos, região sul, interesse em auto"
    assert out.perfil_identificado == "26-35_masculino_sul"
    assert len(out.recomendacoes) == 1
    assert isinstance(out.recomendacoes[0], ProdutoRecomendado)


def test_recomendacao_output_aceita_lista_vazia_de_recomendacoes():
    out = RecomendacaoOutput(**{**_OUTPUT_VALIDO, "recomendacoes": []})
    assert out.recomendacoes == []


def test_recomendacao_output_aceita_ate_3_recomendacoes():
    out = RecomendacaoOutput(
        **{**_OUTPUT_VALIDO, "recomendacoes": [_PRODUTO_VALIDO] * 3}
    )
    assert len(out.recomendacoes) == 3


def test_recomendacao_output_mais_de_3_recomendacoes_levanta_erro():
    with pytest.raises(ValidationError, match="List should have at most 3 items"):
        RecomendacaoOutput(**{**_OUTPUT_VALIDO, "recomendacoes": [_PRODUTO_VALIDO] * 4})


def test_recomendacao_output_campo_obrigatorio_ausente_levanta_erro():
    dados = {k: v for k, v in _OUTPUT_VALIDO.items() if k != "perfil_identificado"}
    with pytest.raises(ValidationError, match="perfil_identificado"):
        RecomendacaoOutput(**dados)


# ---------------------------------------------------------------------------
# RecomendacaoOutput — serialização / desserialização JSON
# ---------------------------------------------------------------------------


def test_recomendacao_output_serializa_para_json():
    out = RecomendacaoOutput(**_OUTPUT_VALIDO)
    payload = out.model_dump_json()
    assert "Seguro Auto" in payload
    assert "26-35_masculino_sul" in payload


def test_recomendacao_output_deserializa_de_json():
    out = RecomendacaoOutput(**_OUTPUT_VALIDO)
    json_str = out.model_dump_json()
    restaurado = RecomendacaoOutput.model_validate_json(json_str)
    assert restaurado.perfil_identificado == out.perfil_identificado
    assert restaurado.recomendacoes[0].produto == "Seguro Auto"


def test_recomendacao_output_json_invalido_levanta_erro():
    with pytest.raises(Exception):
        RecomendacaoOutput.model_validate_json('{"invalido": true}')
