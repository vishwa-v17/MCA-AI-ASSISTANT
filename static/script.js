let activeSessionId = null;
let subjectsData = [];
let currentSemester = 1;

document.addEventListener("DOMContentLoaded", () => {
    loadSessions();
    loadSubjects();

    const textarea = document.getElementById("msg");
    if(textarea) {
        textarea.addEventListener("input", function() {
            this.style.height = "auto";
            this.style.height = (this.scrollHeight - 4) + "px";
        });
        textarea.addEventListener("keydown", function(e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMsg();
            }
        });
    }

    if (window.marked) {
        marked.setOptions({ gfm: true, breaks: true, headerIds: false, mangle: false });
    }

    // Check query params for "Ask AI"
    const params = new URLSearchParams(window.location.search);
    if(params.has('ask_subject')) {
        const code = params.get('ask_subject');
        const name = params.get('subject_name');
        setTimeout(() => {
            askAIAboutSubject(`I am studying ${name} (${code}). Let's start with a general overview and then you can test my knowledge.`);
        }, 500); // short delay to let sessions load
    }
});

function toggleSidebar() {
    document.querySelector(".sidebar").classList.toggle("open");
}

function showDashboard() {
    activeSessionId = null;
    document.querySelectorAll(".session-item").forEach(item => item.classList.remove("active"));
    const chatView = document.getElementById("chat-view");
    const dashView = document.getElementById("dashboard-view");
    if(chatView) chatView.classList.remove("active");
    if(dashView) dashView.classList.add("active");
    
    const title = document.getElementById("current-chat-title");
    if(title) title.innerText = "Welcome back!";
    
    document.querySelector(".sidebar").classList.remove("open");
}

function showChatView() {
    document.getElementById("dashboard-view").classList.remove("active");
    document.getElementById("chat-view").classList.add("active");
}

