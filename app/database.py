"""Criação, carga inicial e inspeção de esquema dos bancos SQLite e DuckDB."""

from __future__ import annotations

import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

import duckdb

from app.schemas import DatabaseEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "escola.db"
DEFAULT_DUCKDB_PATH = PROJECT_ROOT / "data" / "escola.duckdb"

DUCKDB_READONLY_CONFIG: dict[str, str | bool | int] = {
    "enable_external_access": False,
    "allow_community_extensions": False,
    "autoinstall_known_extensions": False,
    "autoload_known_extensions": False,
    "lock_configuration": True,
    "memory_limit": "128MB",
    "threads": 1,
    "temp_directory": tempfile.gettempdir(),
    "max_temp_directory_size": "32MB",
}

DUCKDB_SCHEMA_SQL = """
CREATE TABLE professores (
    id INTEGER PRIMARY KEY,
    nome VARCHAR NOT NULL,
    especialidade VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    salario DECIMAL(10, 2) NOT NULL,
    data_contratacao DATE NOT NULL
);

CREATE TABLE cursos (
    id INTEGER PRIMARY KEY,
    nome VARCHAR NOT NULL UNIQUE,
    categoria VARCHAR NOT NULL,
    carga_horaria INTEGER NOT NULL
);

CREATE TABLE disciplinas (
    id INTEGER PRIMARY KEY,
    codigo VARCHAR NOT NULL UNIQUE,
    nome VARCHAR NOT NULL,
    carga_horaria INTEGER NOT NULL,
    curso_id INTEGER NOT NULL,
    professor_id INTEGER NOT NULL,
    FOREIGN KEY (curso_id) REFERENCES cursos(id),
    FOREIGN KEY (professor_id) REFERENCES professores(id)
);

CREATE TABLE alunos (
    id INTEGER PRIMARY KEY,
    nome VARCHAR NOT NULL,
    idade INTEGER NOT NULL,
    cidade VARCHAR NOT NULL,
    email VARCHAR NOT NULL UNIQUE,
    data_matricula DATE NOT NULL
);

CREATE TABLE alunos_disciplinas (
    id INTEGER PRIMARY KEY,
    aluno_id INTEGER NOT NULL,
    disciplina_id INTEGER NOT NULL,
    data_inscricao DATE NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('cursando', 'concluida', 'trancada')),
    UNIQUE (aluno_id, disciplina_id),
    FOREIGN KEY (aluno_id) REFERENCES alunos(id),
    FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
);

CREATE TABLE notas (
    id INTEGER PRIMARY KEY,
    aluno_disciplina_id INTEGER NOT NULL,
    avaliacao VARCHAR NOT NULL,
    nota DECIMAL(4, 2) NOT NULL CHECK (nota >= 0 AND nota <= 10),
    data_avaliacao DATE NOT NULL,
    FOREIGN KEY (aluno_disciplina_id) REFERENCES alunos_disciplinas(id)
);

CREATE INDEX idx_disciplinas_curso_id ON disciplinas(curso_id);
CREATE INDEX idx_disciplinas_professor_id ON disciplinas(professor_id);
CREATE INDEX idx_alunos_disciplinas_aluno_id ON alunos_disciplinas(aluno_id);
CREATE INDEX idx_alunos_disciplinas_disciplina_id ON alunos_disciplinas(disciplina_id);
CREATE INDEX idx_notas_aluno_disciplina_id ON notas(aluno_disciplina_id);
"""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE professores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    especialidade TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    salario REAL NOT NULL,
    data_contratacao TEXT NOT NULL
);

CREATE TABLE cursos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    categoria TEXT NOT NULL,
    carga_horaria INTEGER NOT NULL
);

CREATE TABLE disciplinas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nome TEXT NOT NULL,
    carga_horaria INTEGER NOT NULL,
    curso_id INTEGER NOT NULL,
    professor_id INTEGER NOT NULL,
    FOREIGN KEY (curso_id) REFERENCES cursos(id),
    FOREIGN KEY (professor_id) REFERENCES professores(id)
);

CREATE TABLE alunos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    idade INTEGER NOT NULL,
    cidade TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    data_matricula TEXT NOT NULL
);

CREATE TABLE alunos_disciplinas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id INTEGER NOT NULL,
    disciplina_id INTEGER NOT NULL,
    data_inscricao TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('cursando', 'concluida', 'trancada')),
    UNIQUE (aluno_id, disciplina_id),
    FOREIGN KEY (aluno_id) REFERENCES alunos(id),
    FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
);

CREATE TABLE notas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_disciplina_id INTEGER NOT NULL,
    avaliacao TEXT NOT NULL,
    nota REAL NOT NULL CHECK (nota >= 0 AND nota <= 10),
    data_avaliacao TEXT NOT NULL,
    FOREIGN KEY (aluno_disciplina_id) REFERENCES alunos_disciplinas(id)
);

