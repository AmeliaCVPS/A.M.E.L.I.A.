// voice.js
/**
 * Módulo de Interface de Voz do sistema AMÉLIA
 * 
 * Usa a Web Speech API (nativa dos navegadores modernos).
 * Vantagem: gratuita, sem latência de rede para transcrição.
 * Limitação: qualidade varia por navegador (Chrome = melhor suporte).
 * 
 * Alternativa pro: Google Cloud Speech-to-Text (mais precisa, paga).
 */

// ===========================================================
// CONFIGURAÇÃO
// ===========================================================

// No voice.js
const API_BASE_URL = window.location.hostname === "localhost" 
    ? "http://localhost:8000" 
    : "/api";  // URL do backend FastAPI

// Estado do módulo de voz
const voiceState = {
    isRecording:   false,
    recognition:   null,   // Instância do reconhecimento de voz
    synthesis:     window.speechSynthesis,  // TTS nativo do browser
    transcript:    "",     // Texto acumulado da fala
    currentUser:   null,   // Dados do usuário logado
};


// ===========================================================
// VERIFICAÇÃO DE SUPORTE
// ===========================================================

function checkBrowserSupport() {
    const hasSTT = 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window;
    const hasTTS = 'speechSynthesis' in window;

    if (!hasSTT) {
        showToast("⚠️ Seu navegador não suporta reconhecimento de voz. Use Chrome.", "warning");
        return false;
    }
    if (!hasTTS) {
        showToast("⚠️ Síntese de voz não disponível.", "warning");
        return false;
    }
    return true;
}


// ===========================================================
// SÍNTESE DE VOZ (TEXTO → FALA)
// ===========================================================

/**
 * Transforma texto em fala.
 * @param {string} text - Texto a ser falado
 * @param {function} onEnd - Callback executado ao terminar
 */
function speak(text, onEnd = null) {
    // Cancelar qualquer fala em andamento
    voiceState.synthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang  = "pt-BR";   // Português brasileiro
    utterance.rate  = 0.9;        // Velocidade (0.1 a 10)
    utterance.pitch = 1.1;        // Tom de voz
    utterance.volume = 1.0;

    // Escolhe voz feminina em pt-BR se disponível
    const voices = voiceState.synthesis.getVoices();
    const ptVoice = voices.find(v =>
        v.lang.startsWith("pt") && v.name.toLowerCase().includes("female")
    ) || voices.find(v => v.lang.startsWith("pt"));

    if (ptVoice) utterance.voice = ptVoice;

    if (onEnd) utterance.onend = onEnd;

    voiceState.synthesis.speak(utterance);
}


// ===========================================================
// RECONHECIMENTO DE VOZ (FALA → TEXTO)
// ===========================================================

/**
 * Inicializa o motor de reconhecimento de voz.
 */
function initSpeechRecognition() {
    const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;

    const recognition = new SpeechRecognition();
    recognition.lang            = "pt-BR";
    recognition.continuous      = true;   // Mantém ouvindo até pararmos
    recognition.interimResults  = true;   // Mostra resultado parcial em tempo real
    recognition.maxAlternatives = 1;

    // ---- EVENTOS ----

    recognition.onstart = () => {
        voiceState.isRecording = true;
        updateMicButton(true);
        showVoiceFeedback("🎙️ Ouvindo... fale agora");
    };

    recognition.onresult = (event) => {
        let interimTranscript = "";
        let finalTranscript   = "";

        // Processa todos os resultados recebidos
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const text = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += text;
            } else {
                interimTranscript += text;
            }
        }

        voiceState.transcript += finalTranscript;

        // Mostra texto em tempo real no chat
        updateLiveTranscript(voiceState.transcript + interimTranscript);
    };

    recognition.onerror = (event) => {
        console.error("Erro no reconhecimento:", event.error);
        const errorMessages = {
            "no-speech":      "Não detectei sua voz. Tente novamente.",
            "audio-capture":  "Não foi possível acessar o microfone.",
            "not-allowed":    "Permissão de microfone negada. Habilite nas configurações.",
            "network":        "Erro de rede. Verifique sua conexão.",
        };
        showToast(errorMessages[event.error] || "Erro no microfone.", "error");
        stopRecording();
    };

    recognition.onend = () => {
        // Se parou mas ainda deveria estar gravando → reinicia (modo contínuo)
        if (voiceState.isRecording) {
            recognition.start();
        }
    };

    return recognition;
}


