# SQL Arena — Treinamento Interativo de SQL

Plataforma web em **FastAPI + SQLite + DuckDB (Friendly SQL)** para praticar consultas SQL (`SELECT`, `WITH`, `FROM`-first, `GROUP BY ALL`, `QUALIFY`, `PIVOT`, `ANTI JOIN`) em uma mesma base acadêmica espelhada nos dois motores, com 40 desafios nos níveis **Fácil**, **Médio** e **Difícil**, **Modo Livre**, **Explorador de Tabelas**, **DER visual** e **Tutor SQL**.

## Estrutura das Bases de Dados (`data/escola.db` e `data/escola.duckdb`)

Ambas as bases compartilham exatamente as mesmas 6 tabelas e os mesmos registros:

- `professores` (10 registros) — 1:N com `disciplinas`
- `cursos` (12 registros) — 1:N com `disciplinas`
- `disciplinas` (20 registros) — cada disciplina pertence a 1 professor e 1 curso
- `alunos` (50 registros)
- `alunos_disciplinas` (108 registros) — relação N:N entre `alunos` e `disciplinas`
- `notas` (159 registros) — avaliações ligadas às matrículas em `alunos_disciplinas`

No frontend, o usuário pode alternar livremente entre **SQLite** e **DuckDB (Friendly SQL)**. Cada tecnologia mantém progresso de exercícios resolvidos, rascunhos e histórico separados, e no modo DuckDB qualquer SQL válido (ANSI padrão ou Friendly SQL) que retorne o resultado esperado é aceito.

## Como executar

1. Instalar dependências (se ainda não estiverem instaladas):
   ```bash
   pip install -r requirements.txt
   ```

2. (Opcional) Recriar/repopular as bases SQLite e DuckDB do zero:
   ```bash
   python -m app.database
   ```

3. Iniciar o servidor FastAPI:
   ```bash
   uvicorn app.main:app --reload
   ```

4. Acessar no navegador: `http://127.0.0.1:8000`

## Como rodar os testes automatizados

```bash
python -m pytest -v
```

## Documentação Técnica

Consulte [docs/DOCUMENTACAO.md](docs/DOCUMENTACAO.md) para detalhes da arquitetura, classes/modelos, diagrama ER do banco de dados e histórico de melhorias.
