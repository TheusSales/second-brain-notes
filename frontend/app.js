/**
 * Second Brain Notes — Frontend Application
 *
 * Gerencia o fluxo: entrada → gerar preview → salvar/descartar.
 * Comunica com o backend via fetch para os endpoints /notes/generate e /notes/save.
 */

const API_BASE = window.location.origin;

// ---------------------------------------------------------------------------
// Elementos do DOM
// ---------------------------------------------------------------------------
const inputSection = document.getElementById("input-section");
const loadingSection = document.getElementById("loading-section");
const previewSection = document.getElementById("preview-section");
const successSection = document.getElementById("success-section");

const providerSelect = document.getElementById("provider-select");
const urlInput = document.getElementById("url-input");
const textInput = document.getElementById("text-input");
const generateBtn = document.getElementById("generate-btn");
const errorMsg = document.getElementById("error-msg");

const previewTitulo = document.getElementById("preview-titulo");
const previewResumo = document.getElementById("preview-resumo");
const previewTags = document.getElementById("preview-tags");
const previewFlashcards = document.getElementById("preview-flashcards");
const previewMarkdown = document.getElementById("preview-markdown");
const connectionsSection = document.getElementById("connections-section");
const previewConnections = document.getElementById("preview-connections");
const saveBtn = document.getElementById("save-btn");
const exportAnkiBtn = document.getElementById("export-anki-btn");
const discardBtn = document.getElementById("discard-btn");

const savedPath = document.getElementById("saved-path");
const exportAnkiSuccessBtn = document.getElementById("export-anki-success-btn");
const newNoteBtn = document.getElementById("new-note-btn");

// Estado da nota gerada (para enviar ao /notes/save)
let generatedNoteData = null;

// ---------------------------------------------------------------------------
// Carregar provedores disponíveis
// ---------------------------------------------------------------------------

const PROVIDER_LABELS = {
  groq: "Groq (Llama 3.3 70B)",
  openai: "OpenAI (GPT-4o mini)",
  anthropic: "Anthropic (Claude Sonnet)",
  gemini: "Google Gemini (2.0 Flash)",
};

(async function loadProviders() {
  try {
    const res = await fetch(`${API_BASE}/providers`);
    const data = await res.json();
    providerSelect.innerHTML = data.available
      .map(
        (p) =>
          `<option value="${p}" ${p === data.active ? "selected" : ""}>${PROVIDER_LABELS[p] || p}</option>`
      )
      .join("");
  } catch {
    providerSelect.innerHTML = '<option value="">Erro ao carregar</option>';
  }
})();

// ---------------------------------------------------------------------------
// Navegação entre seções
// ---------------------------------------------------------------------------

/**
 * Mostra apenas a seção indicada, escondendo as demais.
 *
 * @param {HTMLElement} section - A seção a ser exibida.
 */
function showSection(section) {
  [inputSection, loadingSection, previewSection, successSection].forEach(
    (s) => s.classList.add("hidden")
  );
  section.classList.remove("hidden");
}

/**
 * Exibe mensagem de erro abaixo do formulário.
 *
 * @param {string} message - Texto do erro a ser exibido.
 */
function showError(message) {
  errorMsg.textContent = message;
  errorMsg.classList.remove("hidden");
}

/** Esconde a mensagem de erro. */
function hideError() {
  errorMsg.classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Gerar preview
// ---------------------------------------------------------------------------

generateBtn.addEventListener("click", async () => {
  hideError();

  const url = urlInput.value.trim();
  const text = textInput.value.trim();

  if (!url && !text) {
    showError("Informe uma URL ou cole um texto.");
    return;
  }

  const body = {};
  if (url) body.url = url;
  if (text) body.text = text;
  body.provider = providerSelect.value;

  showSection(loadingSection);

  try {
    const response = await fetch(`${API_BASE}/notes/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Erro HTTP ${response.status}`);
    }

    const note = await response.json();
    generatedNoteData = note;
    renderPreview(note);
    showSection(previewSection);
  } catch (err) {
    showSection(inputSection);
    showError(err.message || "Erro ao gerar nota. Tente novamente.");
  }
});

