-- -----------------------------------------------------------------------
-- FUNÇÕES E OUTRAS COISAS
-- -----------------------------------------------------------------------

-- Função genérica que inviabiliza coluna atualizado_em (schema:public)
CREATE OR REPLACE FUNCTION set_atualizado_em()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.atualizado_em = now();
    RETURN NEW;
END;
$$;

-- Função que inviabliza coluna search_vector
CREATE OR REPLACE FUNCTION cms.atualizar_search_vector()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.search_vector =
        setweight(to_tsvector('portuguese', coalesce(NEW.titulo, '')), 'A') ||
        setweight(to_tsvector('portuguese', coalesce(NEW.conteudo, '')), 'B');
    RETURN NEW;
END;
$$;

