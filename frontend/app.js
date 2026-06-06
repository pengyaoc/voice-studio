let history = [];
let currentTab = "voice-clone";
const STREAMING_MODE = "stream";
let currentModelSize = STREAMING_MODE;
let availableModelSizes = {};
const activeGenerations = new Set();
let playbackQueue = [];
let streamPlaybackActive = false;

let availableReferenceClips = [];
let cloneProfiles = [];
let selectedCloneProfileId = "";
let uploadInFlight = null;
let profileModalMode = "new";
let profileModalEditingId = "";
let profileModalSelectedClip = "";

const profilesList = document.getElementById("vc-profiles");
const newProfileBtn = document.getElementById("vc-new-profile");
const editProfileBtn = document.getElementById("vc-edit-profile");
const deleteProfileBtn = document.getElementById("vc-delete-profile");
const profileModal = document.getElementById("vc-profile-modal");
const profileModalTitle = document.getElementById("vc-modal-title");
const profileModalName = document.getElementById("vc-modal-name");
const profileModalClip = document.getElementById("vc-modal-clip");
const profileModalRefText = document.getElementById("vc-modal-ref-text");
const profileModalFile = document.getElementById("vc-modal-file");
const profileModalFileInfo = document.getElementById("vc-modal-file-info");
const profileModalUploadTrigger = document.getElementById("vc-modal-upload-trigger");
const profileModalSave = document.getElementById("vc-modal-save");
const profileModalCancel = document.getElementById("vc-modal-cancel");
const profileModalClose = document.getElementById("vc-modal-close");

function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }[char]));
}

function formatSeconds(seconds) {
    return `${Number(seconds).toFixed(2)}s`;
}

