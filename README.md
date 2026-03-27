# Second Brain Notes

Ferramenta para capturar conhecimento e salvar notas padronizadas no Obsidian, usando IA para gerar resumos, flashcards e tags automaticamente a partir de texto livre ou URLs.

**Provedor atual:** [Groq](https://console.groq.com) (gratuito) com modelo `llama-3.3-70b-versatile`.

## Arquitetura

```
Entrada (texto ou URL)
        ↓
Backend FastAPI (Python)
        ↓
Groq API (llama-3.3-70b-versatile)
  → Gera: título, resumo, flashcards, tags, corpo
        ↓
Arquivo .md salvo em ~/Documents/Obsidian/Vault/Inbox/
```

## Roadmap

### Fases concluídas

| Fase | Descrição |
|------|-----------|
| 0 | Backend FastAPI + Groq (Llama 3.3 70B) + testes TDD |
| 1 | Validação end-to-end (bug fixes, server funcional) |
| 2 | Frontend web com pré-visualização (HTML/CSS/JS vanilla) |
| 3 | Sugestão de links — conexões com notas existentes no vault |

### Próximas fases

| Fase | Descrição | Status |
|------|-----------|--------|
| 4 | **Exportação para Anki** — gerar arquivo compatível com importação do Anki (CSV/TSV ou `.xlsx`) a partir dos flashcards gerados | Planejado |
| 5 | Bot Telegram | Planejado |
| 6 | AI Wrapper multi-provider | Planejado |
| 7 | Melhorias (auth, rate limit, logs, suporte a PDF) | Planejado |

### Fase 4 — Exportação para Anki (detalhes)

Os flashcards já são gerados automaticamente pela IA. Esta fase adicionará:
- **Endpoint `POST /notes/export-anki`** — recebe os flashcards de uma nota e retorna um arquivo para download
- **Formato de saída:** CSV/TSV com colunas `Front;Back` (separador configurável), compatível com o importador nativo do Anki. Opcionalmente `.xlsx` para quem preferir abrir no Excel antes de importar
- **Botão "Exportar para Anki"** no frontend, disponível na tela de preview após gerar a nota
- **Configuração de deck e tags** — permitir ao usuário definir o nome do deck e tags Anki no momento da exportação
- Testes TDD cobrindo geração do arquivo, encoding UTF-8, e formato compatível

### AI Wrapper multi-provider (futuro)

O projeto evoluirá para uma arquitetura de **AI wrapper** que permitirá ao usuário:
- Selecionar o provedor de IA preferido (Groq, Google Gemini, OpenAI, Anthropic, etc.)
- Configurar sua própria API key por provedor
- Trocar de provedor sem alterar o restante do sistema

Quando implementado, a variável `AI_PROVIDER` no `.env` controlará qual provedor é usado, e cada provedor terá sua própria chave configurável. Consulte `.env.example` para ver as variáveis planejadas.

## Estrutura do projeto

```
second-brain-notes/
├── backend/
│   ├── main.py              # FastAPI app — endpoints HTTP
│   ├── note_generator.py    # Integração com IA + fetch de URLs
│   ├── obsidian_writer.py   # Geração de arquivo .md e escrita no vault
│   ├── vault_reader.py      # Leitura de notas existentes para sugestão de links
│   ├── config.py            # Configurações via variáveis de ambiente
│   ├── requirements.txt     # Dependências Python
│   └── tests/               # Suite de testes (TDD) — 62 testes
│       ├── test_config.py
│       ├── test_obsidian_writer.py
│       ├── test_note_generator.py
│       ├── test_vault_reader.py
│       └── test_main.py
├── frontend/
│   ├── index.html           # Interface web — dark theme
│   ├── style.css            # Estilos
│   └── app.js               # Lógica de preview e salvamento
├── templates/
│   └── note_template.md     # Exemplo de nota gerada
├── .env.example             # Variáveis de ambiente necessárias
└── README.md
```

## Requisitos

- Python 3.10+
- Conta no [Groq](https://console.groq.com) (gratuito) com chave de API

## Instalação

```bash
# 1. Clonar o repositório
git clone <url-do-repo>
cd second-brain-notes

# 2. Criar e ativar ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependências
pip install -r backend/requirements.txt

# 4. Configurar variáveis de ambiente
cp .env.example .env
# Edite .env e adicione sua GROQ_API_KEY
```

## Configuração

Edite o arquivo `.env` na raiz do projeto:

```env
GROQ_API_KEY=gsk_...                     # obrigatória — obtenha em console.groq.com
OBSIDIAN_VAULT_PATH=/seu/caminho/Inbox   # opcional, tem valor padrão
```

O valor padrão de `OBSIDIAN_VAULT_PATH` é `~/Documents/Obsidian/Vault/Inbox`.

## Rodando o servidor

```bash
uvicorn backend.main:app --reload --port 8000
```

O servidor ficará disponível em `http://localhost:8000`.

A documentação interativa (Swagger UI) estará em `http://localhost:8000/docs`.

## Endpoints

### `POST /notes` — Criar nota

Recebe texto livre ou URL e retorna a nota gerada + caminho do arquivo salvo.

**Request body:**
```json
{ "text": "Conteúdo em texto livre" }
```
ou
```json
{ "url": "https://exemplo.com/artigo" }
```

**Response (201 Created):**
```json
{
  "titulo": "Título gerado pela IA",
  "resumo": "Resumo de 2-4 frases.",
  "tags": ["python", "api"],
  "flashcards": [
    {"question": "Pergunta?", "answer": "Resposta."}
  ],
  "fonte": "https://exemplo.com/artigo",
  "date": "2026-03-26",
  "file_path": "/home/user/Documents/Obsidian/Vault/Inbox/2026-03-26-titulo.md",
  "markdown_content": "---\ntitulo: ...\n---\n\n# Título\n..."
}
```

**Erros:**
- `422` — Nem `text` nem `url` fornecidos, ou URL inacessível
- `502` — Falha na API do provedor de IA

### `GET /health` — Verificar saúde

```json
{
  "status": "ok",
  "vault_path": "/home/user/Documents/Obsidian/Vault/Inbox"
}
```

## Rodando os testes

```bash
cd /caminho/para/second-brain-notes
.venv/bin/pytest backend/tests/ -v
```

**Cobertura:**

| Arquivo | O que testa |
|---|---|
| `test_config.py` | Carregamento de settings, validação de campos obrigatórios |
| `test_obsidian_writer.py` | Slug de títulos, YAML frontmatter, deduplicação de arquivos |
| `test_note_generator.py` | Modelos Pydantic, parsing JSON do LLM, strip de fences |
| `test_main.py` | Endpoints HTTP completos com mocks |

## Formato da nota gerada

```markdown
---
titulo: "Título da Nota"
resumo: "Resumo conciso de 2-4 frases."
tags:
  - tag1
  - tag2
flashcards:
  - q: "Pergunta para revisão?"
    a: "Resposta objetiva."
fonte: "https://fonte.com"
date: 2026-03-26
---

# Título da Nota

## Conceitos Principais
...
```

O arquivo é salvo com o nome no formato `YYYY-MM-DD-titulo-slugificado.md`.
