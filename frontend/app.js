let history = [];
let currentTab = "custom-voice";

// --- Tab Switching ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");

        currentTab = btn.dataset.tab;
        document.querySelectorAll(".tab-content").forEach((c) => c.classList.add("hidden"));
        document.getElementById(`tab-${currentTab}`).classList.remove("hidden");
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
    } catch (e) {
        console.error("Failed to load voices:", e);
    }
}

// --- File Upload (Voice Clone) ---
const dropzone = document.getElementById("vc-dropzone");
const fileInput = document.getElementById("vc-file");
const fileInfo = document.getElementById("vc-file-info");

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
        showFileInfo(e.dataTransfer.files[0]);
    }
});
fileInput.addEventListener("change", () => {
    if (fileInput.files.length) showFileInfo(fileInput.files[0]);
});

function showFileInfo(file) {
    fileInfo.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    fileInfo.classList.remove("hidden");
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
async function pollModelStatus(variant) {
    while (true) {
        const res = await fetch(`/api/model-status?variant=${variant}`);
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
        const ready = await pollModelStatus(variant);
        if (!ready) {
            setGenerating(tabId, false);
            return;
        }
        return null;
    }

    if (data.status === "done") {
        hideStatus();
        showAudio(data.filename);
        addHistory({ ...data, text: meta.text });
        setGenerating(tabId, false);
    }

    if (data.status === "error") {
        showStatus(data.message, "error");
        setGenerating(tabId, false);
    }
}

// --- Generate: Custom Voice ---
async function generateCustomVoice() {
    const text = document.getElementById("cv-text").value.trim();
    if (!text) return;

    setGenerating("custom-voice", true);

    const form = new FormData();
    form.append("text", text);
    form.append("language", document.getElementById("cv-language").value);
    form.append("speaker", document.getElementById("cv-speaker").value);
    form.append("instruct", document.getElementById("cv-instruct").value);

    while (true) {
        const res = await fetch("/api/tts/custom-voice", { method: "POST", body: form });
        const result = await handleResponse(res, "custom-voice", "custom_voice", { text });
        if (result !== null) break;
    }
}

// --- Generate: Voice Clone ---
async function generateVoiceClone() {
    const text = document.getElementById("vc-text").value.trim();
    const refText = document.getElementById("vc-ref-text").value.trim();
    const file = document.getElementById("vc-file").files[0];
    if (!text || !refText || !file) {
        showStatus("Please fill in all fields and upload a reference audio clip.", "error");
        return;
    }

    setGenerating("voice-clone", true);

    const form = new FormData();
    form.append("text", text);
    form.append("language", document.getElementById("vc-language").value);
    form.append("ref_text", refText);
    form.append("ref_audio", file);

    while (true) {
        const res = await fetch("/api/tts/voice-clone", { method: "POST", body: form });
        const result = await handleResponse(res, "voice-clone", "voice_clone", { text });
        if (result !== null) break;
    }
}

// --- Generate: Voice Design ---
async function generateVoiceDesign() {
    const text = document.getElementById("vd-text").value.trim();
    const instruct = document.getElementById("vd-instruct").value.trim();
    if (!text || !instruct) {
        showStatus("Please fill in both voice description and text.", "error");
        return;
    }

    setGenerating("voice-design", true);

    const form = new FormData();
    form.append("text", text);
    form.append("language", document.getElementById("vd-language").value);
    form.append("instruct", instruct);

    while (true) {
        const res = await fetch("/api/tts/voice-design", { method: "POST", body: form });
        const result = await handleResponse(res, "voice-design", "voice_design", { text });
        if (result !== null) break;
    }
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
    const snippet = item.text.length > 40 ? item.text.substring(0, 40) + "..." : item.text;
    let label = item.mode.replace("_", " ");
    if (item.speaker) label = item.speaker;
    if (item.mode === "voice_clone") label = "Cloned voice";
    if (item.mode === "voice_design") label = "Designed voice";

    history.unshift({ ...item, snippet, label });

    const list = document.getElementById("history-list");
    list.innerHTML = history
        .map(
            (h, i) => `
        <div class="history-item" onclick="showAudio('${h.filename}')">
            <div>
                <div class="text-white text-sm">"${h.snippet}"</div>
                <div class="text-gray-500 text-xs">${h.label} · ${h.language} · ${h.duration}s</div>
            </div>
            <div class="text-accent text-sm">▶</div>
        </div>
    `
        )
        .join("");
}

// --- Init ---
loadVoices();
