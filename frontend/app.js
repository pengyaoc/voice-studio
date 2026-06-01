let history = [];
let currentTab = "custom-voice";
let currentModelSize = "0.6B";
let availableModelSizes = {};
const activeGenerations = new Set();

function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[char]));
}

function buildHistoryMeta(item) {
    const text = item.text || "Recovered generation";
    const snippet = item.snippet || (text.length > 40 ? text.substring(0, 40) + "..." : text);
    let label = item.label || item.mode.replace("_", " ");
    if (item.speaker) label = item.speaker;
    if (item.mode === "voice_clone") label = "Cloned voice";
    if (item.mode === "voice_design") label = "Designed voice";
    if (item.mode === "recovered") label = item.label || "Recovered clip";
    return { ...item, text, snippet, label };
}

function renderHistory() {
    const list = document.getElementById("history-list");
    if (!history.length) {
        list.innerHTML = `<p class="text-sm text-gray-600">No generations yet</p>`;
        return;
    }

    list.innerHTML = history
        .map((item) => {
            const meta = `${item.label} · ${item.language} · ${item.model_size || "1.7B"} · ${item.duration}s`;
            return `
        <div class="history-item" onclick="showAudio('${item.filename}')">
            <div>
                <div class="text-white text-sm">"${escapeHtml(item.snippet)}"</div>
                <div class="text-gray-500 text-xs">${escapeHtml(meta)}</div>
            </div>
            <div class="text-accent text-sm">▶</div>
        </div>
    `;
        })
        .join("");
}

// --- Model Size Toggle ---
document.querySelectorAll(".model-size-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        const size = btn.dataset.size;
        const variant = currentTab.replace("-", "_");
        if (availableModelSizes[variant] && !availableModelSizes[variant].includes(size)) {
            return;
        }
        document.querySelectorAll(".model-size-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentModelSize = size;
    });
});

function updateModelSizeButtons() {
    const variant = currentTab.replace("-", "_");
    const sizes = availableModelSizes[variant] || ["1.7B"];
    document.querySelectorAll(".model-size-btn").forEach((btn) => {
        const available = sizes.includes(btn.dataset.size);
        btn.disabled = !available;
        btn.classList.toggle("opacity-30", !available);
        btn.classList.toggle("cursor-not-allowed", !available);
    });
    if (!sizes.includes(currentModelSize)) {
        currentModelSize = sizes[sizes.length - 1];
        document.querySelectorAll(".model-size-btn").forEach((b) => b.classList.remove("active"));
        document.querySelector(`.model-size-btn[data-size="${currentModelSize}"]`)?.classList.add("active");
    }
}

// --- Tab Switching ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");

        currentTab = btn.dataset.tab;
        document.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));
        document.getElementById(`tab-${currentTab}`).classList.remove("hidden");
        updateModelSizeButtons();
    });
});

// --- Load Voices & Languages ---
async function loadVoices() {
    try {
        const res = await fetch("/api/voices");
        const data = await res.json();

        const speakerSelect = document.getElementById("cv-speaker");
        speakerSelect.innerHTML = data.speakers
            .map((s) => `<option value="${s.id}">${s.name} — ${s.description} (${s.language})</option>`)
            .join("");

        const languageSelects = ["cv-language", "vc-language", "vd-language"];
        languageSelects.forEach((id) => {
            const sel = document.getElementById(id);
            sel.innerHTML = data.languages
                .map((l) => `<option value="${l}">${l}</option>`)
                .join("");
        });

        if (data.model_sizes) {
            availableModelSizes = data.model_sizes;
            updateModelSizeButtons();
        }
        updateCloneModeHelp();
    } catch (e) {
        console.error("Failed to load voices:", e);
    }
}

async function loadHistory() {
    try {
        const res = await fetch("/api/history");
        const data = await res.json();
        history = (data.items || []).map(buildHistoryMeta);
        renderHistory();
    } catch (e) {
        console.error("Failed to load history:", e);
    }
}

