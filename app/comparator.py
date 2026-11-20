"""Comparação semântica entre o resultado do usuário e o gabarito esperado."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from app.sql_executor import SQLExecutionResult

UserRowStatus = Literal["match", "extra", "order"]
ExpectedRowStatus = Literal["match", "missing", "order"]


@dataclass(frozen=True)
class ComparisonResult:
    """Resultado da avaliação da consulta do usuário contra o gabarito."""

    is_correct: bool
    feedback: str
    user_row_status: list[UserRowStatus] | None = None
    expected_row_status: list[ExpectedRowStatus] | None = None


def _normalize_cell(value: Any) -> Any:
    """Normaliza valores numéricos para tolerar diferenças de precisão e int/float."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 2)
    return value


def _normalize_rows(rows: list[list[Any]]) -> list[tuple[Any, ...]]:
    """Converte linhas em tuplas normalizadas e comparáveis."""
    return [tuple(_normalize_cell(cell) for cell in row) for row in rows]


def _compute_multiset_diff(
    norm_user: list[tuple[Any, ...]],
    norm_expected: list[tuple[Any, ...]],
) -> tuple[list[UserRowStatus], list[ExpectedRowStatus]]:
    """Marca linha a linha quais registros bateram, sobraram no usuário ou faltaram no gabarito."""
    rem_expected = Counter(norm_expected)
    user_status: list[UserRowStatus] = []
    for row in norm_user:
        if rem_expected[row] > 0:
            rem_expected[row] -= 1
            user_status.append("match")
        else:
            user_status.append("extra")

    rem_user = Counter(norm_user)
    expected_status: list[ExpectedRowStatus] = []
    for row in norm_expected:
        if rem_user[row] > 0:
            rem_user[row] -= 1
            expected_status.append("match")
        else:
            expected_status.append("missing")

    return user_status, expected_status


def compare_results(
    user_result: SQLExecutionResult,
    expected_result: SQLExecutionResult,
    order_matters: bool = False,
) -> ComparisonResult:
    """Compara os dados retornados pelo usuário com os do gabarito, independente do SQL escrito."""
    expected_col_count = len(expected_result.columns)
    user_col_count = len(user_result.columns)

    if user_col_count != expected_col_count:
        return ComparisonResult(
            is_correct=False,
            feedback=(
                f"Quantidade de colunas diferente: sua query retornou {user_col_count}, "
                f"mas o esperado são {expected_col_count}."
            ),
        )

    norm_user = _normalize_rows(user_result.rows)
    norm_expected = _normalize_rows(expected_result.rows)

    if order_matters:
        if norm_user == norm_expected:
            return ComparisonResult(
                is_correct=True,
                feedback="Parabéns! Sua query retornou exatamente os resultados e a ordenação esperados.",
                user_row_status=["match"] * len(norm_user),
                expected_row_status=["match"] * len(norm_expected),
            )
        if Counter(norm_user) == Counter(norm_expected):
            user_status: list[UserRowStatus] = [
                "match" if norm_user[i] == norm_expected[i] else "order"
                for i in range(len(norm_user))
            ]
            expected_status: list[ExpectedRowStatus] = [
                "match" if norm_user[i] == norm_expected[i] else "order"
                for i in range(len(norm_expected))
            ]
            return ComparisonResult(
                is_correct=False,
                feedback="Os registros estão corretos, mas a ordenação está diferente do pedido no enunciado.",
                user_row_status=user_status,
                expected_row_status=expected_status,
            )
    else:
        if Counter(norm_user) == Counter(norm_expected):
            return ComparisonResult(
                is_correct=True,
                feedback="Parabéns! Sua query retornou exatamente os resultados esperados.",
                user_row_status=["match"] * len(norm_user),
                expected_row_status=["match"] * len(norm_expected),
            )

    user_status, expected_status = _compute_multiset_diff(norm_user, norm_expected)

    if len(norm_user) != len(norm_expected):
        return ComparisonResult(
            is_correct=False,
            feedback=(
                f"Resultado diferente: sua query retornou {len(norm_user)} linha(s), "
                f"mas o esperado são {len(norm_expected)} linha(s)."
            ),
            user_row_status=user_status,
            expected_row_status=expected_status,
        )

    return ComparisonResult(
        is_correct=False,
        feedback=(
            "Mesma quantidade de linhas e colunas, mas os valores ou a ordem das colunas "
            "estão diferentes do esperado."
        ),
        user_row_status=user_status,
        expected_row_status=expected_status,
    )
