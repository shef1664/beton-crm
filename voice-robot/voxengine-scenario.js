/**
 * voxengine-scenario.js — Бетон42 голосовой бот для Voximplant.
 * МАРИЯ — консультант со звуком (Eleven Labs Bella).
 *
 * Стек: SIP-приём (Voximplant) → Yandex SpeechKit STT → Claude AI → Eleven Labs TTS → наш backend.
 *
 * Деплой: загрузить как Scenario в Voximplant Application,
 * привязать к Routing Rule SIP-номера.
 *
 * Переменные окружения (Voximplant Application properties):
 *   BACKEND_URL          — https://beton-backend-wr3w.onrender.com/api/voice/maria
 *   YANDEX_API_KEY       — API key Yandex SpeechKit
 *   YANDEX_FOLDER_ID     — folder id Yandex Cloud
 *   MANAGER_PHONE        — номер менеджера для передачи (8 903 916 40 40)
 */

require(Modules.ASR);
require(Modules.Player);

const CONFIG = {
    BACKEND_URL: customValue("BACKEND_URL", "backendUrl") || "https://beton42-maria-voice.onrender.com/api/voice/maria",
    YANDEX_API_KEY: customValue("YANDEX_API_KEY", "yandexApiKey") || "",
    YANDEX_FOLDER_ID: customValue("YANDEX_FOLDER_ID", "yandexFolderId") || "",
    ELEVENLABS_API_KEY: customValue("ELEVENLABS_API_KEY", "elevenLabsApiKey") || "",
    ELEVENLABS_VOICE_ID: customValue("ELEVENLABS_VOICE_ID", "elevenLabsVoiceId") || "EXAVITQu4vr4xnSDxMaL",  // Bella
    MANAGER_PHONE: customValue("MANAGER_PHONE", "managerPhone") || "89039164040",
    MAX_TURNS: 12,
    SILENCE_MS: 4000,
    TURN_TIMEOUT_MS: 30000,
};

const STATE = {
    call: null,
    chatId: null,        // уникальный id для backend (call uuid)
    turnCount: 0,
    history: [],         // {from: 'bot'|'client', text}
    consentGiven: false,
};

const FIRST_LINE = (
    "Добрый день! Компания Бетон42. " +
    "Сколько кубов бетона вам нужно и какая марка?"
);

const FALLBACK_LINE = (
    "Извините, не расслышал. Соединяю с менеджером."
);

function customValue(upperName, camelName) {
    const data = VoxEngine.customData ? VoxEngine.customData() : {};
    return data?.[upperName] || data?.[camelName] || "";
}

VoxEngine.addEventListener(AppEvents.CallAlerting, (e) => {
    STATE.call = e.call;
    STATE.chatId = e.call.callerid() + "-" + Date.now();
    e.call.answer();
});

VoxEngine.addEventListener(AppEvents.Connected, () => {
    say(FIRST_LINE).then(() => listenClient());
});

VoxEngine.addEventListener(AppEvents.Disconnected, () => {
    reportToBackend({ event: "call_end", history: STATE.history });
    VoxEngine.terminate();
});

/* ---------- Helpers ---------- */

async function say(text) {
    STATE.history.push({ from: "bot", text });

    // Eleven Labs TTS (Bella voice)
    if (CONFIG.ELEVENLABS_API_KEY) {
        const audioUrl = await getElevenLabsAudio(text);
        if (audioUrl) {
            STATE.call.startPlayback(audioUrl, false);
            await waitEvent(CallEvents.PlaybackFinished);
            return;
        }
    }

    // Fallback: встроенный TTS Voximplant
    if (CONFIG.YANDEX_API_KEY) {
        const url = "https://tts.api.cloud.yandex.net/speech/v1/synthesize";
        const params = new URLSearchParams({
            text, lang: "ru-RU", voice: "alena", emotion: "neutral", format: "lpcm", sampleRateHertz: "48000",
            folderId: CONFIG.YANDEX_FOLDER_ID,
        });
        const audioUrl = url + "?" + params.toString();
        STATE.call.startPlayback(audioUrl, false, {
            Headers: { "Authorization": "Api-Key " + CONFIG.YANDEX_API_KEY },
        });
        await waitEvent(CallEvents.PlaybackFinished);
        return;
    }

    // Last resort: встроенный голос Voximplant
    STATE.call.say(text, { language: VoiceList.Yandex.ru_RU_Female });
    await waitEvent(CallEvents.PlaybackFinished);
}