function truncateText(text, maxLength = 120) {
    if (!text) return "";
    return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function normalizeCloneProfile(profile) {
    return {
        id: profile.id,
        name: profile.name || "",
        reference_clip: profile.reference_clip || "",
        ref_text: profile.ref_text || "",
        created_at: profile.created_at || "",
        updated_at: profile.updated_at || "",
    };
}

function selectedCloneProfile() {
    return cloneProfiles.find((profile) => profile.id === selectedCloneProfileId) || null;
}

function findReferenceClip(filename) {
    return availableReferenceClips.find((item) => item.filename === filename) || null;
}

function buildHistoryMeta(item) {
    const text = item.text || "Recovered generation";
    const snippet = item.snippet || (text.length > 40 ? text.substring(0, 40) + "..." : text);
    let label = item.label || item.mode.replace("_", " ");
    if (item.speaker) label = item.speaker;
    if (item.mode === "voice_clone") label = item.profile_name || "Cloned voice";
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
            const parts = [
                item.label,
                item.language,
                item.model_size || "1.7B",
                `${item.duration}s`,
            ];
            if (item.processing_time != null) {
                parts.push(`processed in ${formatSeconds(item.processing_time)}`);
            }
            if (item.streaming) {
                parts.push("stream");
            }
            const meta = parts.join(" · ");
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

function renderCloneProfiles() {
    if (!cloneProfiles.length) {
        profilesList.innerHTML = `
            <div class="voice-profile-empty">
                No saved voices yet. Click <strong>New Voice</strong> to create one.
            </div>
        `;
        return;
    }

    profilesList.innerHTML = cloneProfiles
        .map((profile) => {
            const isActive = profile.id === selectedCloneProfileId;
            return `
                <button class="voice-profile-card${isActive ? " active" : ""}" type="button" data-profile-id="${escapeHtml(profile.id)}">
                    <div class="voice-profile-card-top">
                        <div class="voice-profile-card-name">${escapeHtml(profile.name)}</div>
                        ${isActive ? '<span class="voice-profile-card-badge">Active</span>' : ""}
                    </div>
                </button>
            `;
        })
        .join("");

    profilesList.querySelectorAll("[data-profile-id]").forEach((button) => {
        button.addEventListener("click", () => {
            void selectCloneProfileAction(button.dataset.profileId);
        });
    });
}

function syncCloneProfileUI() {
    renderCloneProfiles();
    const hasSelection = Boolean(selectedCloneProfile());
    editProfileBtn.disabled = !hasSelection;
    deleteProfileBtn.disabled = !hasSelection;
}

function renderProfileModalClipOptions() {
    profileModalClip.innerHTML = `
        <option value="">Choose an uploaded clip...</option>
        ${availableReferenceClips.map((clip) => `<option value="${clip.filename}">${clip.filename}</option>`).join("")}
    `;
    profileModalClip.value = profileModalSelectedClip;
    updateProfileModalFileInfo();
}

function updateProfileModalFileInfo() {
    if (!profileModalSelectedClip) {
        profileModalFileInfo.textContent = "";
        return;
    }

    const clip = findReferenceClip(profileModalSelectedClip);
    if (clip) {
        profileModalFileInfo.textContent = `${clip.filename} (${(clip.size / 1024).toFixed(1)} KB)`;
    } else {
        profileModalFileInfo.textContent = profileModalSelectedClip;
    }
}

function openProfileModal(mode) {
    const selected = selectedCloneProfile();
    if (mode === "edit" && !selected) {
        showStatus("Choose a saved voice to edit.", "error");
        return;
    }

    profileModalMode = mode;
    profileModalEditingId = mode === "edit" && selected ? selected.id : "";
    profileModalTitle.textContent = mode === "edit" ? "Edit Voice" : "New Voice";
    profileModalSave.textContent = mode === "edit" ? "Save Changes" : "Save Voice";

    profileModalName.value = selected && mode === "edit" ? selected.name : "";
    profileModalRefText.value = selected && mode === "edit" ? selected.ref_text : "";
    profileModalSelectedClip = selected && mode === "edit" ? selected.reference_clip : "";
    renderProfileModalClipOptions();

    profileModal.classList.remove("hidden");
}

function closeProfileModal() {
    profileModal.classList.add("hidden");
    profileModalFile.value = "";
    profileModalFileInfo.textContent = "";
}

function modalPayload() {
    return {
        name: profileModalName.value.trim(),
        reference_clip: profileModalSelectedClip,
        ref_text: profileModalRefText.value.trim(),
    };
}

function isProfileModalValid() {
    const payload = modalPayload();
    return Boolean(payload.name && payload.reference_clip && payload.ref_text);
}

// --- Model Size Toggle ---
function isStreamingAvailable(variant) {
    const sizes = availableModelSizes[variant] || [];
    return variant !== "voice_design" && sizes.includes("0.6B");
}

function getAvailableModes(variant) {
    const sizes = [...(availableModelSizes[variant] || ["1.7B"])];
    if (isStreamingAvailable(variant)) {
        sizes.push(STREAMING_MODE);
    }
    return sizes;
}

document.querySelectorAll(".model-size-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        const size = btn.dataset.size;
        const modes = getAvailableModes(currentTab.replace("-", "_"));
        if (!modes.includes(size)) {
            return;
        }
        document.querySelectorAll(".model-size-btn").forEach((button) => button.classList.remove("active"));
        btn.classList.add("active");
        currentModelSize = size;
    });
});

function updateModelSizeButtons() {
    const variant = currentTab.replace("-", "_");
    const sizes = getAvailableModes(variant);
    document.querySelectorAll(".model-size-btn").forEach((btn) => {
        const available = sizes.includes(btn.dataset.size);
        btn.disabled = !available;
        btn.classList.toggle("opacity-30", !available);
        btn.classList.toggle("cursor-not-allowed", !available);
    });
    if (!sizes.includes(currentModelSize)) {
        currentModelSize = sizes.includes("0.6B") ? "0.6B" : sizes[sizes.length - 1];
        document.querySelectorAll(".model-size-btn").forEach((button) => button.classList.remove("active"));
        document.querySelector(`.model-size-btn[data-size="${currentModelSize}"]`)?.classList.add("active");
    }
}

