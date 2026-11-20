"""Testes da lógica de comparação de resultados."""

from app.comparator import compare_results
from app.sql_executor import SQLExecutionResult


def _res(columns, rows):
    return SQLExecutionResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        execution_ms=1.0,
    )


def test_matches_different_row_order_and_aliases_when_order_does_not_matter() -> None:
    expected = _res(["nome", "media"], [["Ana", 8.33333], ["Bruno", 9.0]])
    user = _res(["aluno_nome", "nota_media"], [["Bruno", 9], ["Ana", 8.33]])

    cmp = compare_results(user, expected, order_matters=False)
    assert cmp.is_correct is True


def test_detects_wrong_order_when_order_matters() -> None:
    expected = _res(["nome", "salario"], [["Ricardo", 11200], ["Mariana", 10400]])
    user = _res(["nome", "salario"], [["Mariana", 10400], ["Ricardo", 11200]])

    cmp = compare_results(user, expected, order_matters=True)
    assert cmp.is_correct is False
    assert "ordenação" in cmp.feedback.lower()


def test_detects_column_and_row_mismatches() -> None:
    expected = _res(["nome", "idade"], [["Ana", 31], ["Bruno", 34]])
    wrong_cols = _res(["nome"], [["Ana"], ["Bruno"]])
    wrong_rows = _res(["nome", "idade"], [["Ana", 31]])
    wrong_vals = _res(["nome", "idade"], [["Ana", 31], ["Carlos", 40]])

    assert compare_results(wrong_cols, expected).is_correct is False
    assert "colunas" in compare_results(wrong_cols, expected).feedback.lower()

    assert compare_results(wrong_rows, expected).is_correct is False
    assert "1 linha(s)" in compare_results(wrong_rows, expected).feedback

    assert compare_results(wrong_vals, expected).is_correct is False


def test_row_diff_statuses_for_extra_missing_and_order() -> None:
    expected = _res(["nome", "idade"], [["Ana", 31], ["Bruno", 34], ["Clara", 39]])
    user = _res(["nome", "idade"], [["Ana", 31], ["Carlos", 40]])

    diff = compare_results(user, expected, order_matters=False)
    assert diff.is_correct is False
    assert diff.user_row_status == ["match", "extra"]
    assert diff.expected_row_status == ["match", "missing", "missing"]

    ordered_user = _res(["nome", "idade"], [["Ana", 31], ["Clara", 39], ["Bruno", 34]])
    order_diff = compare_results(ordered_user, expected, order_matters=True)
    assert order_diff.is_correct is False
    assert order_diff.user_row_status == ["match", "order", "order"]
    assert order_diff.expected_row_status == ["match", "order", "order"]