/**
 * Preenche a seção de preview com os dados da nota gerada.
 *
 * @param {Object} note - Dados da nota retornados pelo endpoint /notes/generate.
 */
function renderPreview(note) {
  previewTitulo.textContent = note.titulo;
  previewResumo.textContent = note.resumo;

  // Tags
  previewTags.innerHTML = note.tags
    .map((tag) => `<span class="tag">${tag}</span>`)
    .join("");

  // Flashcards
  previewFlashcards.innerHTML = note.flashcards
    .map(
      (fc) =>
        `<li>
          <div class="question">Q: ${fc.question}</div>
          <div class="answer">A: ${fc.answer}</div>
        </li>`
    )
    .join("");

  // Conexões
  if (note.connections && note.connections.length > 0) {
    previewConnections.innerHTML = note.connections
      .map((c) => `<span class="tag connection">[[${c}]]</span>`)
      .join("");
    connectionsSection.classList.remove("hidden");
  } else {
    connectionsSection.classList.add("hidden");
  }

  // Markdown completo
  previewMarkdown.textContent = note.markdown_content;
}

// ---------------------------------------------------------------------------
// Salvar nota
// ---------------------------------------------------------------------------

saveBtn.addEventListener("click", async () => {
  if (!generatedNoteData) return;

  saveBtn.disabled = true;
  saveBtn.textContent = "Salvando...";

  try {
    const response = await fetch(`${API_BASE}/notes/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        titulo: generatedNoteData.titulo,
        resumo: generatedNoteData.resumo,
        flashcards: generatedNoteData.flashcards,
        tags: generatedNoteData.tags,
        fonte: generatedNoteData.fonte,
        date: generatedNoteData.date,
        body: generatedNoteData.body,
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Erro HTTP ${response.status}`);
    }

    const result = await response.json();
    savedPath.textContent = result.file_path;
    showSection(successSection);
  } catch (err) {
    showError(err.message || "Erro ao salvar nota.");
    showSection(previewSection);
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = "Salvar no Obsidian";
  }
});

// ---------------------------------------------------------------------------
// Exportar para Anki
// ---------------------------------------------------------------------------

/**
 * Executa a exportação dos flashcards para Anki via download de arquivo.
 *
 * @param {HTMLButtonElement} btn - Botão que disparou a ação (para feedback visual).
 */
async function handleAnkiExport(btn) {
  if (!generatedNoteData) return;

  btn.disabled = true;
  btn.textContent = "Exportando...";

  try {
    const response = await fetch(`${API_BASE}/notes/export-anki`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        flashcards: generatedNoteData.flashcards,
        deck: generatedNoteData.titulo,
        tags: generatedNoteData.tags,
      }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Erro HTTP ${response.status}`);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;

    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?(.+?)"?$/);
    a.download = match ? match[1] : "anki-export.txt";

    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    showError(err.message || "Erro ao exportar para Anki.");
  } finally {
    btn.disabled = false;
    btn.textContent = "Exportar para Anki";
  }
}

exportAnkiBtn.addEventListener("click", () => handleAnkiExport(exportAnkiBtn));
exportAnkiSuccessBtn.addEventListener("click", () => handleAnkiExport(exportAnkiSuccessBtn));

// ---------------------------------------------------------------------------
// Descartar / Nova nota
// ---------------------------------------------------------------------------

discardBtn.addEventListener("click", () => {
  generatedNoteData = null;
  showSection(inputSection);
});

newNoteBtn.addEventListener("click", () => {
  generatedNoteData = null;
  urlInput.value = "";
  textInput.value = "";
  hideError();
  showSection(inputSection);
});