// --- Tab Switching ---
document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((button) => button.classList.remove("active"));
        btn.classList.add("active");

        currentTab = btn.dataset.tab;
        document.querySelectorAll(".tab-content").forEach((content) => content.classList.add("hidden"));
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
            .map((speaker) => `<option value="${speaker.id}">${speaker.name} — ${speaker.description} (${speaker.language})</option>`)
            .join("");

        const languageSelects = ["cv-language", "vc-language", "vd-language"];
        languageSelects.forEach((id) => {
            const select = document.getElementById(id);
            select.innerHTML = data.languages
                .map((language) => `<option value="${language}">${language}</option>`)
                .join("");
        });

        if (data.model_sizes) {
            availableModelSizes = data.model_sizes;
            updateModelSizeButtons();
        }
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

async function loadReferenceClips() {
    try {
        const res = await fetch("/api/reference-clips");
        const data = await res.json();
        availableReferenceClips = data.items || [];
        renderProfileModalClipOptions();
    } catch (e) {
        console.error("Failed to load reference clips:", e);
    }
}

async function fetchCloneProfiles() {
    const res = await fetch("/api/voice-clone/profiles");
    const data = await res.json();
    cloneProfiles = (data.profiles || []).map(normalizeCloneProfile);
    selectedCloneProfileId = data.selected_profile_id || "";
    syncCloneProfileUI();
    return data;
}

async function loadCloneProfiles() {
    try {
        await fetchCloneProfiles();
    } catch (e) {
        console.error("Failed to load voice profiles:", e);
    }
}

async function saveCloneSelection(profileId) {
    const res = await fetch("/api/voice-clone/profiles/selected", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selected_profile_id: profileId }),
    });
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || "Failed to select voice profile.");
    }
    cloneProfiles = (data.profiles || []).map(normalizeCloneProfile);
    selectedCloneProfileId = data.selected_profile_id || "";
    syncCloneProfileUI();
    return data;
}

async function selectCloneProfileAction(profileId) {
    if (profileId === selectedCloneProfileId) {
        return;
    }
    try {
        await saveCloneSelection(profileId);
    } catch (e) {
        console.error("Failed to select voice profile:", e);
        showStatus(e.message || "Failed to switch voice profile.", "error");
    }
}

async function deleteCloneProfileAction() {
    if (!selectedCloneProfileId) {
        return;
    }
    if (!window.confirm("Delete this saved voice profile?")) {
        return;
    }

    try {
        const res = await fetch(`/api/voice-clone/profiles/${selectedCloneProfileId}`, {
            method: "DELETE",
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Failed to delete voice profile.");
        }

        cloneProfiles = (data.profiles || []).map(normalizeCloneProfile);
        selectedCloneProfileId = data.selected_profile_id || "";
        syncCloneProfileUI();
        hideStatus();
    } catch (e) {
        console.error("Failed to delete voice profile:", e);
        showStatus(e.message || "Failed to delete voice profile.", "error");
    }
}

async function uploadReferenceClip(file) {
    const form = new FormData();
    form.append("file", file);

    const res = await fetch("/api/reference-clips", {
        method: "POST",
        body: form,
    });
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.detail || "Failed to upload reference clip.");
    }
    return data.item;
}

async function handleProfileModalFileSelected(file) {
    showStatus("Uploading reference clip...", "loading");

    const uploadPromise = uploadReferenceClip(file);
    uploadInFlight = uploadPromise;

    try {
        const clip = await uploadPromise;
        if (uploadInFlight !== uploadPromise) {
            return;
        }

        await loadReferenceClips();
        profileModalSelectedClip = clip.filename;
        renderProfileModalClipOptions();
        profileModalFile.value = "";
        hideStatus();
    } catch (e) {
        if (uploadInFlight === uploadPromise) {
            showStatus(e.message || "Failed to upload reference clip.", "error");
        }
        console.error("Failed to upload reference clip:", e);
    } finally {
        if (uploadInFlight === uploadPromise) {
            uploadInFlight = null;
        }
    }
}

