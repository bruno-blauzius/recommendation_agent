from pydantic import BaseModel, Field


class ProdutoRecomendado(BaseModel):
    produto: str = Field(description="Nome do produto, ex.: 'Seguro Auto'")
    ramo: str = Field(description="Ramo do seguro, ex.: 'auto'")
    seguradora: str = Field(description="Nome da seguradora")
    score_relevancia: float = Field(
        ge=0.0, le=1.0, description="Relevância de 0.0 a 1.0"
    )
    valor: str = Field(description="Valor médio do produto, ex.: 'R$ 150/mês'")
    logo_url: str = Field(
        description="URL do logo da seguradora, ex.: 'https://.../logo.png'"
    )
    justificativa: str = Field(
        description=(
            "Justificativa baseada nos dados de outros clientes, "
            "ex.: '65% dos clientes da mesma região/faixa contrataram este produto'"
        )
    )


class RecomendacaoOutput(BaseModel):
    cliente_descricao: str = Field(description="Resumo do perfil extraído do prompt")
    perfil_identificado: str = Field(
        description=(
            "Segmento inferido no formato 'faixa_etaria_genero_regiao', "
            "ex.: '26-35_masculino_sul'"
        )
    )
    recomendacoes: list[ProdutoRecomendado] = Field(
        max_length=3,
        description="Lista de até 3 recomendações ordenadas por relevância",
    )