// --- File Upload (Voice Clone) ---
const dropzone = document.getElementById("vc-dropzone");
const fileInput = document.getElementById("vc-file");
const fileInfo = document.getElementById("vc-file-info");
const savedClipsSelect = document.getElementById("vc-saved-clips");
const refTextInput = document.getElementById("vc-ref-text");
const refHelp = document.getElementById("vc-ref-help");
let availableReferenceClips = [];

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
        fileInput.files = e.dataTransfer.files;
        savedClipsSelect.value = "";
        showFileInfo(e.dataTransfer.files[0]);
        persistClonePreferences();
    }
});
fileInput.addEventListener("change", () => {
    if (fileInput.files.length) {
        savedClipsSelect.value = "";
        showFileInfo(fileInput.files[0]);
        persistClonePreferences();
    }
});
savedClipsSelect.addEventListener("change", () => {
    if (savedClipsSelect.value) {
        fileInput.value = "";
        showSavedClipInfo(savedClipsSelect.value);
    } else if (!fileInput.files.length) {
        fileInfo.classList.add("hidden");
    }
    persistClonePreferences();
});
refTextInput.addEventListener("input", persistClonePreferences);

function showFileInfo(file) {
    fileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    fileInfo.classList.remove("hidden");
}

function showSavedClipInfo(filename) {
    const clip = availableReferenceClips.find((item) => item.filename === filename);
    if (clip) {
        fileInfo.textContent = `Selected saved clip: ${clip.filename} (${(clip.size / 1024).toFixed(1)} KB)`;
    } else {
        fileInfo.textContent = `Selected saved clip: ${filename}`;
    }
    fileInfo.classList.remove("hidden");
}

function getClonePreferences() {
    return {
        ref_text: refTextInput.value,
        reference_clip: fileInput.files[0] ? fileInput.files[0].name : savedClipsSelect.value,
    };
}

async function persistClonePreferences() {
    const prefs = getClonePreferences();
    try {
        await fetch("/api/voice-clone/preferences", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(prefs),
        });
    } catch (e) {
        console.error("Failed to persist clone preferences:", e);
    }
}

async function restoreClonePreferences() {
    try {
        const res = await fetch("/api/voice-clone/preferences");
        const prefs = await res.json();
        refTextInput.value = prefs.ref_text || "";
        updateCloneModeHelp();
        return prefs;
    } catch (e) {
        console.error("Failed to restore clone preferences:", e);
        updateCloneModeHelp();
        return {};
    }
}

function renderSavedClips(items, prefs = {}) {
    availableReferenceClips = items;
    savedClipsSelect.innerHTML = `
        <option value="">Choose a saved clip...</option>
        ${items.map((clip) => `<option value="${clip.filename}">${clip.filename}</option>`).join("")}
    `;

    if (prefs.reference_clip && items.some((clip) => clip.filename === prefs.reference_clip)) {
        savedClipsSelect.value = prefs.reference_clip;
        if (!fileInput.files.length) {
            showSavedClipInfo(prefs.reference_clip);
        }
    }
}

async function loadReferenceClips(prefs = {}) {
    try {
        const res = await fetch("/api/reference-clips");
        const data = await res.json();
        renderSavedClips(data.items || [], prefs);
    } catch (e) {
        console.error("Failed to load reference clips:", e);
    }
}

function updateCloneModeHelp() {
    refHelp.textContent = "Must match the reference audio exactly for best results.";
}

// --- Status Banner ---
function showStatus(message, type = "loading") {
    const banner = document.getElementById("status-banner");
    banner.textContent = message;
    banner.className = `mb-4 p-4 rounded-lg text-sm status-${type}`;
    banner.classList.remove("hidden");
}

function hideStatus() {
    document.getElementById("status-banner").classList.add("hidden");
}

// --- Model Loading Poll ---
async function pollModelStatus(variant, modelSize) {
    while (true) {
        const res = await fetch(`/api/model-status?variant=${variant}&model_size=${modelSize}`);
        const data = await res.json();

        if (data.status === "ready") {
            hideStatus();
            return true;
        }
        if (data.status === "error") {
            showStatus(data.message, "error");
            return false;
        }
        showStatus(data.message, "loading");
        await new Promise((r) => setTimeout(r, 2000));
    }
}

// --- Set Button State ---
function setGenerating(tabId, generating) {
    const btn = document.querySelector(`#tab-${tabId} .generate-btn`);
    if (generating) {
        btn.disabled = true;
        btn.textContent = "Generating...";
    } else {
        btn.disabled = false;
        btn.textContent = "Generate Speech";
    }
}