async function saveProfileFromModal() {
    if (!isProfileModalValid()) {
        showStatus("Voice name, reference clip, and transcript are required.", "error");
        return;
    }

    const payload = modalPayload();
    const endpoint = profileModalMode === "edit"
        ? `/api/voice-clone/profiles/${profileModalEditingId}`
        : "/api/voice-clone/profiles";
    const method = profileModalMode === "edit" ? "PUT" : "POST";

    try {
        const res = await fetch(endpoint, {
            method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Failed to save voice profile.");
        }

        cloneProfiles = (data.profiles || []).map(normalizeCloneProfile);
        selectedCloneProfileId = data.selected_profile_id || "";
        syncCloneProfileUI();
        closeProfileModal();
        hideStatus();
    } catch (e) {
        console.error("Failed to save voice profile:", e);
        showStatus(e.message || "Failed to save voice profile.", "error");
    }
}

newProfileBtn.addEventListener("click", () => openProfileModal("new"));
editProfileBtn.addEventListener("click", () => openProfileModal("edit"));
deleteProfileBtn.addEventListener("click", () => {
    void deleteCloneProfileAction();
});
profileModalUploadTrigger.addEventListener("click", () => profileModalFile.click());
profileModalFile.addEventListener("change", () => {
    if (profileModalFile.files.length) {
        void handleProfileModalFileSelected(profileModalFile.files[0]);
    }
});
profileModalClip.addEventListener("change", () => {
    profileModalSelectedClip = profileModalClip.value;
    updateProfileModalFileInfo();
});
profileModalSave.addEventListener("click", () => {
    void saveProfileFromModal();
});
profileModalCancel.addEventListener("click", closeProfileModal);
profileModalClose.addEventListener("click", closeProfileModal);
profileModal.addEventListener("click", (event) => {
    if (event.target === profileModal) {
        closeProfileModal();
    }
});
document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !profileModal.classList.contains("hidden")) {
        closeProfileModal();
    }
});

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
        await new Promise((resolve) => setTimeout(resolve, 2000));
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

function stopStreamPlayback() {
    playbackQueue = [];
    streamPlaybackActive = false;

    const audio = document.getElementById("audio-element");
    audio.onended = null;
    audio.pause();
    audio.removeAttribute("src");
    audio.load();
}

function updateDownloadTarget(filename) {
    const player = document.getElementById("audio-player");
    const downloadBtn = document.getElementById("download-btn");
    const url = `/audio/${filename}`;

    player.classList.remove("hidden");
    downloadBtn.href = url;
    downloadBtn.download = filename.split("/").pop();
}

function playNextQueuedChunk() {
    if (!playbackQueue.length) {
        streamPlaybackActive = false;
        return;
    }

    const audio = document.getElementById("audio-element");
    const nextUrl = playbackQueue.shift();
    streamPlaybackActive = true;
    audio.onended = () => {
        if (playbackQueue.length) {
            playNextQueuedChunk();
            return;
        }
        streamPlaybackActive = false;
    };
    audio.src = nextUrl;
    audio.play().catch((error) => {
        console.error("Failed to play streamed audio chunk:", error);
    });
}

