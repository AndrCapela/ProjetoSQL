"""Catálogo fixo de desafios SQL (Fácil, Médio e Difícil)."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas import DifficultyLevel


@dataclass(frozen=True)
class Challenge:
    """Definição de um desafio SQL com enunciado e gabarito."""

    id: str
    nivel: DifficultyLevel
    titulo: str
    enunciado: str
    dica: str
    solucao_sql: str
    ordem_importa: bool
    topicos: tuple[str, ...]


CHALLENGES: tuple[Challenge, ...] = (
    # ==================== FÁCIL ====================
    Challenge(
        id="facil-1",
        nivel="facil",
        titulo="Alunos acima de 30 anos",
        enunciado=(
            "Liste o nome, a idade e a cidade de todos os alunos com idade maior que 30 anos."
        ),
        dica="Use SELECT nome, idade, cidade FROM alunos seguido de WHERE idade > 30.",
        solucao_sql=(
            "SELECT nome, idade, cidade\n"
            "FROM alunos\n"
            "WHERE idade > 30;"
        ),
        ordem_importa=False,
        topicos=("SELECT", "WHERE"),
    ),
    Challenge(
        id="facil-2",
        nivel="facil",
        titulo="Disciplinas de 80 horas",
        enunciado=(
            "Mostre o código, o nome e a carga horária das disciplinas que possuem "
            "carga horária igual a 80 horas."
        ),
        dica="Consulte a tabela disciplinas filtrando pela coluna carga_horaria.",
        solucao_sql=(
            "SELECT codigo, nome, carga_horaria\n"
            "FROM disciplinas\n"
            "WHERE carga_horaria = 80;"
        ),
        ordem_importa=False,
        topicos=("SELECT", "WHERE"),
    ),
    Challenge(
        id="facil-3",
        nivel="facil",
        titulo="Ranking salarial dos professores",
        enunciado=(
            "Retorne o nome, a especialidade e o salário de todos os professores, "
            "ordenados do maior salário para o menor."
        ),
        dica="Use ORDER BY salario DESC na tabela professores.",
        solucao_sql=(
            "SELECT nome, especialidade, salario\n"
            "FROM professores\n"
            "ORDER BY salario DESC;"
        ),
        ordem_importa=True,
        topicos=("SELECT", "ORDER BY"),
    ),
    Challenge(
        id="facil-4",
        nivel="facil",
        titulo="Cidades distintas dos alunos",
        enunciado=(
            "Liste todas as cidades distintas onde moram os alunos, em ordem alfabética."
        ),
        dica="Combine SELECT DISTINCT cidade com ORDER BY cidade ASC.",
        solucao_sql=(
            "SELECT DISTINCT cidade\n"
            "FROM alunos\n"
            "ORDER BY cidade ASC;"
        ),
        ordem_importa=True,
        topicos=("DISTINCT", "ORDER BY"),
    ),
    Challenge(
        id="facil-5",
        nivel="facil",
        titulo="Jovens alunos de São Paulo",
        enunciado=(
            "Retorne o nome, a idade e o e-mail dos alunos que moram em 'São Paulo' "
            "e têm menos de 25 anos."
        ),
        dica="Use duas condições combinadas com AND no WHERE.",
        solucao_sql=(
            "SELECT nome, idade, email\n"
            "FROM alunos\n"
            "WHERE cidade = 'São Paulo' AND idade < 25;"
        ),
        ordem_importa=False,
        topicos=("WHERE", "AND"),
    ),
    Challenge(
        id="facil-6",
        nivel="facil",
        titulo="Disciplinas sobre Dados",
        enunciado=(
            "Liste o código e o nome das disciplinas cujo nome contém a palavra 'Dados'."
        ),
        dica="Use o operador LIKE com coringas: WHERE nome LIKE '%Dados%'.",
        solucao_sql=(
            "SELECT codigo, nome\n"
            "FROM disciplinas\n"
            "WHERE nome LIKE '%Dados%';"
        ),
        ordem_importa=False,
        topicos=("WHERE", "LIKE"),
    ),
    Challenge(
        id="facil-7",
        nivel="facil",
        titulo="Alunos entre 25 e 30 anos",
        enunciado=(
            "Retorne o nome, a idade e a cidade dos alunos com idade entre 25 e 30 anos (inclusive), "
            "ordenados da menor idade para a maior e, em caso de empate, pelo nome em ordem alfabética (crescente)."
        ),
        dica="Use WHERE idade BETWEEN 25 AND 30 combinado com ORDER BY idade ASC, nome ASC.",
        solucao_sql=(
            "SELECT nome, idade, cidade\n"
            "FROM alunos\n"
            "WHERE idade BETWEEN 25 AND 30\n"
            "ORDER BY idade ASC, nome ASC;"
        ),
        ordem_importa=True,
        topicos=("WHERE", "BETWEEN", "ORDER BY"),
    ),
    Challenge(
        id="facil-8",
        nivel="facil",
        titulo="Alunos da região Sul",
        enunciado=(
            "Liste o nome, a cidade e o e-mail dos alunos que moram em 'Curitiba', "
            "'Porto Alegre' ou 'Florianópolis'."
        ),
        dica="Use o operador IN: WHERE cidade IN ('Curitiba', 'Porto Alegre', 'Florianópolis').",
        solucao_sql=(
            "SELECT nome, cidade, email\n"
            "FROM alunos\n"
            "WHERE cidade IN ('Curitiba', 'Porto Alegre', 'Florianópolis');"
        ),
        ordem_importa=False,
        topicos=("WHERE", "IN"),
    ),
    Challenge(
        id="facil-9",
        nivel="facil",
        titulo="Inscrições trancadas",
        enunciado=(
            "Mostre o id, o aluno_id, a disciplina_id e a data_inscricao de todas as "
            "matrículas na tabela alunos_disciplinas com status igual a 'trancada'."
        ),
        dica="Consulte alunos_disciplinas com WHERE status = 'trancada'.",
        solucao_sql=(
            "SELECT id, aluno_id, disciplina_id, data_inscricao\n"
            "FROM alunos_disciplinas\n"
            "WHERE status = 'trancada';"
        ),
        ordem_importa=False,
        topicos=("SELECT", "WHERE"),
    ),
    Challenge(
        id="facil-10",
        nivel="facil",
        titulo="Top 5 cursos com maior carga horária",
        enunciado=(
            "Liste o nome, a categoria e a carga horária dos 5 cursos com maior carga horária, "
            "ordenados do maior para o menor e pelo nome em caso de empate."
        ),
        dica="Ordene por carga_horaria DESC, nome ASC e limite com LIMIT 5.",
        solucao_sql=(
            "SELECT nome, categoria, carga_horaria\n"
            "FROM cursos\n"
            "ORDER BY carga_horaria DESC, nome ASC\n"
            "LIMIT 5;"
        ),
        ordem_importa=True,
        topicos=("ORDER BY", "LIMIT"),
    ),
    # ==================== MÉDIO ====================
    Challenge(
        id="medio-1",
        nivel="medio",
        titulo="Disciplinas e seus professores",
        enunciado=(
            "Mostre o nome de cada disciplina junto com o nome do professor responsável por ela."
        ),
        dica="Faça um INNER JOIN entre disciplinas e professores usando professor_id.",
        solucao_sql=(
            "SELECT d.nome AS disciplina, p.nome AS professor\n"
            "FROM disciplinas d\n"
            "INNER JOIN professores p ON p.id = d.professor_id;"
        ),
        ordem_importa=False,
        topicos=("INNER JOIN",),
    ),
    Challenge(
        id="medio-2",
        nivel="medio",
        titulo="Quantidade de disciplinas por professor",
        enunciado=(
            "Liste o nome de cada professor e a quantidade de disciplinas que ele leciona, "
            "ordenados da maior quantidade para a menor e, em caso de empate, pelo nome do professor em ordem alfabética."
        ),
        dica="Agrupe por professor com GROUP BY e conte as disciplinas com COUNT(d.id).",
        solucao_sql=(
            "SELECT p.nome, COUNT(d.id) AS total_disciplinas\n"
            "FROM professores p\n"
            "LEFT JOIN disciplinas d ON d.professor_id = p.id\n"
            "GROUP BY p.id, p.nome\n"
            "ORDER BY total_disciplinas DESC, p.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("JOIN", "GROUP BY", "COUNT", "ORDER BY"),
    ),
    Challenge(
        id="medio-3",
        nivel="medio",
        titulo="Média de notas por disciplina",
        enunciado=(
            "Calcule a média das notas lançadas para cada disciplina. "
            "Retorne o nome da disciplina e a média arredondada para 2 casas decimais, "
            "apenas para disciplinas que já possuem avaliações."
        ),
        dica="Conecte disciplinas -> alunos_disciplinas -> notas, use GROUP BY e ROUND(AVG(n.nota), 2).",
        solucao_sql=(
            "SELECT d.nome AS disciplina, ROUND(AVG(n.nota), 2) AS media_nota\n"
            "FROM disciplinas d\n"
            "INNER JOIN alunos_disciplinas ad ON ad.disciplina_id = d.id\n"
            "INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "GROUP BY d.id, d.nome;"
        ),
        ordem_importa=False,
        topicos=("JOIN", "GROUP BY", "AVG", "ROUND"),
    ),
    Challenge(
        id="medio-4",
        nivel="medio",
        titulo="Alunos de Modelagem de Dados",
        enunciado=(
            "Liste o nome do aluno e o status da inscrição para todos os alunos matriculados "
            "na disciplina 'Modelagem de Dados'."
        ),
        dica="Relacione alunos, alunos_disciplinas e disciplinas filtrando pelo nome da disciplina.",
        solucao_sql=(
            "SELECT a.nome, ad.status\n"
            "FROM alunos a\n"
            "INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n"
            "INNER JOIN disciplinas d ON d.id = ad.disciplina_id\n"
            "WHERE d.nome = 'Modelagem de Dados';"
        ),
        ordem_importa=False,
        topicos=("JOIN", "N:N", "WHERE"),
    ),
    Challenge(
        id="medio-5",
        nivel="medio",
        titulo="Professores com múltiplas disciplinas",
        enunciado=(
            "Retorne o nome dos professores que lecionam 2 ou mais disciplinas, "
            "junto com a respectiva quantidade de disciplinas."
        ),
        dica="Use GROUP BY por professor e filtre os grupos com HAVING COUNT(d.id) >= 2.",
        solucao_sql=(
            "SELECT p.nome, COUNT(d.id) AS total_disciplinas\n"
            "FROM professores p\n"
            "INNER JOIN disciplinas d ON d.professor_id = p.id\n"
            "GROUP BY p.id, p.nome\n"
            "HAVING COUNT(d.id) >= 2;"
        ),
        ordem_importa=False,
        topicos=("JOIN", "GROUP BY", "HAVING"),
    ),
    Challenge(
        id="medio-6",
        nivel="medio",
        titulo="Grade de disciplinas por curso",
        enunciado=(
            "Liste o nome do curso, a categoria do curso e o nome da disciplina, "
            "ordenados alfabeticamente pelo nome do curso e depois pelo nome da disciplina."
        ),
        dica="Junte cursos e disciplinas por curso_id e ordene por c.nome, d.nome.",
        solucao_sql=(
            "SELECT c.nome AS curso, c.categoria, d.nome AS disciplina\n"
            "FROM cursos c\n"
            "INNER JOIN disciplinas d ON d.curso_id = c.id\n"
            "ORDER BY c.nome ASC, d.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("JOIN", "ORDER BY"),
    ),
    Challenge(
        id="medio-7",
        nivel="medio",
        titulo="Quantidade de alunos por cidade",
        enunciado=(
            "Mostre cada cidade e a quantidade de alunos que moram nela, "
            "ordenados da maior quantidade para a menor e pelo nome da cidade em caso de empate."
        ),
        dica="Use GROUP BY cidade com COUNT(*) e ORDER BY total DESC, cidade ASC.",
        solucao_sql=(
            "SELECT cidade, COUNT(*) AS total_alunos\n"
            "FROM alunos\n"
            "GROUP BY cidade\n"
            "ORDER BY total_alunos DESC, cidade ASC;"
        ),
        ordem_importa=True,
        topicos=("GROUP BY", "COUNT", "ORDER BY"),
    ),
    Challenge(
        id="medio-8",
        nivel="medio",
        titulo="Estatísticas por tipo de avaliação",
        enunciado=(
            "Para cada tipo de avaliação da tabela notas, retorne o nome da avaliação, "
            "a menor nota, a maior nota, a média arredondada para 2 casas e a quantidade de notas."
        ),
        dica="Agrupe por avaliacao e use MIN(nota), MAX(nota), ROUND(AVG(nota), 2) e COUNT(*).",
        solucao_sql=(
            "SELECT\n"
            "    avaliacao,\n"
            "    MIN(nota) AS menor_nota,\n"
            "    MAX(nota) AS maior_nota,\n"
            "    ROUND(AVG(nota), 2) AS media_nota,\n"
            "    COUNT(*) AS total_notas\n"
            "FROM notas\n"
            "GROUP BY avaliacao;"
        ),
        ordem_importa=False,
        topicos=("GROUP BY", "MIN", "MAX", "AVG"),
    ),
    Challenge(
        id="medio-9",
        nivel="medio",
        titulo="Cursos com mais de uma disciplina",
        enunciado=(
            "Retorne o nome dos cursos que possuem mais de 1 disciplina cadastrada, "
            "junto com a quantidade de disciplinas de cada um."
        ),
        dica="Faça JOIN entre cursos e disciplinas, agrupe por curso e filtre com HAVING COUNT(d.id) > 1.",
        solucao_sql=(
            "SELECT c.nome AS curso, COUNT(d.id) AS total_disciplinas\n"
            "FROM cursos c\n"
            "INNER JOIN disciplinas d ON d.curso_id = c.id\n"
            "GROUP BY c.id, c.nome\n"
            "HAVING COUNT(d.id) > 1;"
        ),
        ordem_importa=False,
        topicos=("JOIN", "GROUP BY", "HAVING"),
    ),
    Challenge(
        id="medio-10",
        nivel="medio",
        titulo="Carga horária total por professor",
        enunciado=(
            "Calcule a soma da carga horária de todas as disciplinas ministradas por cada professor. "
            "Retorne o nome do professor e a carga horária total, ordenados da maior carga para a menor "
            "e pelo nome do professor em caso de empate."
        ),
        dica="Use SUM(d.carga_horaria) com JOIN entre professores e disciplinas.",
        solucao_sql=(
            "SELECT p.nome AS professor, SUM(d.carga_horaria) AS carga_total\n"
            "FROM professores p\n"
            "INNER JOIN disciplinas d ON d.professor_id = p.id\n"
            "GROUP BY p.id, p.nome\n"
            "ORDER BY carga_total DESC, p.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("JOIN", "SUM", "GROUP BY", "ORDER BY"),
    ),
    # ==================== MÉDIO (EXTRAS) ====================
    Challenge(
        id="medio-11",
        nivel="medio",
        titulo="Cursos e disciplinas por categoria",
        enunciado=(
            "Para cada categoria de curso, retorne o nome da categoria, a quantidade de cursos distintos "
            "e a quantidade total de disciplinas cadastradas naquela categoria. Ordene do maior número "
            "de disciplinas para o menor e, em caso de empate, pela categoria em ordem alfabética."
        ),
        dica="Use LEFT JOIN entre cursos e disciplinas, COUNT(DISTINCT c.id) e COUNT(d.id).",
        solucao_sql=(
            "SELECT\n"
            "    c.categoria,\n"
            "    COUNT(DISTINCT c.id) AS total_cursos,\n"
            "    COUNT(d.id) AS total_disciplinas\n"
            "FROM cursos c\n"
            "LEFT JOIN disciplinas d ON d.curso_id = c.id\n"
            "GROUP BY c.categoria\n"
            "ORDER BY total_disciplinas DESC, c.categoria ASC;"
        ),
        ordem_importa=True,
        topicos=("LEFT JOIN", "COUNT(DISTINCT)", "GROUP BY", "ORDER BY"),
    ),
    Challenge(
        id="medio-12",
        nivel="medio",
        titulo="Cursos sem disciplinas cadastradas",
        enunciado=(
            "Encontre o id, o nome e a categoria dos cursos que ainda não possuem nenhuma "
            "disciplina vinculada na tabela disciplinas."
        ),
        dica="Faça um LEFT JOIN de cursos para disciplinas e filtre WHERE d.id IS NULL.",
        solucao_sql=(
            "SELECT c.id, c.nome, c.categoria\n"
            "FROM cursos c\n"
            "LEFT JOIN disciplinas d ON d.curso_id = c.id\n"
            "WHERE d.id IS NULL;"
        ),
        ordem_importa=False,
        topicos=("LEFT JOIN", "IS NULL"),
    ),
    Challenge(
        id="medio-13",
        nivel="medio",
        titulo="Distribuição de matrículas por status",
        enunciado=(
            "Mostre cada status existente na tabela alunos_disciplinas e a quantidade total de matrículas "
            "em cada um, ordenados da maior quantidade para a menor e pelo status em ordem alfabética."
        ),
        dica="Agrupe por status com GROUP BY status e conte com COUNT(*).",
        solucao_sql=(
            "SELECT status, COUNT(*) AS total_matriculas\n"
            "FROM alunos_disciplinas\n"
            "GROUP BY status\n"
            "ORDER BY total_matriculas DESC, status ASC;"
        ),
        ordem_importa=True,
        topicos=("GROUP BY", "COUNT", "ORDER BY"),
    ),
    Challenge(
        id="medio-14",
        nivel="medio",
        titulo="Professores contratados antes de 2020",
        enunciado=(
            "Liste o nome, a especialidade, a data_contratacao e o salário dos professores contratados "
            "antes de 1º de janeiro de 2020, ordenados do contrato mais antigo para o mais recente."
        ),
        dica="Como as datas estão em formato ISO (YYYY-MM-DD), use WHERE data_contratacao < '2020-01-01'.",
        solucao_sql=(
            "SELECT nome, especialidade, data_contratacao, salario\n"
            "FROM professores\n"
            "WHERE data_contratacao < '2020-01-01'\n"
            "ORDER BY data_contratacao ASC;"
        ),
        ordem_importa=True,
        topicos=("WHERE", "Datas SQLite", "ORDER BY"),
    ),
    Challenge(
        id="medio-15",
        nivel="medio",
        titulo="Avaliações em disciplinas concluídas",
        enunciado=(
            "Considerando apenas matrículas com status 'concluida', retorne o nome do aluno, "
            "a quantidade de avaliações lançadas e a média das notas (arredondada para 2 casas decimais), "
            "somente para os alunos que possuem 4 ou mais avaliações em disciplinas concluídas. "
            "Ordene da maior média para a menor e pelo nome do aluno."
        ),
        dica="Filtre WHERE ad.status = 'concluida' antes de agrupar e use HAVING COUNT(n.id) >= 4.",
        solucao_sql=(
            "SELECT\n"
            "    a.nome,\n"
            "    COUNT(n.id) AS total_avaliacoes,\n"
            "    ROUND(AVG(n.nota), 2) AS media_concluidas\n"
            "FROM alunos a\n"
            "INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n"
            "INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "WHERE ad.status = 'concluida'\n"
            "GROUP BY a.id, a.nome\n"
            "HAVING COUNT(n.id) >= 4\n"
            "ORDER BY media_concluidas DESC, a.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("JOIN", "WHERE", "GROUP BY", "HAVING"),
    ),
    # ==================== DIFÍCIL ====================
    Challenge(
        id="dificil-1",
        nivel="dificil",
        titulo="Alunos sem nenhuma disciplina",
        enunciado=(
            "Encontre o id, o nome e o e-mail dos alunos que ainda não estão inscritos "
            "em nenhuma disciplina."
        ),
        dica="Use LEFT JOIN com alunos_disciplinas filtrando WHERE ad.id IS NULL (ou NOT EXISTS).",
        solucao_sql=(
            "SELECT a.id, a.nome, a.email\n"
            "FROM alunos a\n"
            "LEFT JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n"
            "WHERE ad.id IS NULL;"
        ),
        ordem_importa=False,
        topicos=("LEFT JOIN", "IS NULL", "NOT EXISTS"),
    ),
    Challenge(
        id="dificil-2",
        nivel="dificil",
        titulo="Alunos acima da média geral da escola",
        enunciado=(
            "Liste o nome e a média geral (arredondada para 2 casas) dos alunos cuja média "
            "de notas é estritamente maior que a média global de todas as notas da tabela notas. "
            "Ordene da maior média para a menor e pelo nome do aluno em caso de empate."
        ),
        dica="Use HAVING AVG(n.nota) > (SELECT AVG(nota) FROM notas) ou uma CTE.",
        solucao_sql=(
            "SELECT a.nome, ROUND(AVG(n.nota), 2) AS media_aluno\n"
            "FROM alunos a\n"
            "INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n"
            "INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "GROUP BY a.id, a.nome\n"
            "HAVING AVG(n.nota) > (SELECT AVG(nota) FROM notas)\n"
            "ORDER BY media_aluno DESC, a.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("Subquery", "GROUP BY", "HAVING", "AVG"),
    ),
    Challenge(
        id="dificil-3",
        nivel="dificil",
        titulo="Inscrições ativas ou concluídas sem notas",
        enunciado=(
            "Liste o nome do aluno, o nome da disciplina e o status da matrícula para todas as "
            "inscrições (alunos_disciplinas) cujo status não é 'trancada' e que ainda não possuem "
            "nenhuma nota lançada."
        ),
        dica="Faça LEFT JOIN em notas e verifique n.id IS NULL, além de filtrar status != 'trancada'.",
        solucao_sql=(
            "SELECT a.nome AS aluno, d.nome AS disciplina, ad.status\n"
            "FROM alunos_disciplinas ad\n"
            "INNER JOIN alunos a ON a.id = ad.aluno_id\n"
            "INNER JOIN disciplinas d ON d.id = ad.disciplina_id\n"
            "LEFT JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "WHERE ad.status != 'trancada' AND n.id IS NULL;"
        ),
        ordem_importa=False,
        topicos=("LEFT JOIN", "IS NULL", "Múltiplos JOINs"),
    ),
    Challenge(
        id="dificil-4",
        nivel="dificil",
        titulo="Classificação de desempenho por matrícula",
        enunciado=(
            "Para cada matrícula que possui notas lançadas, retorne o nome do aluno, o nome da disciplina, "
            "a média das notas (2 casas decimais) e um conceito calculado com CASE: "
            "'Excelente' se média >= 9.0, 'Bom' se >= 7.5 e < 9.0, ou 'Regular' se < 7.5. "
            "Ordene pelo nome do aluno e depois pelo nome da disciplina."
        ),
        dica="Calcule a média em uma CTE ou subquery e aplique CASE WHEN na consulta externa (ou direto no SELECT).",
        solucao_sql=(
            "WITH medias AS (\n"
            "    SELECT\n"
            "        a.nome AS aluno,\n"
            "        d.nome AS disciplina,\n"
            "        ROUND(AVG(n.nota), 2) AS media\n"
            "    FROM alunos_disciplinas ad\n"
            "    INNER JOIN alunos a ON a.id = ad.aluno_id\n"
            "    INNER JOIN disciplinas d ON d.id = ad.disciplina_id\n"
            "    INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "    GROUP BY ad.id, a.nome, d.nome\n"
            ")\n"
            "SELECT\n"
            "    aluno,\n"
            "    disciplina,\n"
            "    media,\n"
            "    CASE\n"
            "        WHEN media >= 9.0 THEN 'Excelente'\n"
            "        WHEN media >= 7.5 THEN 'Bom'\n"
            "        ELSE 'Regular'\n"
            "    END AS conceito\n"
            "FROM medias\n"
            "ORDER BY aluno ASC, disciplina ASC;"
        ),
        ordem_importa=True,
        topicos=("CTE (WITH)", "CASE WHEN", "GROUP BY"),
    ),
    Challenge(
        id="dificil-5",
        nivel="dificil",
        titulo="Maior nota em cada disciplina",
        enunciado=(
            "Para cada disciplina que possui notas, mostre o nome da disciplina, o nome do aluno "
            "e a maior nota registrada naquela disciplina (incluindo empates, se houver). "
            "Ordene pelo nome da disciplina e, em caso de empate, pelo nome do aluno."
        ),
        dica="Use uma CTE com RANK() OVER (PARTITION BY d.id ORDER BY n.nota DESC) e filtre onde o rank = 1.",
        solucao_sql=(
            "WITH ranking AS (\n"
            "    SELECT\n"
            "        d.nome AS disciplina,\n"
            "        a.nome AS aluno,\n"
            "        n.nota,\n"
            "        RANK() OVER (PARTITION BY d.id ORDER BY n.nota DESC) AS pos\n"
            "    FROM notas n\n"
            "    INNER JOIN alunos_disciplinas ad ON ad.id = n.aluno_disciplina_id\n"
            "    INNER JOIN alunos a ON a.id = ad.aluno_id\n"
            "    INNER JOIN disciplinas d ON d.id = ad.disciplina_id\n"
            ")\n"
            "SELECT disciplina, aluno, nota\n"
            "FROM ranking\n"
            "WHERE pos = 1\n"
            "ORDER BY disciplina ASC, aluno ASC;"
        ),
        ordem_importa=True,
        topicos=("Window Function", "RANK()", "CTE (WITH)"),
    ),
    Challenge(
        id="dificil-6",
        nivel="dificil",
        titulo="Alcance de alunos por professor",
        enunciado=(
            "Mostre o nome de cada professor e a quantidade de alunos distintos matriculados "
            "em suas disciplinas (mesmo que o aluno faça mais de uma disciplina com o mesmo professor, "
            "ele deve ser contado apenas uma vez). Ordene da maior quantidade para a menor e pelo nome."
        ),
        dica="Conecte professores -> disciplinas -> alunos_disciplinas com LEFT JOIN e conte COUNT(DISTINCT ad.aluno_id).",
        solucao_sql=(
            "SELECT\n"
            "    p.nome AS professor,\n"
            "    COUNT(DISTINCT ad.aluno_id) AS alunos_distintos\n"
            "FROM professores p\n"
            "LEFT JOIN disciplinas d ON d.professor_id = p.id\n"
            "LEFT JOIN alunos_disciplinas ad ON ad.disciplina_id = d.id\n"
            "GROUP BY p.id, p.nome\n"
            "ORDER BY alunos_distintos DESC, p.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("LEFT JOIN", "COUNT(DISTINCT)", "GROUP BY"),
    ),
    Challenge(
        id="dificil-7",
        nivel="dificil",
        titulo="Ingressantes de 2025 no SQLite",
        enunciado=(
            "Liste o nome, a cidade e a data_matricula dos alunos matriculados no ano de 2025, "
            "ordenados pela data de matrícula e pelo nome do aluno."
        ),
        dica="No SQLite você pode extrair o ano com strftime('%Y', data_matricula) = '2025' (ou LIKE '2025-%').",
        solucao_sql=(
            "SELECT nome, cidade, data_matricula\n"
            "FROM alunos\n"
            "WHERE strftime('%Y', data_matricula) = '2025'\n"
            "ORDER BY data_matricula ASC, nome ASC;"
        ),
        ordem_importa=True,
        topicos=("strftime", "Datas SQLite", "ORDER BY"),
    ),
    Challenge(
        id="dificil-8",
        nivel="dificil",
        titulo="Taxa de conclusão por disciplina (%)",
        enunciado=(
            "Para cada disciplina que possui matrículas, calcule o total de inscritos e a taxa de conclusão "
            "percentual (matrículas com status 'concluida' divididas pelo total * 100, arredondada em 2 casas). "
            "Ordene da maior taxa para a menor e pelo nome da disciplina."
        ),
        dica="Use SUM(CASE WHEN ad.status = 'concluida' THEN 1 ELSE 0 END) * 100.0 / COUNT(ad.id).",
        solucao_sql=(
            "SELECT\n"
            "    d.nome AS disciplina,\n"
            "    COUNT(ad.id) AS total_inscritos,\n"
            "    ROUND(\n"
            "        SUM(CASE WHEN ad.status = 'concluida' THEN 1 ELSE 0 END) * 100.0 / COUNT(ad.id),\n"
            "        2\n"
            "    ) AS taxa_conclusao_pct\n"
            "FROM disciplinas d\n"
            "INNER JOIN alunos_disciplinas ad ON ad.disciplina_id = d.id\n"
            "GROUP BY d.id, d.nome\n"
            "ORDER BY taxa_conclusao_pct DESC, d.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("CASE WHEN", "Agregação Condicional", "ROUND"),
    ),
    Challenge(
        id="dificil-9",
        nivel="dificil",
        titulo="Professores com média de turma acima de 8.5",
        enunciado=(
            "Liste o nome dos professores cujos alunos alcançaram média geral de notas estritamente maior que 8.5 "
            "nas disciplinas por eles ministradas, junto com a média arredondada para 2 casas decimais. "
            "Ordene da maior média para a menor e pelo nome."
        ),
        dica="Conecte professores -> disciplinas -> alunos_disciplinas -> notas e filtre com HAVING AVG(n.nota) > 8.5.",
        solucao_sql=(
            "SELECT p.nome AS professor, ROUND(AVG(n.nota), 2) AS media_notas\n"
            "FROM professores p\n"
            "INNER JOIN disciplinas d ON d.professor_id = p.id\n"
            "INNER JOIN alunos_disciplinas ad ON ad.disciplina_id = d.id\n"
            "INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "GROUP BY p.id, p.nome\n"
            "HAVING AVG(n.nota) > 8.5\n"
            "ORDER BY media_notas DESC, p.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("Múltiplos JOINs", "GROUP BY", "HAVING"),
    ),
    Challenge(
        id="dificil-10",
        nivel="dificil",
        titulo="Top 2 posições em quantidade de disciplinas",
        enunciado=(
            "Usando DENSE_RANK(), encontre os alunos que estão nas 2 primeiras posições do ranking de "
            "quantidade de disciplinas inscritas. Retorne o nome do aluno, o total de disciplinas e a posição no ranking, "
            "ordenados pela posição e pelo nome do aluno."
        ),
        dica="Crie uma CTE agrupando por aluno com COUNT(ad.id) e DENSE_RANK() OVER (ORDER BY COUNT(ad.id) DESC), depois filtre ranking <= 2.",
        solucao_sql=(
            "WITH contagem AS (\n"
            "    SELECT\n"
            "        a.nome,\n"
            "        COUNT(ad.id) AS total_disciplinas,\n"
            "        DENSE_RANK() OVER (ORDER BY COUNT(ad.id) DESC) AS ranking\n"
            "    FROM alunos a\n"
            "    INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n"
            "    GROUP BY a.id, a.nome\n"
            ")\n"
            "SELECT nome, total_disciplinas, ranking\n"
            "FROM contagem\n"
            "WHERE ranking <= 2\n"
            "ORDER BY ranking ASC, nome ASC;"
        ),
        ordem_importa=True,
        topicos=("CTE (WITH)", "DENSE_RANK()", "Window Function"),
    ),
    Challenge(
        id="dificil-11",
        nivel="dificil",
        titulo="Alunos com todas as disciplinas concluídas",
        enunciado=(
            "Encontre o id, o nome e a quantidade de disciplinas dos alunos que possuem pelo menos 1 matrícula "
            "e têm 100% das suas matrículas com status igual a 'concluida' (nenhuma cursando ou trancada). "
            "Ordene da maior quantidade para a menor e pelo nome do aluno."
        ),
        dica="Compare COUNT(ad.id) = SUM(CASE WHEN ad.status = 'concluida' THEN 1 ELSE 0 END) no HAVING, ou use NOT EXISTS.",
        solucao_sql=(
            "SELECT a.id, a.nome, COUNT(ad.id) AS total_concluidas\n"
            "FROM alunos a\n"
            "INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n"
            "GROUP BY a.id, a.nome\n"
            "HAVING COUNT(ad.id) = SUM(CASE WHEN ad.status = 'concluida' THEN 1 ELSE 0 END)\n"
            "ORDER BY total_concluidas DESC, a.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("HAVING", "CASE WHEN", "NOT EXISTS"),
    ),
    Challenge(
        id="dificil-12",
        nivel="dificil",
        titulo="Notas comparadas à média da disciplina",
        enunciado=(
            "Para cada avaliação lançada na disciplina 'SQL Avançado e Otimização', retorne o nome do aluno, "
            "o tipo de avaliação, a nota, a média geral da disciplina (2 casas) e a diferença entre a nota do aluno "
            "e a média da disciplina (2 casas). Ordene da maior nota para a menor, pelo nome do aluno e pela avaliação."
        ),
        dica="Use AVG(n.nota) OVER (PARTITION BY d.id) para manter as linhas individuais junto com a média da turma.",
        solucao_sql=(
            "SELECT\n"
            "    a.nome AS aluno,\n"
            "    n.avaliacao,\n"
            "    n.nota,\n"
            "    ROUND(AVG(n.nota) OVER (PARTITION BY d.id), 2) AS media_disciplina,\n"
            "    ROUND(n.nota - AVG(n.nota) OVER (PARTITION BY d.id), 2) AS diferenca_media\n"
            "FROM notas n\n"
            "INNER JOIN alunos_disciplinas ad ON ad.id = n.aluno_disciplina_id\n"
            "INNER JOIN alunos a ON a.id = ad.aluno_id\n"
            "INNER JOIN disciplinas d ON d.id = ad.disciplina_id\n"
            "WHERE d.nome = 'SQL Avançado e Otimização'\n"
            "ORDER BY n.nota DESC, a.nome ASC, n.avaliacao ASC;"
        ),
        ordem_importa=True,
        topicos=("Window Function", "AVG() OVER", "Múltiplos JOINs"),
    ),
    Challenge(
        id="dificil-13",
        nivel="dificil",
        titulo="Pivot de matrículas por categoria de curso",
        enunciado=(
            "Para cada categoria de curso que possui matrículas, crie um resumo em colunas mostrando: "
            "a categoria, quantas matrículas estão 'cursando', quantas estão 'concluida', quantas estão 'trancada' "
            "e o total geral de matrículas. Ordene do maior total para o menor e pela categoria."
        ),
        dica="Use múltiplos SUM(CASE WHEN ad.status = '...' THEN 1 ELSE 0 END) agrupando por c.categoria.",
        solucao_sql=(
            "SELECT\n"
            "    c.categoria,\n"
            "    SUM(CASE WHEN ad.status = 'cursando' THEN 1 ELSE 0 END) AS cursando,\n"
            "    SUM(CASE WHEN ad.status = 'concluida' THEN 1 ELSE 0 END) AS concluidas,\n"
            "    SUM(CASE WHEN ad.status = 'trancada' THEN 1 ELSE 0 END) AS trancadas,\n"
            "    COUNT(ad.id) AS total_matriculas\n"
            "FROM cursos c\n"
            "INNER JOIN disciplinas d ON d.curso_id = c.id\n"
            "INNER JOIN alunos_disciplinas ad ON ad.disciplina_id = d.id\n"
            "GROUP BY c.categoria\n"
            "ORDER BY total_matriculas DESC, c.categoria ASC;"
        ),
        ordem_importa=True,
        topicos=("CASE WHEN", "Agregação Condicional", "Múltiplos JOINs"),
    ),
    Challenge(
        id="dificil-14",
        nivel="dificil",
        titulo="Disciplina com maior média em cada curso",
        enunciado=(
            "Para cada curso que possui avaliações lançadas, identifique a disciplina com a maior média de notas "
            "(incluindo empates, se houver). Retorne o nome do curso, o nome da disciplina e a média arredondada "
            "para 2 casas decimais, ordenados pelo nome do curso e pelo nome da disciplina."
        ),
        dica="Calcule a média por disciplina em uma CTE usando RANK() OVER (PARTITION BY c.id ORDER BY AVG(n.nota) DESC).",
        solucao_sql=(
            "WITH medias_disc AS (\n"
            "    SELECT\n"
            "        c.id AS curso_id,\n"
            "        c.nome AS curso,\n"
            "        d.nome AS disciplina,\n"
            "        ROUND(AVG(n.nota), 2) AS media_nota,\n"
            "        RANK() OVER (PARTITION BY c.id ORDER BY AVG(n.nota) DESC) AS pos\n"
            "    FROM cursos c\n"
            "    INNER JOIN disciplinas d ON d.curso_id = c.id\n"
            "    INNER JOIN alunos_disciplinas ad ON ad.disciplina_id = d.id\n"
            "    INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "    GROUP BY c.id, c.nome, d.id, d.nome\n"
            ")\n"
            "SELECT curso, disciplina, media_nota\n"
            "FROM medias_disc\n"
            "WHERE pos = 1\n"
            "ORDER BY curso ASC, disciplina ASC;"
        ),
        ordem_importa=True,
        topicos=("CTE (WITH)", "RANK()", "Window Function", "GROUP BY"),
    ),
    Challenge(
        id="dificil-15",
        nivel="dificil",
        titulo="Destaque multidisciplinar com vários professores",
        enunciado=(
            "Liste o nome do aluno, a quantidade de professores distintos que lecionaram nas disciplinas em que "
            "ele possui notas e sua média geral de notas (2 casas), apenas para alunos avaliados em disciplinas de "
            "2 ou mais professores diferentes e com média geral maior ou igual a 8.5. "
            "Ordene da maior média para a menor e pelo nome do aluno."
        ),
        dica="Conecte alunos -> alunos_disciplinas -> disciplinas -> notas e filtre com HAVING COUNT(DISTINCT d.professor_id) >= 2 AND AVG(n.nota) >= 8.5.",
        solucao_sql=(
            "SELECT\n"
            "    a.nome,\n"
            "    COUNT(DISTINCT d.professor_id) AS qtd_professores,\n"
            "    ROUND(AVG(n.nota), 2) AS media_geral\n"
            "FROM alunos a\n"
            "INNER JOIN alunos_disciplinas ad ON ad.aluno_id = a.id\n"
            "INNER JOIN disciplinas d ON d.id = ad.disciplina_id\n"
            "INNER JOIN notas n ON n.aluno_disciplina_id = ad.id\n"
            "GROUP BY a.id, a.nome\n"
            "HAVING COUNT(DISTINCT d.professor_id) >= 2 AND AVG(n.nota) >= 8.5\n"
            "ORDER BY media_geral DESC, a.nome ASC;"
        ),
        ordem_importa=True,
        topicos=("COUNT(DISTINCT)", "HAVING", "Múltiplos JOINs"),
    ),
)

CHALLENGES_BY_ID: dict[str, Challenge] = {c.id: c for c in CHALLENGES}


def list_challenges(nivel: DifficultyLevel | None = None) -> list[Challenge]:
    """Retorna todos os desafios ou filtra por nível de dificuldade."""
    if nivel is None:
        return list(CHALLENGES)
    return [c for c in CHALLENGES if c.nivel == nivel]


def get_challenge(challenge_id: str) -> Challenge | None:
    """Busca um desafio pelo ID."""
    return CHALLENGES_BY_ID.get(challenge_id)