// --- Handle Generation Response ---
async function handleResponse(res, tabId, variant, meta) {
    const data = await res.json();

    if (data.status === "loading") {
        showStatus(data.message, "loading");
        const ready = await pollModelStatus(variant, meta.modelSize);
        if (!ready) {
            return "error";
        }
        return "retry";
    }

    if (data.status === "done") {
        hideStatus();
        showAudio(data.filename);
        addHistory({ ...data, text: data.text || meta.text });
        if (typeof meta.afterSuccess === "function") {
            await meta.afterSuccess(data);
        }
        return "done";
    }

    if (data.status === "error") {
        showStatus(data.message, "error");
        return "error";
    }

    showStatus("Unexpected server response.", "error");
    return "error";
}

async function submitGeneration(tabId, endpoint, variant, buildForm, meta) {
    if (activeGenerations.has(tabId)) {
        return;
    }

    activeGenerations.add(tabId);
    setGenerating(tabId, true);

    try {
        while (true) {
            const res = await fetch(endpoint, { method: "POST", body: buildForm() });
            const action = await handleResponse(res, tabId, variant, meta);
            if (action !== "retry") {
                break;
            }
        }
    } catch (e) {
        console.error(`Failed to generate for ${tabId}:`, e);
        showStatus("Generation failed. Check the server logs and try again.", "error");
    } finally {
        activeGenerations.delete(tabId);
        setGenerating(tabId, false);
    }
}

// --- Generate: Custom Voice ---
async function generateCustomVoice() {
    const text = document.getElementById("cv-text").value.trim();
    if (!text) return;
    const modelSize = currentModelSize;

    await submitGeneration(
        "custom-voice",
        "/api/tts/custom-voice",
        "custom_voice",
        () => {
            const form = new FormData();
            form.append("text", text);
            form.append("language", document.getElementById("cv-language").value);
            form.append("speaker", document.getElementById("cv-speaker").value);
            form.append("instruct", document.getElementById("cv-instruct").value);
            form.append("model_size", modelSize);
            return form;
        },
        { text, modelSize },
    );
}

// --- Generate: Voice Clone ---
async function generateVoiceClone() {
    const text = document.getElementById("vc-text").value.trim();
    const refText = refTextInput.value.trim();
    const file = document.getElementById("vc-file").files[0];
    const savedClip = savedClipsSelect.value;
    const modelSize = currentModelSize;
    if (!text || (!file && !savedClip) || !refText) {
        showStatus("Please upload a reference audio clip and provide the required fields.", "error");
        return;
    }

    persistClonePreferences();

    await submitGeneration(
        "voice-clone",
        "/api/tts/voice-clone",
        "voice_clone",
        () => {
            const form = new FormData();
            form.append("text", text);
            form.append("language", document.getElementById("vc-language").value);
            form.append("ref_text", refText);
            if (file) {
                form.append("ref_audio", file);
            } else if (savedClip) {
                form.append("reference_clip", savedClip);
            }
            form.append("model_size", modelSize);
            return form;
        },
        {
            text,
            modelSize,
            afterSuccess: async () => {
                await loadReferenceClips();
                persistClonePreferences();
            },
        },
    );
}

// --- Generate: Voice Design ---
async function generateVoiceDesign() {
    const text = document.getElementById("vd-text").value.trim();
    const instruct = document.getElementById("vd-instruct").value.trim();
    if (!text || !instruct) {
        showStatus("Please fill in both voice description and text.", "error");
        return;
    }
    const modelSize = currentModelSize;

    await submitGeneration(
        "voice-design",
        "/api/tts/voice-design",
        "voice_design",
        () => {
            const form = new FormData();
            form.append("text", text);
            form.append("language", document.getElementById("vd-language").value);
            form.append("instruct", instruct);
            return form;
        },
        { text, modelSize },
    );
}

// --- Audio Player ---
function showAudio(filename) {
    const player = document.getElementById("audio-player");
    const audio = document.getElementById("audio-element");
    const downloadBtn = document.getElementById("download-btn");

    const url = `/audio/${filename}`;
    audio.src = url;
    downloadBtn.href = url;
    downloadBtn.download = filename;

    player.classList.remove("hidden");
    audio.play();
}

// --- History ---
function addHistory(item) {
    history = [buildHistoryMeta(item), ...history.filter((entry) => entry.filename !== item.filename)];
    renderHistory();
}

// --- Init ---
loadVoices();
loadHistory();
restoreClonePreferences();
loadReferenceClips();
updateCloneModeHelp();