async function loadSessions() {
    try {
        const res = await fetch("/api/sessions");
        const data = await res.json();
        const list = document.getElementById("sessions-list");
        if(!list) return;
        list.innerHTML = "";

        if (data.sessions.length === 0) {
            list.innerHTML = `<div style="padding: 10px 8px; font-size: 12.5px; color: var(--text-muted); font-style: italic;">No recent sessions. Start a new chat!</div>`;
            return;
        }

        data.sessions.forEach(session => {
            const item = document.createElement("div");
            item.className = `session-item ${session.id === activeSessionId ? 'active' : ''}`;
            item.setAttribute("data-id", session.id);
            item.onclick = () => selectSession(session.id, session.title);
            
            const pinIcon = session.is_pinned ? `<i class="fa-solid fa-thumbtack text-purple"></i>` : `<i class="fa-regular fa-comments"></i>`;

            item.innerHTML = `
                <span class="session-title-text">
                    ${pinIcon}
                    <span>${escapeHTML(session.title)}</span>
                </span>
                <button class="delete-session-btn" onclick="deleteSession('${session.id}', event)">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;
            list.appendChild(item);
        });
    } catch (err) {
        console.error("Error loading sessions:", err);
    }
}

async function startNewSession(initialTitle = "New Study Session") {
    try {
        const res = await fetch("/api/sessions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: initialTitle })
        });
        const data = await res.json();
        
        activeSessionId = data.session_id;
        await loadSessions();
        selectSession(data.session_id, data.title);
    } catch (err) {
        console.error("Error starting new session:", err);
    }
}

async function selectSession(sessionId, title) {
    activeSessionId = sessionId;
    showChatView();
    
    document.querySelectorAll(".session-item").forEach(item => {
        if (item.getAttribute("data-id") === sessionId) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    document.getElementById("current-chat-title").innerText = title;
    
    const chatMessages = document.getElementById("chat-messages");
    chatMessages.innerHTML = "";

    const typingIndicator = addLoadingIndicator();

    try {
        const res = await fetch(`/api/sessions/${sessionId}/messages`);
        const data = await res.json();
        
        removeLoadingIndicator(typingIndicator);

        if (data.messages.length === 0) {
            addMessage("Hello! I am your MCA AI Assistant. What can I help you learn today?", "bot");
        } else {
            data.messages.forEach(msg => {
                addMessage(msg.content, msg.sender);
            });
        }
    } catch (err) {
        removeLoadingIndicator(typingIndicator);
        addMessage("Failed to load chat history. Please try reloading the page.", "bot");
    }
    
    document.querySelector(".sidebar").classList.remove("open");
}

async function deleteSession(sessionId, event) {
    event.stopPropagation();
    if (!confirm("Are you sure you want to delete this study session?")) return;

    try {
        await fetch(`/api/sessions/${sessionId}`, { method: "DELETE" });
        if (activeSessionId === sessionId) {
            showDashboard();
        }
        loadSessions();
    } catch (err) {
        console.error("Error deleting session:", err);
    }
}

async function renameCurrentSession() {
    if(!activeSessionId) return;
    const newTitle = prompt("Enter new title for this session:");
    if(!newTitle) return;
    try {
        await fetch(`/api/sessions/${activeSessionId}/rename`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({title: newTitle})
        });
        loadSessions();
        document.getElementById("current-chat-title").innerText = newTitle;
    } catch (err) {
        console.error(err);
    }
}

async function pinCurrentSession() {
    if(!activeSessionId) return;
    try {
        await fetch(`/api/sessions/${activeSessionId}/pin`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({is_pinned: true})
        });
        loadSessions();
        alert("Session pinned!");
    } catch (err) {
        console.error(err);
    }
}

let currentAttachedFile = null;

function triggerFileUpload() {
    const fileInput = document.getElementById("chat-file-input");
    if (fileInput) {
        fileInput.value = "";
        fileInput.click();
    }
}

function handleChatFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const MAX_SIZE = 10 * 1024 * 1024; // 10 MB limit
    const ALLOWED_EXTS = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'webp'];

    // 1. Frontend validation: File size
    if (file.size > MAX_SIZE) {
        alert("File size must not exceed 10 MB.");
        event.target.value = "";
        return;
    }

    // 2. Frontend validation: Extension
    const parts = file.name.split('.');
    const ext = parts.length > 1 ? parts.pop().toLowerCase() : '';
    if (!ALLOWED_EXTS.includes(ext)) {
        alert("Unsupported file type. Please upload a PDF, Word document (.doc, .docx), or image (.jpg, .jpeg, .png, .webp).");
        event.target.value = "";
        return;
    }

    // Store selected file as an attachment to the current message (do NOT auto-send)
    currentAttachedFile = file;

    // Display attachment preview chip
    const previewContainer = document.getElementById("attachment-preview-container");
    const nameEl = document.getElementById("attachment-name");
    const sizeEl = document.getElementById("attachment-size");
    const iconEl = document.getElementById("attachment-icon");
    const thumbEl = document.getElementById("attachment-thumb");

    const sizeFormatted = file.size > 1024 * 1024 
        ? (file.size / (1024 * 1024)).toFixed(1) + " MB" 
        : (file.size / 1024).toFixed(1) + " KB";

    if (nameEl) nameEl.textContent = file.name;
    if (sizeEl) sizeEl.textContent = `(${sizeFormatted})`;

    // Show thumbnail for images, icon for documents
    if (['jpg', 'jpeg', 'png', 'webp'].includes(ext)) {
        const reader = new FileReader();
        reader.onload = function(e) {
            if (thumbEl) {
                thumbEl.src = e.target.result;
                thumbEl.style.display = "inline-block";
            }
            if (iconEl) iconEl.style.display = "none";
        };
        reader.readAsDataURL(file);
    } else {
        if (thumbEl) {
            thumbEl.src = "";
            thumbEl.style.display = "none";
        }
        if (iconEl) {
            iconEl.style.display = "inline-flex";
            if (ext === 'pdf') {
                iconEl.innerHTML = '<i class="fa-solid fa-file-pdf" style="color: #ef4444;"></i>';
            } else {
                iconEl.innerHTML = '<i class="fa-solid fa-file-word" style="color: #3b82f6;"></i>';
            }
        }
    }

    if (previewContainer) {
        previewContainer.style.display = "flex";
    }

    // Ensure chat view is active and focus input textarea so user can type question
    showChatView();
    const textarea = document.getElementById("msg");
    if (textarea) {
        textarea.focus();
    }
}

function removeAttachment() {
    currentAttachedFile = null;
    const previewContainer = document.getElementById("attachment-preview-container");
    if (previewContainer) {
        previewContainer.style.display = "none";
    }
    const thumbEl = document.getElementById("attachment-thumb");
    if (thumbEl) {
        thumbEl.src = "";
        thumbEl.style.display = "none";
    }
    const fileInput = document.getElementById("chat-file-input");
    if (fileInput) {
        fileInput.value = "";
    }
    // Leaves any typed text in the message input untouched!
}

async function streamAIChatResponse(fetchOptions) {
    const typing = addTypingBubble();

    try {
        const res = await fetch("/chat", fetchOptions);

        if (!res.ok) {
            removeTypingBubble(typing);
            let errMsg = "Error connecting to server.";
            try {
                const errData = await res.json();
                if (errData && errData.error) errMsg = errData.error;
            } catch (e) {}
            addMessage(errMsg, "bot");
            return;
        }

        removeTypingBubble(typing);
        
        const chatContainer = document.getElementById("chat-messages");
        const wrapper = document.createElement("div");
        wrapper.className = "message-wrapper bot";
        const bubble = document.createElement("div");
        bubble.className = "msg";
        wrapper.appendChild(bubble);
        chatContainer.appendChild(wrapper);
        
        let accumulatedText = "";
        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();
            
            for (const line of lines) {
                const cleanedLine = line.trim();
                if (cleanedLine.startsWith("data: ")) {
                    const dataStr = cleanedLine.substring(6);
                    try {
                        const parsed = JSON.parse(dataStr);
                        if (parsed.error) {
                            bubble.innerText = "Error: " + parsed.error;
                            break;
                        } else if (parsed.content) {
                            accumulatedText += parsed.content;
                            if (window.marked) {
                                bubble.innerHTML = marked.parse(accumulatedText);
                            } else {
                                bubble.innerText = accumulatedText;
                            }
                            chatContainer.scrollTop = chatContainer.scrollHeight;
                        }
                    } catch (e) {
                        // ignore malformed JSON or partial chunks
                    }
                }
            }
        }

        if (window.Prism) {
            Prism.highlightAllUnder(bubble);
        }

    } catch (err) {
        removeTypingBubble(typing);
        addMessage("Connection error. Please try again.", "bot");
        console.error(err);
    }
}

async function sendMsg() {
    const input = document.getElementById("msg");
    const message = input ? input.value.trim() : "";
    const fileToSend = currentAttachedFile;

    // Must have either a message or an attached file
    if (!message && !fileToSend) return;

    // Clear input field immediately
    if (input) {
        input.value = "";
        input.style.height = "auto";
    }

    // Clear attachment chip
    if (fileToSend) {
        removeAttachment();
    }

    // Ensure session exists
    if (!activeSessionId) {
        let shortTitle = message.substring(0, 24);
        if (!shortTitle && fileToSend) {
            shortTitle = "Doc: " + fileToSend.name.substring(0, 20);
        }
        if (shortTitle && shortTitle.length > 24) shortTitle += "...";
        
        try {
            const res = await fetch("/api/sessions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: shortTitle || "New Study Session" })
            });
            const data = await res.json();
            activeSessionId = data.session_id;
            await loadSessions();
            showChatView();
            const titleEl = document.getElementById("current-chat-title");
            if (titleEl) titleEl.innerText = data.title;
        } catch (err) {
            console.error("Error starting dynamic session:", err);
            return;
        }
    }

    // Display user message in chat
    let displayUserMessage = message;
    if (fileToSend) {
        const sizeFormatted = fileToSend.size > 1024 * 1024 
            ? (fileToSend.size / (1024 * 1024)).toFixed(1) + " MB" 
            : (fileToSend.size / 1024).toFixed(1) + " KB";
        displayUserMessage = `📎 ${fileToSend.name} (${sizeFormatted})`;
        if (message) {
            displayUserMessage += `\n\n${message}`;
        }
    }
    addMessage(displayUserMessage, "user");

    // Prepare request payload (multipart if attached file, JSON otherwise)
    let fetchOptions;
    if (fileToSend) {
        const formData = new FormData();
        formData.append("file", fileToSend);
        formData.append("message", message);
        formData.append("session_id", activeSessionId);
        fetchOptions = {
            method: "POST",
            body: formData
        };
    } else {
        fetchOptions = {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: message, session_id: activeSessionId })
        };
    }

    // Stream AI response
    await streamAIChatResponse(fetchOptions);
}

function addMessage(text, sender) {
    const chatContainer = document.getElementById("chat-messages");
    if(!chatContainer) return;
    
    const wrapper = document.createElement("div");
    wrapper.className = `message-wrapper ${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "msg";

    if (sender === "bot") {
        if (window.marked) {
            bubble.innerHTML = marked.parse(text);
        } else {
            bubble.innerText = text;
        }
    } else {
        bubble.innerText = text;
    }

    wrapper.appendChild(bubble);
    chatContainer.appendChild(wrapper);
    
    if (sender === "bot" && window.Prism) {
        Prism.highlightAllUnder(bubble);
    }
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addLoadingIndicator() {
    const chatContainer = document.getElementById("chat-messages");
    const wrapper = document.createElement("div");
    wrapper.className = "message-wrapper bot temp-loader";
    wrapper.innerHTML = `
        <div class="msg" style="padding: 12px 16px;">
            <div class="typing-bubble">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatContainer.appendChild(wrapper);
    return wrapper;
}
function removeLoadingIndicator(el) { if (el) el.remove(); }
function addTypingBubble() { return addLoadingIndicator(); }
function removeTypingBubble(el) { removeLoadingIndicator(el); }

function useQuickPrompt(text) {
    const textarea = document.getElementById("msg");
    if(textarea) {
        textarea.value = text;
        textarea.style.height = "auto";
        textarea.style.height = (textarea.scrollHeight - 4) + "px";
        sendMsg();
    }
}

function askAIAboutSubject(prompt) {
    if (!activeSessionId) {
        startNewSession("Syllabus Study").then(() => {
            useQuickPrompt(prompt);
        });
    } else {
        useQuickPrompt(prompt);
    }
}

async function loadSubjects() {
    try {
        const res = await fetch("/api/subjects");
        const data = await res.json();
        subjectsData = data.subjects || [];
        renderSubjects();
    } catch (err) {
        console.error("Error fetching subjects:", err);
    }
}

function switchSemester(sem) {
    currentSemester = sem;
    document.querySelectorAll(".sem-tab").forEach((tab, index) => {
        if (index + 1 === sem) {
            tab.classList.add("active");
        } else {
            tab.classList.remove("active");
        }
    });
    renderSubjects();
}

function renderSubjects() {
    const container = document.getElementById("subjects-container");
    if(!container) return;
    
    container.innerHTML = "";

    const filtered = subjectsData.filter(s => s.semester === currentSemester);

    if (filtered.length === 0) {
        container.innerHTML = `<div style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 40px;">No subjects found for Semester ${currentSemester}.</div>`;
        return;
    }

    filtered.forEach(subject => {
        const card = document.createElement("div");
        card.className = "subject-card";
        // Directly route to the new subject page
        card.onclick = () => {
            window.location.href = `/subject/${subject.code}`;
        };

        card.innerHTML = `
            <div>
                <span class="subj-code">${subject.code}</span>
                <h4 class="subj-title">${escapeHTML(subject.name)}</h4>
            </div>
            <div class="subj-footer">
                <span>Semester ${subject.semester}</span>
                <span class="view-syllabus-link">Study Hub <i class="fa-solid fa-arrow-right"></i></span>
            </div>
        `;
        container.appendChild(card);
    });
}

// Config Modal handling
let availableModels = [];
let selectedModelId = "";

async function openConfigModal() {
    const statusMsg = document.getElementById("config-status-msg");
    statusMsg.style.display = "none";
    statusMsg.className = "";
    statusMsg.innerText = "";

    document.getElementById("config-api-key").value = "";
    document.getElementById("config-model-search").value = "";

    try {
        const res = await fetch("/api/config");
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Could not load settings.");

        selectedModelId = data.model || data.default_model || "openrouter/free";

        const access = document.getElementById("config-access-status");
        access.innerText = data.api_key_status || "Using default server key";
        access.style.color = data.has_personal_key ? "var(--accent-primary)" : "var(--text-muted)";

        const personalStatus = document.getElementById("personal-key-status");
        if (data.has_personal_key) {
            personalStatus.innerText = `Personal key: ••••••••••••${data.personal_key_last4 || ""} (stored securely)`;
        } else {
            personalStatus.innerText = data.server_default_available
                ? "Personal key not configured. Using the default server key."
                : "No personal key is configured.";
        }

        document.getElementById("remove-key-btn").disabled = !data.has_personal_key;

        await loadModelCatalog();
    } catch (err) {
        showConfigStatus(err.message || "Could not load settings.", "status-error");
    }

    document.getElementById("config-modal").classList.add("active");
    document.querySelector(".sidebar").classList.remove("open");
}

function closeConfigModal() {
    document.getElementById("config-modal").classList.remove("active");
}

function toggleApiKeyVisibility() {
    const keyInput = document.getElementById("config-api-key");
    const eyeIcon = document.getElementById("eye-icon");
    if (keyInput.type === "password") {
        keyInput.type = "text";
        eyeIcon.className = "fa-regular fa-eye-slash";
    } else {
        keyInput.type = "password";
        eyeIcon.className = "fa-regular fa-eye";
    }
}

function showConfigStatus(message, className) {
    const statusMsg = document.getElementById("config-status-msg");
    statusMsg.style.display = "block";
    statusMsg.className = className || "";
    statusMsg.innerText = message;
}

function buildModelOptions(freeModels, allModels) {
    const select = document.getElementById("config-model");
    if (!select) return;

    select.innerHTML = "";

    const addGroup = (label, models) => {
        if (!models || !models.length) return;
        const group = document.createElement("optgroup");
        group.label = label;
        models.forEach(model => {
            const option = document.createElement("option");
            option.value = model.id;
            option.textContent = `${model.name || model.id}${model.free ? " • FREE" : ""}`;
            option.title = model.description || model.id;
            group.appendChild(option);
        });
        select.appendChild(group);
    };

    const freeRouter = {
        id: "openrouter/free",
        name: "OpenRouter Free Router",
        free: true
    };
    addGroup("Recommended Free Models", [freeRouter, ...(freeModels || [])]);

    const freeIds = new Set((freeModels || []).map(m => m.id));
    addGroup("All Available Models", (allModels || []).filter(m => !freeIds.has(m.id)));

    const found = [...select.options].some(option => option.value === selectedModelId);
    if (!found && selectedModelId) {
        const fallback = document.createElement("option");
        fallback.value = selectedModelId;
        fallback.textContent = selectedModelId;
        fallback.selected = true;
        select.appendChild(fallback);
    }

    select.value = selectedModelId || "openrouter/free";
}

async function loadModelCatalog() {
    const select = document.getElementById("config-model");
    if (select) {
        select.innerHTML = '<option>Loading current OpenRouter models...</option>';
    }

    try {
        const res = await fetch("/api/config/models");
        const data = await res.json();
        if (!res.ok && !data.free_models) {
            throw new Error(data.error || "Could not load models.");
        }
        availableModels = [...(data.free_models || []), ...(data.all_models || [])];
        buildModelOptions(data.free_models || [], data.all_models || []);
    } catch (err) {
        if (select) {
            select.innerHTML = "";
            const option = document.createElement("option");
            option.value = "openrouter/free";
            option.textContent = "OpenRouter Free Router";
            select.appendChild(option);
            select.value = selectedModelId || "openrouter/free";
        }
        showConfigStatus(err.message || "Could not load the current model list.", "status-error");
    }
}

function filterModelOptions() {
    const query = (document.getElementById("config-model-search").value || "").trim().toLowerCase();
    const select = document.getElementById("config-model");
    if (!select) return;

    Array.from(select.options).forEach(option => {
        const matches = !query || option.textContent.toLowerCase().includes(query) || option.value.toLowerCase().includes(query);
        option.hidden = !matches;
    });
}

async function validatePersonalKey() {
    const apiKey = document.getElementById("config-api-key").value.trim();
    if (!apiKey) {
        showConfigStatus("Enter your personal OpenRouter API key first.", "status-error");
        return;
    }

    const btn = document.getElementById("validate-key-btn");
    btn.disabled = true;
    showConfigStatus("Validating your key with OpenRouter...", "status-loading");

    try {
        const res = await fetch("/api/config/validate-key", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({api_key: apiKey})
        });
        const data = await res.json();

        if (res.ok && data.status === "success") {
            showConfigStatus(data.message, "status-success");
            await loadModelCatalog();
        } else {
            showConfigStatus(data.message || "Invalid OpenRouter API key.", "status-error");
        }
    } catch (err) {
        showConfigStatus("Could not validate the key.", "status-error");
    } finally {
        btn.disabled = false;
    }
}

async function removePersonalKey() {
    if (!confirm("Remove your personal OpenRouter API key and return to the server default?")) return;

    const btn = document.getElementById("remove-key-btn");
    btn.disabled = true;

    try {
        const res = await fetch("/api/config/key", {method: "DELETE"});
        const data = await res.json();

        if (!res.ok) {
            showConfigStatus(data.error || data.message || "Could not remove the personal key.", "status-error");
            return;
        }

        document.getElementById("config-api-key").value = "";
        document.getElementById("personal-key-status").innerText = "Personal key removed. Using the default server key.";
        document.getElementById("config-access-status").innerText = "Using default server key";
        selectedModelId = document.getElementById("config-model").value || selectedModelId;
        showConfigStatus(data.message, "status-success");
        await loadModelCatalog();
    } catch (err) {
        showConfigStatus("Could not remove the personal key.", "status-error");
    } finally {
        btn.disabled = false;
    }
}

async function saveConfig() {
    const apiKey = document.getElementById("config-api-key").value.trim();
    const model = document.getElementById("config-model").value.trim();
    const saveBtn = document.getElementById("save-config-btn");

    if (!model) {
        showConfigStatus("Please select a model.", "status-error");
        return;
    }

    saveBtn.disabled = true;
    showConfigStatus("Saving settings...", "status-loading");

    try {
        const payload = {model: model};
        // An empty field means "keep the existing personal key"; a newly
        // entered value replaces it. Removing is handled by the Remove button.
        if (apiKey) payload.api_key = apiKey;

        const res = await fetch("/api/config", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (res.ok && data.status === "success") {
            selectedModelId = model;
            showConfigStatus(data.message, "status-success");
            document.getElementById("config-api-key").value = "";
            setTimeout(() => {
                closeConfigModal();
                saveBtn.disabled = false;
            }, 900);
        } else {
            showConfigStatus(data.message || "Failed to update settings.", "status-error");
            saveBtn.disabled = false;
        }
    } catch (err) {
        showConfigStatus("Error communicating with server.", "status-error");
        saveBtn.disabled = false;
    }
}

function escapeHTML(str) {
    if (!str) return "";
    return str.replace(/[&<>'"]/g, tag => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[tag] || tag));
}

/* =========================================
   DARK / LIGHT MODE
   ========================================= */

function setTheme(theme) {
    const body = document.body;
    const themeIcon = document.getElementById("theme-icon");
    const themeToggle = document.getElementById("theme-toggle");

    if (theme === "light") {
        body.classList.remove("dark-theme");
        body.classList.add("light-theme");

        if (themeIcon) {
            themeIcon.className = "fa-solid fa-moon";
        }

        if (themeToggle) {
            themeToggle.title = "Switch to dark mode";
        }

        localStorage.setItem("mca-ai-theme", "light");
    } else {
        body.classList.remove("light-theme");
        body.classList.add("dark-theme");

        if (themeIcon) {
            themeIcon.className = "fa-solid fa-sun";
        }

        if (themeToggle) {
            themeToggle.title = "Switch to light mode";
        }

        localStorage.setItem("mca-ai-theme", "dark");
    }
}


function toggleTheme() {
    const body = document.body;

    if (body.classList.contains("dark-theme")) {
        setTheme("light");
    } else {
        setTheme("dark");
    }
}


/* Load saved theme when page opens */
document.addEventListener("DOMContentLoaded", function () {
    const savedTheme = localStorage.getItem("mca-ai-theme");

    if (savedTheme === "light") {
        setTheme("light");
    } else {
        setTheme("dark");
    }
});
