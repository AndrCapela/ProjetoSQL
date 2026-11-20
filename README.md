# SQL Arena — Treinamento Interativo de SQL

Plataforma web em **FastAPI + SQLite** para praticar consultas SQL (`SELECT` / `WITH`) em uma base acadêmica de exemplo com desafios nos níveis **Fácil**, **Médio** e **Difícil**, além de **Modo Livre** e **Explorador de Tabelas**.

## Estrutura do Banco de Dados (`data/escola.db`)

- `professores` (10 registros) — 1:N com `disciplinas`
- `cursos` (12 registros) — 1:N com `disciplinas`
- `disciplinas` (20 registros) — cada disciplina pertence a 1 professor e 1 curso
- `alunos` (50 registros)
- `alunos_disciplinas` (108 registros) — relação N:N entre `alunos` e `disciplinas`
- `notas` (159 registros) — avaliações ligadas às matrículas em `alunos_disciplinas`

## Como executar

1. Instalar dependências (se ainda não estiverem instaladas):
   ```bash
   pip install -r requirements.txt
   ```

2. (Opcional) Recriar/repopular a base SQLite do zero:
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
