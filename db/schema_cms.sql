-- ===========================================
-- BANCO DE DADOS DA BASE DE CONHECIMENTO
-- ===========================================

CREATE SCHEMA cms;

-- Categorias é segmentador de mais alto nível
CREATE TABLE cms.categorias (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    slug TEXT NOT NULL,
    descricao TEXT,
    posicao SMALLINT NOT NULL DEFAULT 0, -- ordenação no menu
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cms.setores (
    id SERIAL PRIMARY KEY,
    categoria_id INT NOT NULL REFERENCES cms.categorias(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    slug TEXT NOT NULL,
    posicao SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (categoria_id, slug)
);