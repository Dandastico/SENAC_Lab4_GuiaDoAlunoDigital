-- ===========================================
-- BANCO DE DADOS DA BASE DE CONHECIMENTO
-- ===========================================

CREATE SCHEMA cms;

-- ENUM para os possíveris estados de um artigo
CREATE TYPE cms.artigo_status AS ENUM (
    'rascunho',     -- visível para os admin
    'publicado',    -- visível para todos
    'escondido',    -- ocultado manualmente pelo admin
    'agendado'      -- será publicado em agendado_para
);

-- Categorias são os segmentadores de mais alto nível
CREATE TABLE cms.categorias (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    descricao TEXT,
    posicao SMALLINT NOT NULL DEFAULT 0, -- ordenação no menu
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seções são segmentações que habitam dentro das categorias
CREATE TABLE cms.setores (
    id SERIAL PRIMARY KEY,
    categoria_id INT NOT NULL REFERENCES cms.categorias(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    slug TEXT NOT NULL,
    posicao SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (categoria_id, slug)
);

-- Artigos da base de conhecimento
CREATE TABLE cms.artigos (
    id SERIAL PRIMARY KEY,
    secao_id INT NOT NULL REFERENCES cms.setores(id) ON DELETE SET NULL,
    autor_id UUID NOT NULL REFERENCES auth.users(id),
    titulo TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    conteudo TEXT NOT NULL, -- html ou markdown
    status cms.artigo_status NOT NULL DEFAULT 'rascunho',
    agendado_para TIMESTAMPTZ,
    publicado_em TIMESTAMPTZ, -- NULL significa não publicado ainda
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_vector TSVECTOR
);

CREATE TABLE cms.revisoes_de_artigos (
    id SERIAL PRIMARY KEY,
    artigo_id INT NOT NULL REFERENCES cms.artigos(id) ON DELETE CASCADE,
    editor_id UUID NOT NULL REFERENCES auth.users(id),
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);