async function getElevenLabsAudio(text) {
    try {
        const resp = await Net.httpRequestAsync(
            "https://api.elevenlabs.io/v1/text-to-speech/" + CONFIG.ELEVENLABS_VOICE_ID,
            {
                method: "POST",
                headers: [
                    "Content-Type: application/json",
                    "xi-api-key: " + CONFIG.ELEVENLABS_API_KEY
                ],
                postData: JSON.stringify({
                    text: text,
                    model_id: "eleven_multilingual_v2",
                    voice_settings: {
                        stability: 0.55,
                        similarity_boost: 0.75,
                        style: 0.10,
                        use_speaker_boost: true
                    }
                }),
                timeout: 10,
            }
        );
        if (resp.code === 200) {
            // resp.body содержит MP3 данные
            // Нужно загрузить на хранилище и вернуть публичный URL
            const audioBase64 = resp.body;
            // TODO: загрузить в Cloudflare R2 и вернуть URL
            // На данный момент возвращаем как data URI (не рекомендуется для большых файлов)
            return "data:audio/mpeg;base64," + audioBase64;
        }
    } catch (e) {
        Logger.write("Eleven Labs error: " + e);
    }
    return null;
}

async function listenClient() {
    if (STATE.turnCount >= CONFIG.MAX_TURNS) {
        await say("Извините, я не могу больше помочь. Передаю менеджеру.");
        transferToHuman();
        return;
    }
    STATE.turnCount++;

    const asr = VoxEngine.createASR({
        profile: ASRProfileList.Yandex.ru_RU,
        singleUtterance: true,
        interimResults: false,
    });
    STATE.call.sendMediaTo(asr);

    const timer = setTimeout(() => {
        try { asr.stop(); } catch (e) {}
    }, CONFIG.TURN_TIMEOUT_MS);

    asr.addEventListener(ASREvents.Result, async (ev) => {
        clearTimeout(timer);
        const clientText = (ev.text || "").trim();
        STATE.history.push({ from: "client", text: clientText });
        if (!clientText) {
            await say(FALLBACK_LINE);
            transferToHuman();
            return;
        }
        const reply = await askBackend(clientText);
        if (reply.transfer) {
            const transferLine = reply.text || "Спасибо, давайте я подключу менеджера.";
            await say(transferLine);
            transferToHuman(reply.transfer_phone);
            return;
        }
        if (reply.hangup) {
            await say(reply.text || "Спасибо. До свидания.");
            STATE.call.hangup();
            return;
        }
        await say(reply.text || "Минуту, проверяю.");
        listenClient();
    });
    asr.addEventListener(ASREvents.Error, () => {
        clearTimeout(timer);
        listenClient();
    });
}

async function askBackend(clientText) {
    try {
        const resp = await Net.httpRequestAsync(CONFIG.BACKEND_URL, {
            method: "POST",
            headers: ["Content-Type: application/json"],
            postData: JSON.stringify({
                chat_id: STATE.chatId,
                text: clientText,
                history: STATE.history,
                caller: STATE.call.callerid(),
            }),
            timeout: 10,
        });
        if (resp.code === 200) {
            const reply = JSON.parse(resp.text);
            // Backend возвращает: { text, transfer_needed, transfer_phone, conversation_history }
            return {
                text: reply.text || reply.response_text || "",
                transfer: reply.transfer_needed || false,
                transfer_phone: reply.transfer_phone || CONFIG.MANAGER_PHONE,
            };
        }
    } catch (e) {
        Logger.write("backend error: " + e);
    }
    // Fallback на простой ответ
    return mockReply(clientText);
}

function mockReply(clientText) {
    const t = clientText.toLowerCase();
    if (/срочн|сейчас|сегодня/.test(t) || /менеджер|человек/.test(t)) {
        return { text: "Передаю заявку руководителю.", transfer: true };
    }
    if (/\d+\s*куб/.test(t)) {
        return { text: "Принял заявку. Сейчас перезвонит менеджер, посчитает стоимость." };
    }
    return { text: "Понял. Подскажите, пожалуйста, адрес и желаемое время доставки?" };
}

function transferToHuman(managerPhone) {
    const phoneToCall = managerPhone || CONFIG.MANAGER_PHONE;
    if (!phoneToCall) {
        STATE.call.hangup();
        return;
    }
    // Передаём с историей для менеджера
    reportToBackend({
        event: "transfer_to_manager",
        manager_phone: phoneToCall,
        history: STATE.history
    });
    const newCall = VoxEngine.callPSTN(phoneToCall, STATE.call.callerid());
    VoxEngine.easyProcess(STATE.call, newCall);
}

function reportToBackend(payload) {
    try {
        const eventUrl = CONFIG.BACKEND_URL.replace(/\/maria$/, "/event");
        Net.httpRequestAsync(eventUrl, {
            method: "POST",
            headers: ["Content-Type: application/json"],
            postData: JSON.stringify({ chat_id: STATE.chatId, ...payload }),
            timeout: 5,
        });
    } catch (e) {}
}

function waitEvent(eventName) {
    return new Promise((resolve) => {
        const handler = (e) => {
            STATE.call.removeEventListener(eventName, handler);
            resolve(e);
        };
        STATE.call.addEventListener(eventName, handler);
    });
}