CREATE INDEX idx_disciplinas_curso_id ON disciplinas(curso_id);
CREATE INDEX idx_disciplinas_professor_id ON disciplinas(professor_id);
CREATE INDEX idx_alunos_disciplinas_aluno_id ON alunos_disciplinas(aluno_id);
CREATE INDEX idx_alunos_disciplinas_disciplina_id ON alunos_disciplinas(disciplina_id);
CREATE INDEX idx_notas_aluno_disciplina_id ON notas(aluno_disciplina_id);
"""

PROFESSORES_SEED = [
    (1, "Carlos Eduardo Mendes", "Banco de Dados", "carlos.mendes@academia.edu.br", 9800.00, "2019-03-15"),
    (2, "Mariana Oliveira Costa", "Engenharia de Software", "mariana.costa@academia.edu.br", 10400.00, "2018-08-01"),
    (3, "Ricardo Almeida Santos", "Ciência de Dados", "ricardo.santos@academia.edu.br", 11200.00, "2020-02-10"),
    (4, "Fernanda Lima Rocha", "Desenvolvimento Web", "fernanda.rocha@academia.edu.br", 9200.00, "2021-07-19"),
    (5, "Thiago Pereira Souza", "Redes e Segurança", "thiago.souza@academia.edu.br", 9500.00, "2022-01-24"),
    (6, "Juliana Nogueira Campos", "Computação em Nuvem", "juliana.campos@academia.edu.br", 10800.00, "2019-11-04"),
    (7, "Alexandre Ribeiro Teixeira", "Inteligência Artificial", "alexandre.teixeira@academia.edu.br", 11900.00, "2017-05-12"),
    (8, "Patrícia Gomes Azevedo", "Sistemas Distribuídos", "patricia.azevedo@academia.edu.br", 10100.00, "2020-09-21"),
    (9, "Eduardo Ferreira Machado", "UX e Frontend", "eduardo.machado@academia.edu.br", 8900.00, "2023-02-06"),
    (10, "Beatriz Vasconcelos Pinto", "DevOps e SRE", "beatriz.pinto@academia.edu.br", 10600.00, "2021-04-14"),
]

CURSOS_SEED = [
    (1, "Ciência da Computação", "Tecnologia", 3200),
    (2, "Sistemas de Informação", "Tecnologia", 2800),
    (3, "Engenharia de Software", "Engenharia", 3000),
    (4, "Análise e Desenvolvimento de Sistemas", "Tecnologia", 2000),
    (5, "Ciência de Dados e IA", "Dados", 2400),
    (6, "Segurança da Informação", "Infraestrutura", 2200),
    (7, "Arquitetura em Nuvem", "Infraestrutura", 1800),
    (8, "Engenharia de Dados", "Dados", 2600),
    (9, "Desenvolvimento Full Stack", "Tecnologia", 2100),
    (10, "Sistemas Embarcados e IoT", "Engenharia", 2500),
    (11, "Computação Aplicada", "Dados", 2300),
    (12, "Governança e Qualidade de TI", "Gestão", 1900),
]

DISCIPLINAS_SEED = [
    (1, "BD101", "Modelagem de Dados", 60, 1, 1),
    (2, "BD202", "SQL Avançado e Otimização", 80, 2, 1),
    (3, "BD303", "Administração de Bancos NoSQL", 60, 1, 1),
    (4, "ES101", "Arquitetura de Software", 80, 3, 2),
    (5, "ES204", "Testes Automatizados e Qualidade", 60, 3, 2),
    (6, "CD101", "Estatística Aplicada", 60, 5, 3),
    (7, "CD205", "Machine Learning", 80, 5, 3),
    (8, "DW101", "Desenvolvimento Backend com Python", 80, 4, 4),
    (9, "DW202", "Interfaces Web Responsivas", 60, 4, 4),
    (10, "RS101", "Segurança em Aplicações Web", 60, 6, 5),
    (11, "ES305", "Padrões de Projeto e Clean Code", 80, 3, 2),
    (12, "RS202", "Criptografia e Redes Seguras", 60, 6, 5),
    (13, "CN101", "Fundamentos de Cloud Computing", 60, 7, 6),
    (14, "CN204", "Containers e Orquestração", 80, 7, 6),
    (15, "IA101", "Redes Neurais e Deep Learning", 80, 5, 7),
    (16, "IA202", "Processamento de Linguagem Natural", 60, 11, 7),
    (17, "SD101", "Sistemas Distribuídos e Mensageria", 80, 8, 8),
    (18, "SD203", "Engenharia de Pipelines de Dados", 80, 8, 8),
    (19, "UX101", "Design de Interfaces e Acessibilidade", 40, 9, 9),
    (20, "DV101", "CI/CD e Observabilidade", 60, 12, 10),
]

ALUNOS_SEED = [
    (1, "Ana Beatriz Silva", 22, "São Paulo", "ana.silva@aluno.edu.br", "2024-02-05"),
    (2, "Bruno Henrique Martins", 34, "Rio de Janeiro", "bruno.martins@aluno.edu.br", "2023-08-12"),
    (3, "Camila Ferreira Dias", 27, "Belo Horizonte", "camila.dias@aluno.edu.br", "2024-02-10"),
    (4, "Daniel Augusto Ribeiro", 31, "Curitiba", "daniel.ribeiro@aluno.edu.br", "2023-03-01"),
    (5, "Eduarda Nogueira Lima", 19, "São Paulo", "eduarda.lima@aluno.edu.br", "2025-02-03"),
    (6, "Felipe Carvalho Gomes", 38, "Porto Alegre", "felipe.gomes@aluno.edu.br", "2022-08-15"),
    (7, "Gabriela Teixeira Nunes", 24, "Recife", "gabriela.nunes@aluno.edu.br", "2024-08-05"),
    (8, "Henrique Barbosa Pires", 42, "São Paulo", "henrique.pires@aluno.edu.br", "2023-02-20"),
    (9, "Isabela Monteiro Castro", 21, "Florianópolis", "isabela.castro@aluno.edu.br", "2025-02-04"),
    (10, "João Victor Azevedo", 29, "Curitiba", "joao.azevedo@aluno.edu.br", "2024-02-11"),
    (11, "Larissa Duarte Fonseca", 33, "Rio de Janeiro", "larissa.fonseca@aluno.edu.br", "2023-08-18"),
    (12, "Lucas Gabriel Moreira", 25, "Belo Horizonte", "lucas.moreira@aluno.edu.br", "2024-02-14"),
    (13, "Mariana Cardoso Neves", 36, "São Paulo", "mariana.neves@aluno.edu.br", "2023-03-06"),
    (14, "Mateus Rodrigues Cunha", 20, "Recife", "mateus.cunha@aluno.edu.br", "2025-02-07"),
    (15, "Natália Freitas Borges", 28, "Porto Alegre", "natalia.borges@aluno.edu.br", "2024-08-09"),
    (16, "Otávio Santana Melo", 41, "Curitiba", "otavio.melo@aluno.edu.br", "2022-08-22"),
    (17, "Patrícia Vieira Correia", 30, "Florianópolis", "patricia.correia@aluno.edu.br", "2023-08-25"),
    (18, "Rafael Augusto Tavares", 23, "São Paulo", "rafael.tavares@aluno.edu.br", "2024-08-12"),
    (19, "Renata Campos Vasconcelos", 35, "Rio de Janeiro", "renata.vasconcelos@aluno.edu.br", "2023-02-27"),
    (20, "Rodrigo Batista Moura", 26, "Belo Horizonte", "rodrigo.moura@aluno.edu.br", "2024-02-19"),
    (21, "Sofia Andrade Pinto", 22, "Porto Alegre", "sofia.pinto@aluno.edu.br", "2025-02-10"),
    (22, "Thiago Henrique Lopes", 39, "Recife", "thiago.lopes@aluno.edu.br", "2022-09-01"),
    (23, "Vanessa Cristina Rezende", 32, "São Paulo", "vanessa.rezende@aluno.edu.br", "2023-08-29"),
    (24, "Vinícius Soares Teixeira", 24, "Florianópolis", "vinicius.teixeira@aluno.edu.br", "2024-08-14"),
    (25, "Yasmin Alencar Farias", 27, "Curitiba", "yasmin.farias@aluno.edu.br", "2024-02-22"),
    (26, "Arthur Mendes Cavalcanti", 23, "Salvador", "arthur.cavalcanti@aluno.edu.br", "2024-08-19"),
    (27, "Bianca Costa Silveira", 37, "São Paulo", "bianca.silveira@aluno.edu.br", "2023-03-14"),
    (28, "Caio Vinícius Prado", 29, "Campinas", "caio.prado@aluno.edu.br", "2024-02-26"),
    (29, "Débora Alencar Moraes", 31, "Belo Horizonte", "debora.moraes@aluno.edu.br", "2023-09-04"),
    (30, "Enzo Gabriel Queiroz", 19, "Curitiba", "enzo.queiroz@aluno.edu.br", "2025-02-12"),
    (31, "Fernanda Lopes Guimarães", 44, "Rio de Janeiro", "fernanda.guimaraes@aluno.edu.br", "2022-08-10"),
    (32, "Gustavo Henrique Bastos", 26, "Porto Alegre", "gustavo.bastos@aluno.edu.br", "2024-02-28"),
    (33, "Helena Cardoso Siqueira", 33, "Florianópolis", "helena.siqueira@aluno.edu.br", "2023-08-30"),
    (34, "Igor Nascimento Peixoto", 25, "Recife", "igor.peixoto@aluno.edu.br", "2024-08-21"),
    (35, "Júlia Ramos Fonseca", 21, "São Paulo", "julia.fonseca@aluno.edu.br", "2025-02-15"),
    (36, "Kevin Oliveira Barreto", 35, "Salvador", "kevin.barreto@aluno.edu.br", "2023-03-20"),
    (37, "Letícia Machado Porto", 28, "Campinas", "leticia.porto@aluno.edu.br", "2024-03-04"),
    (38, "Marcelo Duarte Viana", 40, "Belo Horizonte", "marcelo.viana@aluno.edu.br", "2022-09-12"),
    (39, "Nicole Araújo Medeiros", 22, "Curitiba", "nicole.medeiros@aluno.edu.br", "2025-02-17"),
    (40, "Pedro Lucas Nogueira", 30, "Rio de Janeiro", "pedro.nogueira@aluno.edu.br", "2023-09-08"),
    (41, "Queila Souza Monteiro", 34, "Porto Alegre", "queila.monteiro@aluno.edu.br", "2023-04-03"),
    (42, "Raul Ferreira Franco", 27, "São Paulo", "raul.franco@aluno.edu.br", "2024-08-25"),
    (43, "Sabrina Vieira Lacerda", 24, "Florianópolis", "sabrina.lacerda@aluno.edu.br", "2024-03-07"),
    (44, "Tiago Borges Coutinho", 36, "Recife", "tiago.coutinho@aluno.edu.br", "2023-04-11"),
    (45, "Úrsula Andrade Rangel", 29, "Salvador", "ursula.rangel@aluno.edu.br", "2024-08-28"),
    (46, "Vitor Hugo Salgado", 20, "Campinas", "vitor.salgado@aluno.edu.br", "2025-02-19"),
    (47, "Wesley Rocha Pinheiro", 38, "Curitiba", "wesley.pinheiro@aluno.edu.br", "2022-09-18"),
    (48, "Xênia Lima Macedo", 26, "Belo Horizonte", "xenia.macedo@aluno.edu.br", "2024-03-11"),
    (49, "Yuri Santos Carvalho", 32, "Rio de Janeiro", "yuri.carvalho@aluno.edu.br", "2023-09-14"),
    (50, "Zuleica Martins Braga", 28, "São Paulo", "zuleica.braga@aluno.edu.br", "2024-03-15"),
]

# Relação N:N entre alunos e disciplinas (alunos 25 e 50 sem matrículas para cenários de LEFT JOIN)
ALUNOS_DISCIPLINAS_SEED = [
    (1, 1, 1, "2024-02-10", "concluida"),
    (2, 1, 2, "2024-08-05", "cursando"),
    (3, 1, 8, "2024-08-05", "cursando"),
    (4, 2, 1, "2023-08-15", "concluida"),
    (5, 2, 2, "2024-02-10", "concluida"),
    (6, 2, 6, "2024-08-10", "cursando"),
    (7, 2, 10, "2024-08-10", "trancada"),
    (8, 3, 4, "2024-02-12", "concluida"),
    (9, 3, 5, "2024-08-12", "cursando"),
    (10, 4, 1, "2023-03-05", "concluida"),
    (11, 4, 3, "2024-02-15", "concluida"),
    (12, 4, 8, "2024-08-08", "cursando"),
    (13, 5, 8, "2025-02-06", "cursando"),
    (14, 5, 9, "2025-02-06", "cursando"),
    (15, 6, 2, "2023-02-20", "concluida"),
    (16, 6, 6, "2023-08-20", "concluida"),
    (17, 6, 7, "2024-02-20", "cursando"),
    (18, 7, 4, "2024-08-07", "cursando"),
    (19, 7, 9, "2024-08-07", "cursando"),
    (20, 8, 1, "2023-03-01", "concluida"),
    (21, 8, 2, "2023-08-18", "concluida"),
    (22, 8, 10, "2024-02-18", "concluida"),
    (23, 9, 6, "2025-02-07", "cursando"),
    (24, 9, 8, "2025-02-07", "cursando"),
    (25, 10, 4, "2024-02-14", "concluida"),
    (26, 10, 5, "2024-08-14", "trancada"),
    (27, 10, 8, "2024-08-14", "cursando"),
    (28, 11, 6, "2023-08-20", "concluida"),
    (29, 11, 7, "2024-02-20", "concluida"),
    (30, 12, 1, "2024-02-16", "concluida"),
    (31, 12, 8, "2024-08-16", "cursando"),
    (32, 13, 2, "2023-03-10", "concluida"),
    (33, 13, 3, "2023-08-21", "concluida"),
    (34, 13, 7, "2024-08-11", "cursando"),
    (35, 14, 9, "2025-02-09", "cursando"),
    (36, 15, 4, "2024-08-11", "cursando"),
    (37, 15, 5, "2024-08-11", "cursando"),
    (38, 16, 1, "2022-08-25", "concluida"),
    (39, 16, 10, "2023-03-04", "concluida"),
    (40, 17, 6, "2023-08-27", "concluida"),
    (41, 17, 7, "2024-02-25", "cursando"),
    (42, 18, 8, "2024-08-15", "cursando"),
    (43, 18, 9, "2024-08-15", "trancada"),
    (44, 19, 2, "2023-03-02", "concluida"),
    (45, 19, 3, "2023-08-22", "concluida"),
    (46, 19, 10, "2024-02-22", "concluida"),
    (47, 20, 4, "2024-02-21", "concluida"),
    (48, 20, 5, "2024-08-18", "cursando"),
    (49, 21, 6, "2025-02-11", "cursando"),
    (50, 22, 1, "2022-09-05", "concluida"),
    (51, 22, 10, "2023-03-10", "concluida"),
    (52, 23, 7, "2023-09-01", "concluida"),
    (53, 23, 8, "2024-02-26", "concluida"),
    (54, 24, 9, "2024-08-16", "cursando"),
    (55, 24, 10, "2024-08-16", "cursando"),
    # Novas matrículas (alunos 26..49 e novas disciplinas 11..20)
    (56, 26, 11, "2024-08-20", "cursando"),
    (57, 26, 13, "2024-08-20", "concluida"),
    (58, 27, 1, "2023-03-20", "concluida"),
    (59, 27, 14, "2024-02-15", "concluida"),
    (60, 27, 20, "2024-08-18", "cursando"),
    (61, 28, 12, "2024-03-01", "concluida"),
    (62, 28, 17, "2024-08-19", "cursando"),
    (63, 29, 15, "2023-09-08", "concluida"),
    (64, 29, 16, "2024-02-22", "concluida"),
    (65, 30, 19, "2025-02-14", "cursando"),
    (66, 30, 9, "2025-02-14", "cursando"),
    (67, 31, 2, "2022-08-18", "concluida"),
    (68, 31, 18, "2023-03-14", "concluida"),
    (69, 31, 15, "2024-02-19", "trancada"),
    (70, 32, 11, "2024-03-04", "concluida"),
    (71, 32, 13, "2024-08-21", "cursando"),
    (72, 33, 14, "2023-09-02", "concluida"),
    (73, 33, 20, "2024-02-27", "concluida"),
    (74, 34, 17, "2024-08-22", "cursando"),
    (75, 34, 18, "2024-08-22", "cursando"),
    (76, 35, 19, "2025-02-16", "cursando"),
    (77, 35, 8, "2025-02-16", "cursando"),
    (78, 36, 12, "2023-03-22", "concluida"),
    (79, 36, 10, "2023-09-10", "concluida"),
    (80, 37, 15, "2024-03-08", "concluida"),
    (81, 37, 16, "2024-08-24", "cursando"),
    (82, 38, 13, "2022-09-15", "concluida"),
    (83, 38, 14, "2023-03-18", "concluida"),
    (84, 38, 20, "2024-03-05", "concluida"),
    (85, 39, 11, "2025-02-19", "cursando"),
    (86, 40, 17, "2023-09-12", "concluida"),
    (87, 40, 18, "2024-03-01", "concluida"),
    (88, 41, 1, "2023-04-06", "concluida"),
    (89, 41, 18, "2024-03-06", "concluida"),
    (90, 41, 16, "2024-08-26", "cursando"),
    (91, 42, 19, "2024-08-27", "cursando"),
    (92, 42, 20, "2024-08-27", "trancada"),
    (93, 43, 12, "2024-03-11", "concluida"),
    (94, 43, 13, "2024-08-28", "cursando"),
    (95, 44, 15, "2023-04-15", "concluida"),
    (96, 44, 7, "2023-09-15", "concluida"),
    (97, 45, 14, "2024-08-30", "cursando"),
    (98, 45, 17, "2024-08-30", "cursando"),
    (99, 46, 19, "2025-02-20", "cursando"),
    (100, 46, 11, "2025-02-20", "cursando"),
    (101, 47, 12, "2022-09-21", "concluida"),
    (102, 47, 13, "2023-03-25", "concluida"),
    (103, 47, 20, "2024-03-12", "concluida"),
    (104, 48, 16, "2024-03-14", "concluida"),
    (105, 48, 18, "2024-08-31", "cursando"),
    (106, 49, 15, "2023-09-18", "concluida"),
    (107, 49, 17, "2024-03-16", "concluida"),
    (108, 49, 14, "2024-09-02", "cursando"),
]

NOTAS_SEED = [
    (1, 1, "P1", 8.5, "2024-04-15"),
    (2, 1, "P2", 9.0, "2024-06-20"),
    (3, 2, "P1", 7.5, "2024-10-10"),
    (4, 3, "P1", 8.8, "2024-10-12"),
    (5, 4, "P1", 9.2, "2023-10-15"),
    (6, 4, "P2", 8.7, "2023-12-05"),
    (7, 5, "P1", 8.0, "2024-04-18"),
    (8, 5, "P2", 9.5, "2024-06-22"),
    (9, 6, "P1", 7.8, "2024-10-14"),
    (10, 8, "P1", 6.5, "2024-04-12"),
    (11, 8, "P2", 7.5, "2024-06-18"),
    (12, 9, "Trabalho", 8.2, "2024-10-20"),
    (13, 10, "P1", 9.0, "2023-05-10"),
    (14, 10, "P2", 9.4, "2023-07-02"),
    (15, 11, "P1", 8.6, "2024-04-20"),
    (16, 11, "Projeto Final", 9.1, "2024-06-25"),
    (17, 12, "P1", 7.0, "2024-10-15"),
    (18, 13, "P1", 8.9, "2025-04-10"),
    (19, 14, "Trabalho", 9.3, "2025-04-18"),
    (20, 15, "P1", 7.2, "2023-05-12"),
    (21, 15, "P2", 6.8, "2023-07-05"),
    (22, 16, "P1", 8.4, "2023-10-18"),
    (23, 16, "P2", 8.9, "2023-12-08"),
    (24, 17, "Trabalho", 7.7, "2024-05-14"),
    (25, 18, "P1", 9.1, "2024-10-11"),
    (26, 19, "Trabalho", 8.5, "2024-10-19"),
    (27, 20, "P1", 9.8, "2023-05-09"),
    (28, 20, "P2", 9.6, "2023-07-01"),
    (29, 21, "P1", 9.5, "2023-10-16"),
    (30, 21, "P2", 9.7, "2023-12-06"),
    (31, 22, "P1", 9.0, "2024-04-22"),
    (32, 22, "Projeto Final", 9.4, "2024-06-28"),
    (33, 23, "P1", 8.0, "2025-04-11"),
    (34, 24, "P1", 8.6, "2025-04-16"),
    (35, 25, "P1", 7.4, "2024-04-19"),
    (36, 25, "P2", 8.1, "2024-06-21"),
    (37, 27, "P1", 6.9, "2024-10-17"),
    (38, 28, "P1", 8.8, "2023-10-19"),
    (39, 28, "P2", 9.1, "2023-12-10"),
    (40, 29, "P1", 8.5, "2024-04-24"),
    (41, 29, "Projeto Final", 9.2, "2024-06-29"),
    (42, 30, "P1", 6.0, "2024-04-16"),
    (43, 30, "P2", 6.5, "2024-06-22"),
    (44, 31, "P1", 7.9, "2024-10-18"),
    (45, 32, "P1", 9.3, "2023-05-15"),
    (46, 32, "P2", 9.5, "2023-07-04"),
    (47, 33, "P1", 8.7, "2023-10-20"),
    (48, 33, "P2", 9.0, "2023-12-11"),
    (49, 34, "Trabalho", 8.8, "2024-10-22"),
    (50, 35, "P1", 7.6, "2025-04-14"),
    (51, 36, "P1", 8.3, "2024-10-13"),
    (52, 37, "Trabalho", 8.9, "2024-10-21"),
    (53, 38, "P1", 5.8, "2022-10-18"),
    (54, 38, "P2", 6.4, "2022-12-08"),
    (55, 39, "P1", 7.1, "2023-05-18"),
    (56, 39, "Projeto Final", 7.9, "2023-07-06"),
    (57, 40, "P1", 8.2, "2023-10-21"),
    (58, 40, "P2", 8.5, "2023-12-12"),
    (59, 41, "P1", 7.4, "2024-04-25"),
    (60, 42, "P1", 9.0, "2024-10-15"),
    (61, 44, "P1", 8.1, "2023-05-16"),
    (62, 44, "P2", 8.6, "2023-07-07"),
    (63, 45, "P1", 7.8, "2023-10-23"),
    (64, 45, "P2", 8.2, "2023-12-13"),
    (65, 46, "P1", 8.9, "2024-04-26"),
    (66, 46, "Projeto Final", 9.3, "2024-06-30"),
    (67, 47, "P1", 7.5, "2024-04-21"),
    (68, 47, "P2", 7.7, "2024-06-23"),
    (69, 48, "Trabalho", 8.4, "2024-10-23"),
    (70, 49, "P1", 9.4, "2025-04-12"),
    (71, 50, "P1", 6.7, "2022-10-19"),
    (72, 50, "P2", 7.3, "2022-12-09"),
    (73, 51, "P1", 7.6, "2023-05-19"),
    (74, 51, "Projeto Final", 8.0, "2023-07-08"),
    (75, 52, "P1", 9.1, "2023-10-24"),
    (76, 52, "P2", 9.6, "2023-12-14"),
    (77, 53, "P1", 8.8, "2024-04-27"),
    (78, 53, "Projeto Final", 9.2, "2024-07-01"),
    (79, 54, "Trabalho", 8.1, "2024-10-24"),
    # Novas notas para as matrículas 56..107 (matrículas 55 e 108 propositalmente sem nota lançada)
    (80, 56, "P1", 8.4, "2024-10-12"),
    (81, 57, "P1", 9.1, "2024-10-14"),
    (82, 57, "P2", 8.9, "2024-12-04"),
    (83, 58, "P1", 7.8, "2023-05-14"),
    (84, 58, "P2", 8.2, "2023-07-03"),
    (85, 59, "P1", 9.4, "2024-04-18"),
    (86, 59, "Projeto Final", 9.6, "2024-06-27"),
    (87, 60, "Trabalho", 8.7, "2024-10-22"),
    (88, 61, "P1", 7.1, "2024-04-20"),
    (89, 61, "P2", 7.5, "2024-06-24"),
    (90, 62, "P1", 8.0, "2024-10-19"),
    (91, 63, "P1", 9.5, "2023-10-20"),
    (92, 63, "P2", 9.8, "2023-12-10"),
    (93, 64, "P1", 9.2, "2024-04-22"),
    (94, 64, "Projeto Final", 9.4, "2024-06-29"),
    (95, 65, "Trabalho", 8.6, "2025-04-15"),
    (96, 66, "P1", 7.9, "2025-04-17"),
    (97, 67, "P1", 6.4, "2022-10-14"),
    (98, 67, "P2", 7.0, "2022-12-06"),
    (99, 68, "P1", 8.3, "2023-05-18"),
    (100, 68, "P2", 8.8, "2023-07-06"),
    (101, 70, "P1", 9.0, "2024-04-25"),
    (102, 70, "P2", 9.2, "2024-06-28"),
    (103, 71, "Trabalho", 8.5, "2024-10-25"),
    (104, 72, "P1", 7.7, "2023-10-22"),
    (105, 72, "P2", 8.1, "2023-12-12"),
    (106, 73, "P1", 8.9, "2024-04-26"),
    (107, 73, "Projeto Final", 9.3, "2024-07-02"),
    (108, 74, "P1", 7.4, "2024-10-20"),
    (109, 75, "Trabalho", 8.2, "2024-10-23"),
    (110, 76, "Trabalho", 9.1, "2025-04-16"),
    (111, 77, "P1", 8.8, "2025-04-18"),
    (112, 78, "P1", 6.2, "2023-05-16"),
    (113, 78, "P2", 6.9, "2023-07-08"),
    (114, 79, "P1", 7.3, "2023-10-25"),
    (115, 79, "Projeto Final", 7.8, "2023-12-15"),
    (116, 80, "P1", 9.4, "2024-04-28"),
    (117, 80, "P2", 9.7, "2024-06-30"),
    (118, 81, "Trabalho", 9.0, "2024-10-26"),
    (119, 82, "P1", 8.0, "2022-10-21"),
    (120, 82, "P2", 8.4, "2022-12-11"),
    (121, 83, "P1", 8.6, "2023-05-20"),
    (122, 83, "P2", 8.9, "2023-07-09"),
    (123, 84, "P1", 9.1, "2024-04-29"),
    (124, 84, "Projeto Final", 9.5, "2024-07-03"),
    (125, 85, "P1", 7.5, "2025-04-19"),
    (126, 86, "P1", 8.7, "2023-10-26"),
    (127, 86, "P2", 9.0, "2023-12-16"),
    (128, 87, "P1", 8.4, "2024-04-30"),
    (129, 87, "Projeto Final", 8.8, "2024-07-04"),
    (130, 88, "P1", 7.2, "2023-05-22"),
    (131, 88, "P2", 7.6, "2023-07-10"),
    (132, 89, "P1", 8.1, "2024-05-02"),
    (133, 89, "P2", 8.5, "2024-07-05"),
    (134, 90, "Trabalho", 7.9, "2024-10-27"),
    (135, 91, "Trabalho", 9.3, "2024-10-28"),
    (136, 93, "P1", 6.8, "2024-05-03"),
    (137, 93, "P2", 7.4, "2024-07-06"),
    (138, 94, "P1", 8.2, "2024-10-29"),
    (139, 95, "P1", 9.6, "2023-05-24"),
    (140, 95, "P2", 9.9, "2023-07-11"),
    (141, 96, "P1", 9.0, "2023-10-28"),
    (142, 96, "Projeto Final", 9.4, "2023-12-18"),
    (143, 97, "Trabalho", 8.3, "2024-10-30"),
    (144, 98, "P1", 7.7, "2024-10-31"),
    (145, 99, "Trabalho", 8.9, "2025-04-20"),
    (146, 100, "P1", 8.4, "2025-04-22"),
    (147, 101, "P1", 5.9, "2022-10-24"),
    (148, 101, "P2", 6.6, "2022-12-13"),
    (149, 102, "P1", 7.5, "2023-05-26"),
    (150, 102, "P2", 8.0, "2023-07-12"),
    (151, 103, "P1", 8.2, "2024-05-05"),
    (152, 103, "Projeto Final", 8.7, "2024-07-08"),
    (153, 104, "P1", 9.1, "2024-05-06"),
    (154, 104, "P2", 9.3, "2024-07-09"),
    (155, 105, "Trabalho", 8.6, "2024-11-01"),
    (156, 106, "P1", 9.5, "2023-10-30"),
    (157, 106, "P2", 9.7, "2023-12-19"),
    (158, 107, "P1", 8.9, "2024-05-08"),
    (159, 107, "Projeto Final", 9.1, "2024-07-10"),
]


def create_and_seed_database(db_path: Path = DEFAULT_DB_PATH, overwrite: bool = False) -> Path:
    """Cria o banco SQLite com o schema acadêmico e popula os dados iniciais."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        if not overwrite:
            return db_path
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        with conn:
            conn.executemany(
                "INSERT INTO professores (id, nome, especialidade, email, salario, data_contratacao) VALUES (?, ?, ?, ?, ?, ?)",
                PROFESSORES_SEED,
            )
            conn.executemany(
                "INSERT INTO cursos (id, nome, categoria, carga_horaria) VALUES (?, ?, ?, ?)",
                CURSOS_SEED,
            )
            conn.executemany(
                "INSERT INTO disciplinas (id, codigo, nome, carga_horaria, curso_id, professor_id) VALUES (?, ?, ?, ?, ?, ?)",
                DISCIPLINAS_SEED,
            )
            conn.executemany(
                "INSERT INTO alunos (id, nome, idade, cidade, email, data_matricula) VALUES (?, ?, ?, ?, ?, ?)",
                ALUNOS_SEED,
            )
            conn.executemany(
                "INSERT INTO alunos_disciplinas (id, aluno_id, disciplina_id, data_inscricao, status) VALUES (?, ?, ?, ?, ?)",
                ALUNOS_DISCIPLINAS_SEED,
            )
            conn.executemany(
                "INSERT INTO notas (id, aluno_disciplina_id, avaliacao, nota, data_avaliacao) VALUES (?, ?, ?, ?, ?)",
                NOTAS_SEED,
            )
    finally:
        conn.close()

    return db_path


