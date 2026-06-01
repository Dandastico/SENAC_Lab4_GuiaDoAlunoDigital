# Guia do Aluno Digital – Facilitando a Vida do Aluno

### Especificação e Protótipos
Grupo: Churros Mágico

**Integrantes**

- Daniel Ferreira - dandastico.bsb@gmail.com
- Filipe Peres - filipe98.peres@gmail.com
- Gabriel Republicano - 
- Gabriel Oliveira - 

**Prof. Orientador**

Prof. João Gabriel Alvares

[Repositório Online](https://github.com/Dandastico/SENAC_Lab4_GuiaDoAlunoDigital/tree/main)

## 1. INTRODUÇÃO

O presente documento constitui o Plano de Projeto para o desenvolvimento do Guia Estudantil Digital da Faculdade de Tecnologia e Inovação SENAC-DF. O objetivo primordial do projeto é aprimorar a experiência do estudante da faculdade, disponibilizando informações de interesse dos alunos e funcionalidades úteis como Calculadora de Média e Acompanhamento de Presença.

O Guia do Aluno Digital do FACSENAC-DF se propõe a ser um **Centro de Ajuda**, como o [Centro de Ajuda do Brevo](https://help.brevo.com/hc/pt), [Centro de Ajuda da Meta](https://www.meta.com/pt-br/help/) ou [Documentação do Mozilla](https://developer.mozilla.org/pt-BR/). Visa organizar artigos que explicam com detalhes as regras da Faculdade e informa dados de relevância para a experiência do aluno. Integrado ao sistema, caso o usuário deseje se autenticar, terá acesso a funcionalidades para melhor gerenciar a vida acadêmica.

Os diferenciais estratégicos do Guia Estudantil é a maior facilidade de atualizar as informações no sistema e o maior acesso à informação para todos os alunos e corpo discente do FACSENAC-DF.

Este Plano de Projeto detalha o escopo, os objetivos de alto nível, requisitos funcionais, estrutura de trabalho e o cronograma proposto para a entrega da primeira versão funcional do Guia Estudantil Digital.

## 2. DESCRIÇÃO DO PROJETO

### 2.1 Título do Projeto

Guia Estudantil Digital FACSENAC-DF

### 2,2 Objetivos de Alto Nível

- **PARA** alunos e professores do FACSENAC-DF
- **QUE** necessitam de uma forma mais rápida e com maior disponibilidade de acessar informações relevantes para sua vida acadêmica no FACSENAC-DF
- **DIFERENTEMENTE DO** guia impresso ou do PDF disposto pela Faculdade de Tecnologia e Inovação SENAC-DF, que é de difícil atualização, com informações ultrapassadas e difícil acesso
- **NOSSO PRODUTO** oferece espaço de manutenção, criação e gerenciamento de Artigos de Base de Conhecimento. Também há serviços como Calculadora de Média e Espaço de Gerenciamento de Frequência
- **QUANDO precisa estar pronto?** A conclusão do projeto é no dia **[TODO]**
- **QUANTO é a previsão de custo?** Investimento inicial estimado em **[TODO]**

### ESCOPO DO PROJETO

Funcionalidades principais:

- Base de Conhecimento (Artigos): Espaço para criar, manter e gerenciar artigos explicando regras da faculdade e informações relevantes para os alunos, sem necessidade de autenticação para a leitura.
- Calculadora de Média: Ferramenta para o aluno o aluno calcular suas médias acadêmicas.
- Acompanhamento de Presença (Frequência): Espaço para o aluno gerenciar e acompanhar sua frequência nas disciplinas matriculadas.
- Autenticação de Usuário: Login opcional que, quando feito, desbloqueia as funcionalidades personalizadas

Limitações:

- Público-alvo Inicial: Versão 1.0 focada nos alunos do curso de Análise e Desenvolvimento de Sistemas do FACSENAC-DF
- Conteúdo: Artigos da Base de Conhecimento limitados às regras e informações do FACSENAC-DF, sem considerar as outras unidades do SENAC
- Funcionalidades Personalizadas: Calculadora de Média e Acompanhamento de Presença disponíveis apenas para usuários autenticados
- Cálculo de Mèdia: Cálculo automático sem sem integração direta com o sistema acadêmico da faculdade (sem conexão com APIs oficiais ou outros métodos de importação de notas)
- Presença: Gerenciamento manual pelo aluno, sem sincronização com registros oficiais de frequência da instituição

### 3.1 Escopo do Produto (Requisitos Funcionais)

- RF01 - Manter Cadastro de Usuário
    - RF01.1 - Consultar Usuário
    - RF01.2 - Cadastrar Usuário
    - RF01.3 - Validar E-mail
        - Gerar link de validação, enviar por e-mail
    - RF01.4 - Editar Usuário

- RF02 - Gerenciar Login do Usuário
    - RF02.1 - Validar Credencial
    - RF02.2 - Redefinir Senha

- RF03 - Gerenciar Artigos da Base de Conhecimento
    - RF03.1 - Criar Artigos
    - RF03.2 - Editar Artigo
    - RF03.3 - Excluir Artigo
    - RF03.4 - Publicar/Ocultar Artigo
    - RF03.5 - Programar Publicação
    - RF03.6 - Associar Artigos à Seções ou Categorias

- RF04 - Gerenciar Disciplinas Matriculadas
    - RF04.1 - Cadastrar Disciplina
    - RF04.2 - Editar Disciplina
    - RF04.3 - Excluir Disciplina
    - RF04.4 - Deifinir Total de Aulas da Disciplina

- RF05 - Gerenciar Calculadora de Média
    - RF05.1 - Inserir Notas da Disciplina com seus pesos
    - RF05.2 - Calcular Média da Disciplina
    - RF05.3 - Exibir Situação do Aluno na Disciplina (Em curso/Aprovado/Recuperação/Reprovado)

- RF06 - Gerenciar Acompanhamento de Presença
    - RF06.1 - Registrar Presença ou Falta em Aula
    - RF06.2 - Calcular Percentual de Frequência
    - RF06.3 - Exibir Situação de Frequência do Aluno (Aprovado/Reprovado/Em risco)

## ESPECIFICAÇÃO DOS REQUISITOS

