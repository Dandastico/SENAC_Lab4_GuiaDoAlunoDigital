-- ===========================================
-- BANCO DE DADOS DA BASE DE CONHECIMENTO
-- ===========================================

CREATE SCHEMA IF NOT EXISTS cms;

-- ENUM para os possíveis estados de um artigo
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
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seções são segmentações que habitam dentro das categorias
CREATE TABLE cms.setores (
    id SERIAL PRIMARY KEY,
    categoria_id INT NOT NULL REFERENCES cms.categorias(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    slug TEXT NOT NULL,
    posicao SMALLINT NOT NULL DEFAULT 0,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (categoria_id, slug)
);

-- Artigos da base de conhecimento
CREATE TABLE cms.artigos (
    id SERIAL PRIMARY KEY,
    secao_id INT REFERENCES cms.setores(id) ON DELETE RESTRICT,
    autor_id UUID REFERENCES auth.users(id),
    titulo TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    conteudo TEXT NOT NULL, -- html ou markdown
    status cms.artigo_status NOT NULL DEFAULT 'rascunho',
    agendado_para TIMESTAMPTZ,
    publicado_em TIMESTAMPTZ, -- NULL significa não publicado ainda
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    search_vector TSVECTOR,
    
    CONSTRAINT artigo_publicado_exige_secao
        CHECK (status NOT IN ('publicado', 'agendado') OR secao_id IS NOT NULL) ,
    CONSTRAINT agendado_exige_data
        CHECK (status != 'agendado' OR agendado_para IS NOT NULL)
);

-- Histórico de edições (útil para auditoria de conteúdo)
CREATE TABLE cms.revisoes_de_artigos (
    id SERIAL PRIMARY KEY,
    artigo_id INT NOT NULL REFERENCES cms.artigos(id) ON DELETE CASCADE,
    editor_id UUID NOT NULL REFERENCES auth.users(id),
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    editado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Busca de artigos é a query mais frequente
CREATE INDEX idx_artigos_status ON cms.artigos(status);
CREATE INDEX idx_artigos_secao_id ON cms.artigos(secao_id);
CREATE INDEX idx_artigos_slug ON cms.artigos(slug);

-- Publicação agendada
CREATE INDEX idx_artigos_agendados ON cms.artigos(agendado_para)
    WHERE status = 'agendado' AND agendado_para IS NOT NULL;

-- Index faz busca full-text ser mais performática
CREATE INDEX idx_artigos_search_vector ON cms.artigos USING GIN(search_vector);

-- ===========================================
-- RLS BÁSICO
-- ===========================================
ALTER TABLE cms.artigos ENABLE ROW LEVEL SECURITY;

-- Qualquer pessoa pode ler artigos publicados
CREATE POLICY "Artigos publicados são públicos"
    ON cms.artigos FOR SELECT
    USING (status = 'publicado');

-- Somente admins podem criar, editar e excluir
CREATE POLICY "Somente admins gerenciam artigos"
    ON cms.artigos FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM public.perfis
            WHERE id = auth.uid() AND funcao = 'admin'
        )
    );

-- ===========================================
-- CRIAR TRIGGERS
-- ===========================================

CREATE TRIGGER trg_artigos_atualizado_em
    BEFORE UPDATE ON cms.artigos
    FOR EACH ROW
    EXECUTE FUNCTION set_atualizado_em();

CREATE TRIGGER trg_artigos_search_vector
    BEFORE INSERT OR UPDATE ON cms.artigos
    FOR EACH ROW
    EXECUTE FUNCTION cms.atualizar_search_vector();