def connect_duckdb_readonly(db_path: Path = DEFAULT_DUCKDB_PATH) -> duckdb.DuckDBPyConnection:
    """Abre uma conexão DuckDB somente leitura com configuração sandbox travada."""
    resolved = Path(db_path).resolve()
    return duckdb.connect(
        str(resolved),
        read_only=True,
        config=dict(DUCKDB_READONLY_CONFIG),
    )


def create_and_seed_duckdb(
    db_path: Path = DEFAULT_DUCKDB_PATH,
    overwrite: bool = False,
) -> Path:
    """Cria o banco DuckDB com o schema acadêmico e popula os mesmos registros iniciais."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists():
        if not overwrite:
            return db_path
        db_path.unlink()

    wal_path = Path(f"{db_path}.wal")
    if wal_path.exists():
        wal_path.unlink()

    conn = duckdb.connect(str(db_path.resolve()))
    try:
        conn.execute(DUCKDB_SCHEMA_SQL)
        conn.begin()
        try:
            conn.executemany(
                "INSERT INTO professores (id, nome, especialidade, email, salario, data_contratacao) VALUES (?, ?, ?, ?, ?, ?)",
                PROFESSORES_SEED,
            )
            conn.executemany(
                "INSERT INTO cursos (id, nome, categoria, carga_horaria) VALUES (?, ?, ?, ?)",
                CURSOS_SEED,
            )
            conn.executemany(
                "INSERT INTO disciplinas (id, codigo, nome, carga_horaria, curso_id, professor_id) VALUES (?, ?, ?, ?, ?, ?)",
                DISCIPLINAS_SEED,
            )
            conn.executemany(
                "INSERT INTO alunos (id, nome, idade, cidade, email, data_matricula) VALUES (?, ?, ?, ?, ?, ?)",
                ALUNOS_SEED,
            )
            conn.executemany(
                "INSERT INTO alunos_disciplinas (id, aluno_id, disciplina_id, data_inscricao, status) VALUES (?, ?, ?, ?, ?)",
                ALUNOS_DISCIPLINAS_SEED,
            )
            conn.executemany(
                "INSERT INTO notas (id, aluno_disciplina_id, avaliacao, nota, data_avaliacao) VALUES (?, ?, ?, ?, ?)",
                NOTAS_SEED,
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()

    return db_path


def create_and_seed_all_databases(
    sqlite_path: Path = DEFAULT_DB_PATH,
    duckdb_path: Path = DEFAULT_DUCKDB_PATH,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Cria e popula as bases SQLite e DuckDB com os mesmos dados."""
    sqlite_file = create_and_seed_database(db_path=sqlite_path, overwrite=overwrite)
    duckdb_file = create_and_seed_duckdb(db_path=duckdb_path, overwrite=overwrite)
    return sqlite_file, duckdb_file


