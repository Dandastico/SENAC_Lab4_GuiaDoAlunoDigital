-- ===========================================
-- SCHEMA PUBLIC
-- ===========================================

-- ENUM para possíveis funções do usuário
CREATE TYPE public.perfil_funcao AS ENUM (
    'estudante',    
    'professor',    
    'admin',    -- consegue realizar todo o CRUD da base de conhecimento
);

CREATE TABLE public.perfis (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE;
    nome_inteiro TEXT,
    funcao public.perfil_funcao NOT NULL DEFAULT 'estudante',
    criado_em timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now()
);