// ===========================================================
// CONTROLE DE GRAVAÇÃO
// ===========================================================

function startRecording() {
    if (!checkBrowserSupport()) return;

    voiceState.transcript = "";
    voiceState.recognition = initSpeechRecognition();
    voiceState.recognition.start();
}

function stopRecording() {
    if (!voiceState.recognition) return;

    voiceState.isRecording = false;
    voiceState.recognition.stop();
    updateMicButton(false);
    showVoiceFeedback("✅ Gravação finalizada");
}

/**
 * Botão de toggle: inicia ou para a gravação.
 * Vinculado ao botão do microfone no HTML.
 */
function toggleRecording() {
    if (voiceState.isRecording) {
        stopRecording();
        // Após parar, processa o que foi dito
        if (voiceState.transcript.trim()) {
            processVoiceInput(voiceState.transcript);
        }
    } else {
        startRecording();
        // AMÉLIA orienta o paciente por voz
        speak("Por favor, descreva seus sintomas. Como você está se sentindo?");
    }
}


// ===========================================================
// PROCESSAMENTO E ENVIO PARA O BACKEND
// ===========================================================

/**
 * Envia o texto transcrito para a API e exibe o resultado.
 * @param {string} transcript - Texto falado pelo paciente
 */
async function processVoiceInput(transcript) {
    if (!transcript.trim()) {
        showToast("Nenhum áudio capturado.", "warning");
        return;
    }

    // Exibe mensagem do usuário no chat
    addUserMessage(transcript);
    showVoiceFeedback("⏳ Analisando seus sintomas...");

    try {
        // Envia para o endpoint de triagem por texto
        const response = await fetch(`${API_BASE_URL}/triage/from-text`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: transcript,
                cpf:  currentUser.cpf,
                age:  calculateAge(currentUser.nascimento),
                sex:  "M",  // Em produção: perguntar ao usuário
            }),
        });

        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }

        const result = await response.json();
        displayTriageResult(result);

    } catch (error) {
        console.error("Erro ao processar triagem:", error);
        showToast("Erro ao comunicar com o servidor. Tente novamente.", "error");
        addBotMessage("Desculpe, ocorreu um erro. Por favor, tente novamente.");
    }
}


/**
 * Exibe o resultado da triagem no chat e o lê em voz alta.
 */
function displayTriageResult(result) {
    const { password, classification } = result;

    const colorEmoji = {
        red:    "🔴",
        yellow: "🟡",
        green:  "🟢"
    };

    const messageHTML = `
        ${colorEmoji[classification.color]} <strong>${classification.explanation}</strong><br><br>
        Sua senha de atendimento é: 
        <span style="font-size:1.5em; font-weight:bold; color:var(--primary-blue);">
            ${password}
        </span><br>
        <small>Confiança do modelo: ${(classification.confidence * 100).toFixed(1)}%</small>
    `;

    addBotMessage(messageHTML);

    // Fala o resultado (acessibilidade!)
    speak(
        `Triagem concluída. ${classification.explanation} ` +
        `Sua senha é ${password.split("").join(" ")}.`
    );

    // Salva dados para geração do PDF
    chatData.password       = password;
    chatData.classification = classification.color.toUpperCase()[0];

    // Exibe botões de ação
    document.getElementById("chat-input-area").style.display = "none";
    document.getElementById("chat-actions").style.display    = "flex";
}


// ===========================================================
// ATUALIZAÇÃO DA INTERFACE
// ===========================================================

function updateMicButton(isRecording) {
    const btn = document.getElementById("btn-voice");
    if (!btn) return;

    if (isRecording) {
        btn.innerHTML  = "🔴 Parar";
        btn.classList.add("recording");
    } else {
        btn.innerHTML  = "🎙️ Falar";
        btn.classList.remove("recording");
    }
}

function showVoiceFeedback(message) {
    const feedback = document.getElementById("voice-feedback");
    if (feedback) feedback.textContent = message;
}

function updateLiveTranscript(text) {
    const input = document.getElementById("chat-input");
    if (input) input.value = text;
}

function calculateAge(birthDateStr) {
    const birth = new Date(birthDateStr);
    const today = new Date();
    let age = today.getFullYear() - birth.getFullYear();
    if (today < new Date(today.getFullYear(), birth.getMonth(), birth.getDate())) {
        age--;
    }
    return age;
}