def ensure_database(
    db_path: Path | None = None,
    engine: DatabaseEngine = "sqlite",
) -> Path:
    """Garante que o banco do motor especificado exista no caminho esperado."""
    if engine == "duckdb":
        target = Path(db_path) if db_path is not None else DEFAULT_DUCKDB_PATH
        return create_and_seed_duckdb(db_path=target, overwrite=False)
    target = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    return create_and_seed_database(db_path=target, overwrite=False)


_FK_TEXT_RE = re.compile(
    r"FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+([^\s(]+)\s*\(([^)]+)\)",
    re.IGNORECASE,
)


def _strip_ident_quotes(name: str) -> str:
    return name.strip().strip('"').strip("'").strip("`")


_TABLE_DISPLAY_ORDER = {
    "professores": 0,
    "cursos": 1,
    "disciplinas": 2,
    "alunos": 3,
    "alunos_disciplinas": 4,
    "notas": 5,
}


def get_duckdb_schema_metadata(db_path: Path = DEFAULT_DUCKDB_PATH) -> list[dict[str, Any]]:
    """Retorna metadados das tabelas, colunas, chaves e contagem de registros do DuckDB."""
    ensure_database(db_path, engine="duckdb")
    conn = connect_duckdb_readonly(db_path)
    try:
        tables = conn.execute(
            """
            SELECT table_name
            FROM duckdb_tables()
            WHERE schema_name = 'main' AND NOT internal
            ORDER BY table_oid
            """
        ).fetchall()
        ordered_tables = sorted(
            (row[0] for row in tables),
            key=lambda name: (_TABLE_DISPLAY_ORDER.get(name, 99), name),
        )

        metadata: list[dict[str, Any]] = []
        for table_name in ordered_tables:
            constraint_rows = conn.execute(
                """
                SELECT constraint_type, constraint_column_names, constraint_text
                FROM duckdb_constraints()
                WHERE schema_name = 'main' AND table_name = ?
                """,
                [table_name],
            ).fetchall()

            pk_cols: set[str] = set()
            fk_map: dict[str, str] = {}
            for c_type, c_cols, c_text in constraint_rows:
                if c_type == "PRIMARY KEY" and c_cols:
                    pk_cols.update(str(col) for col in c_cols)
                elif c_type == "FOREIGN KEY" and c_text:
                    match = _FK_TEXT_RE.search(c_text)
                    if match:
                        from_col = _strip_ident_quotes(match.group(1).split(",")[0])
                        ref_table = _strip_ident_quotes(match.group(2))
                        ref_col = _strip_ident_quotes(match.group(3).split(",")[0])
                        fk_map[from_col] = f"{ref_table}.{ref_col}"

            col_rows = conn.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM duckdb_columns()
                WHERE schema_name = 'main' AND table_name = ? AND NOT internal
                ORDER BY column_index
                """,
                [table_name],
            ).fetchall()

            columns = [
                {
                    "name": col_name,
                    "type": data_type or "VARCHAR",
                    "nullable": bool(is_nullable),
                    "primary_key": col_name in pk_cols,
                    "foreign_key": fk_map.get(col_name),
                }
                for col_name, data_type, is_nullable in col_rows
            ]

            row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            metadata.append(
                {
                    "name": table_name,
                    "row_count": row_count,
                    "columns": columns,
                }
            )
        return metadata
    finally:
        conn.close()


def get_schema_metadata(
    db_path: Path | None = None,
    engine: DatabaseEngine = "sqlite",
) -> list[dict[str, Any]]:
    """Retorna metadados das tabelas, colunas, chaves e contagem de registros."""
    if engine == "duckdb":
        return get_duckdb_schema_metadata(db_path if db_path is not None else DEFAULT_DUCKDB_PATH)

    sqlite_path = db_path if db_path is not None else DEFAULT_DB_PATH
    ensure_database(sqlite_path, engine="sqlite")
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY rowid
            """
        ).fetchall()

        metadata: list[dict[str, Any]] = []
        for table_row in tables:
            table_name = table_row["name"]
            fk_rows = conn.execute(f'PRAGMA foreign_key_list("{table_name}")').fetchall()
            fk_map = {
                fk["from"]: f"{fk['table']}.{fk['to']}"
                for fk in fk_rows
            }

            col_rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            columns = [
                {
                    "name": col["name"],
                    "type": col["type"] or "TEXT",
                    "nullable": not bool(col["notnull"]),
                    "primary_key": bool(col["pk"]),
                    "foreign_key": fk_map.get(col["name"]),
                }
                for col in col_rows
            ]

            row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
            metadata.append(
                {
                    "name": table_name,
                    "row_count": row_count,
                    "columns": columns,
                }
            )
        return metadata
    finally:
        conn.close()


if __name__ == "__main__":
    sqlite_file, duckdb_file = create_and_seed_all_databases(overwrite=True)
    print(f"Banco SQLite criado e populado em: {sqlite_file}")
    print(f"Banco DuckDB criado e populado em: {duckdb_file}")
