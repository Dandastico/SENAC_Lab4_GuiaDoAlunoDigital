-- ===========================================
-- SCHEMA PUBLIC
-- ===========================================

-- ENUM para possíveis funções do usuário
CREATE TYPE public.perfil_funcao AS ENUM (
    'estudante',    
    'professor',    
    'admin'    -- consegue realizar todo o CRUD da base de conhecimento
);

CREATE TABLE public.perfis (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nome_inteiro TEXT,
    funcao public.perfil_funcao NOT NULL DEFAULT 'estudante',
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);

-- ===========================================
-- CRIAR TRIGGERS
-- ===========================================

-- Trigger que acionar coluna atualizado_em na tabela perfis
CREATE TRIGGER trg_perfis_atualizado_em
    BEFORE UPDATE ON public.perfis
    FOR EACH ROW
    EXECUTE FUNCTION set_atualizado_em();

-- Trigger que insere dados para cada novo usuário criadopelo auth
CREATE TRIGGER trg_criar_perfil_apos_registro
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.criar_perfil_novo_usuario();