function enqueueStreamChunk(filename) {
    updateDownloadTarget(filename);
    playbackQueue.push(`/audio/${filename}`);
    const audio = document.getElementById("audio-element");
    if (!streamPlaybackActive || audio.ended || !audio.src) {
        playNextQueuedChunk();
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

async function handleStreamingResponse(res, variant, meta) {
    const reader = res.body?.getReader();
    if (!reader) {
        showStatus("Streaming is not supported by this browser response.", "error");
        return "error";
    }

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { value, done } = await reader.read();
        if (done) {
            break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
            if (!line.trim()) {
                continue;
            }

            const data = JSON.parse(line);
            if (data.status === "loading") {
                showStatus(data.message, "loading");
                const ready = await pollModelStatus(variant, meta.modelSize);
                if (!ready) {
                    return "error";
                }
                return "retry";
            }

            if (data.status === "chunk") {
                showStatus(`Streaming audio ${data.index + 1}/${data.count}...`, "loading");
                enqueueStreamChunk(data.filename);
                continue;
            }

            if (data.status === "done") {
                hideStatus();
                updateDownloadTarget(data.item.filename);
                addHistory(data.item);
                if (typeof meta.afterSuccess === "function") {
                    await meta.afterSuccess(data.item);
                }
                return "done";
            }

            if (data.status === "error") {
                showStatus(data.message, "error");
                return "error";
            }
        }
    }

    showStatus("Streaming ended unexpectedly.", "error");
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

async function submitStreamingGeneration(tabId, endpoint, variant, buildForm, meta) {
    if (activeGenerations.has(tabId)) {
        return;
    }

    activeGenerations.add(tabId);
    setGenerating(tabId, true);
    stopStreamPlayback();

    try {
        while (true) {
            const res = await fetch(endpoint, { method: "POST", body: buildForm() });
            const action = await handleStreamingResponse(res, variant, meta);
            if (action !== "retry") {
                break;
            }
        }
    } catch (e) {
        console.error(`Failed to stream for ${tabId}:`, e);
        showStatus("Streaming failed. Check the server logs and try again.", "error");
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

    if (modelSize === STREAMING_MODE) {
        await submitStreamingGeneration(
            "custom-voice",
            "/api/tts/custom-voice/stream",
            "custom_voice",
            () => {
                const form = new FormData();
                form.append("text", text);
                form.append("language", document.getElementById("cv-language").value);
                form.append("speaker", document.getElementById("cv-speaker").value);
                form.append("instruct", document.getElementById("cv-instruct").value);
                return form;
            },
            { text, modelSize: "0.6B" },
        );
        return;
    }

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
    const profile = selectedCloneProfile();
    const modelSize = currentModelSize;

    if (uploadInFlight) {
        showStatus("Wait for the reference clip upload to finish.", "loading");
        return;
    }
    if (!profile || !profile.reference_clip || !profile.ref_text) {
        showStatus("Choose a saved voice profile with a clip and transcript before generating.", "error");
        return;
    }
    if (!text) {
        showStatus("Enter text to speak.", "error");
        return;
    }

    if (modelSize === STREAMING_MODE) {
        await submitStreamingGeneration(
            "voice-clone",
            "/api/tts/voice-clone/stream",
            "voice_clone",
            () => {
                const form = new FormData();
                form.append("text", text);
                form.append("language", document.getElementById("vc-language").value);
                form.append("ref_text", profile.ref_text);
                form.append("reference_clip", profile.reference_clip);
                form.append("profile_name", profile.name);
                return form;
            },
            { text, modelSize: "0.6B" },
        );
        return;
    }

    await submitGeneration(
        "voice-clone",
        "/api/tts/voice-clone",
        "voice_clone",
        () => {
            const form = new FormData();
            form.append("text", text);
            form.append("language", document.getElementById("vc-language").value);
            form.append("ref_text", profile.ref_text);
            form.append("reference_clip", profile.reference_clip);
            form.append("profile_name", profile.name);
            form.append("model_size", modelSize);
            return form;
        },
        { text, modelSize },
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
    stopStreamPlayback();
    const audio = document.getElementById("audio-element");
    const url = `/audio/${filename}`;
    updateDownloadTarget(filename);
    audio.src = url;
    audio.play();
}

// --- History ---
function addHistory(item) {
    history = [buildHistoryMeta(item), ...history.filter((entry) => entry.filename !== item.filename)];
    renderHistory();
}

async function init() {
    editProfileBtn.disabled = true;
    deleteProfileBtn.disabled = true;
    renderCloneProfiles();
    await Promise.all([
        loadVoices(),
        loadHistory(),
        loadReferenceClips(),
        loadCloneProfiles(),
    ]);
}

void init();
