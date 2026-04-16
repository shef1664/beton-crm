document.addEventListener('DOMContentLoaded', () => {

    // ===== CALCULATOR LOGIC =====
    const calcState = {
        tab: 'volume',
        shape: 'plate',
        volume: 0,
        area: 0,
        mixers: 0,
        total: 0
    };

    // DOM references
    const gradeSelect = document.getElementById('concrete-grade');
    const resultVolume = document.getElementById('result-volume');
    const resultArea = document.getElementById('result-area');
    const resultMixers = document.getElementById('result-mixers');
    const resultTotal = document.getElementById('result-total');

    // ---- Tabs ----
    document.querySelectorAll('.calc-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.calc-tab').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.calc-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            calcState.tab = btn.dataset.tab;
            document.getElementById('panel-' + calcState.tab).classList.add('active');
            recalc();
        });
    });

    // ---- Shapes ----
    document.querySelectorAll('.shape-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.shape-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.calc-form').forEach(f => f.style.display = 'none');
            btn.classList.add('active');
            calcState.shape = btn.dataset.shape;
            document.getElementById('form-' + calcState.shape).style.display = 'flex';
            recalc();
        });
    });

    // ---- Input listeners ----
    const allInputs = document.querySelectorAll('.calculator-card input[type="number"]');
    allInputs.forEach(input => {
        input.addEventListener('input', recalc);
    });

    gradeSelect.addEventListener('change', recalc);

    // ---- Calculation engine ----
    function getVal(id) {
        const el = document.getElementById(id);
        return el ? parseFloat(el.value) || 0 : 0;
    }

    function recalc() {
        let volume = 0;
        let area = 0;
        let mixers = 0;

        if (calcState.tab === 'volume') {
            if (calcState.shape === 'plate') {
                const l = getVal('plate-length');
                const w = getVal('plate-width');
                const h = getVal('plate-height');
                volume = l * w * h;
            } else if (calcState.shape === 'ribbon') {
                const p = getVal('ribbon-perimeter');
                const w = getVal('ribbon-width');
                const h = getVal('ribbon-height');
                volume = p * w * h;
            } else if (calcState.shape === 'cylinder-v') {
                const r = getVal('cyl-v-radius');
                const h = getVal('cyl-v-height');
                volume = Math.PI * r * r * h;
            }
        } else if (calcState.tab === 'cylinder') {
            const r = getVal('cyl-radius');
            const h = getVal('cyl-height');
            area = 2 * Math.PI * r * h;
            // Also compute volume for completeness
            volume = Math.PI * r * r * h;
        } else if (calcState.tab === 'mixers') {
            volume = getVal('mixers-volume');
        }

        if (volume > 0) {
            mixers = Math.ceil(volume / 7);
        }

        const pricePerCube = parseFloat(gradeSelect.value) || 0;
        const total = Math.round(volume * pricePerCube);

        calcState.volume = volume;
        calcState.area = area;
        calcState.mixers = mixers;
        calcState.total = total;

        renderResults();
    }

    function renderResults() {
        resultVolume.textContent = formatNum(calcState.volume, 2) + ' м³';
        resultArea.textContent = formatNum(calcState.area, 2) + ' м²';
        resultMixers.textContent = calcState.mixers > 0 ? calcState.mixers + ' шт' : '0 шт';
        resultTotal.textContent = calcState.total > 0 ? formatPrice(calcState.total) + ' ₽' : '0 ₽';
    }

    function formatNum(num, decimals) {
        if (num === 0) return '0';
        return num.toFixed(decimals).replace(/\.?0+$/, '').replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    }

    function formatPrice(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    }

    // ---- CTA form submission ----
    const ctaForm = document.getElementById('cta-form');

    // API URL для отправки лидов
    const API_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? 'http://localhost:8000'
        : 'https://beton-backend-kwa9.onrender.com';

    // ---- Телефонная маска ----
    const phoneInput = ctaForm ? ctaForm.querySelector('input[name="phone"]') : null;
    if (phoneInput) {
        phoneInput.addEventListener('input', (e) => {
            let val = e.target.value.replace(/[^\d+]/g, '');
            if (val.length === 1 && val !== '+') {
                if (val === '8') val = '+7';
                else if (val === '7') val = '+7';
                else val = '+7' + val;
            }
            e.target.value = val;
        });
        phoneInput.placeholder = '+7 999 123-45-67';
    }

    // Убирать ошибку при вводе
    if (ctaForm) {
        ctaForm.querySelectorAll('input, select').forEach(el => {
            el.addEventListener('input', () => clearFieldError(el));
            el.addEventListener('change', () => clearFieldError(el));
        });
    }

    // ---- Валидация ----
    function validatePhone(phone) {
        const cleaned = phone.replace(/[\s\-\(\)]/g, '');
        return /^(\+7|8|7)\d{10}$/.test(cleaned);
    }

    function validateName(name) {
        const t = name.trim();
        if (t.length < 2) return 'Имя слишком короткое';
        if (t.length > 50) return 'Имя слишком длинное';
        if (!/^[а-яА-ЯёЁa-zA-Z\s\-]+$/.test(t)) return 'Только буквы и дефис';
        return null;
    }

    function formatPhone(phone) {
        const d = phone.replace(/\D/g, '');
        if (d.startsWith('8') && d.length === 11) return '+7' + d.slice(1);
        if (d.startsWith('7') && d.length === 11) return '+' + d;
        if (d.length === 10) return '+7' + d;
        return phone;
    }

    function showFieldError(input, message) {
        clearFieldError(input);
        input.classList.add('input-error');
        const div = document.createElement('div');
        div.className = 'field-error-msg';
        div.textContent = message;
        input.parentNode.insertBefore(div, input.nextSibling);
    }

    function clearFieldError(input) {
        input.classList.remove('input-error');
        const msg = input.parentNode.querySelector('.field-error-msg');
        if (msg) msg.remove();
    }

    function showFormMessage(form, type, text) {
        removeFormMessages(form);
        const div = document.createElement('div');
        div.className = type === 'success' ? 'form-msg form-msg--success' : 'form-msg form-msg--error';
        div.textContent = text;
        form.appendChild(div);
        div.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(() => {
            div.style.opacity = '0';
            div.style.transition = 'opacity 0.5s';
            setTimeout(() => div.remove(), 500);
        }, 10000);
    }

    function removeFormMessages(form) {
        form.querySelectorAll('.form-msg').forEach(el => el.remove());
    }

    if (ctaForm) {
        ctaForm.setAttribute('novalidate', '');
        ctaForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const nameInput  = ctaForm.querySelector('input[name="name"]');
            const phoneInput = ctaForm.querySelector('input[name="phone"]');
            const gradeInput = ctaForm.querySelector('select[name="grade"]');

            const name  = nameInput  ? nameInput.value  : '';
            const phone = phoneInput ? phoneInput.value : '';
            const grade = gradeInput ? gradeInput.value : 'М200';

            // -- Валидация --
            let hasError = false;

            const nameError = validateName(name);
            if (nameError) {
                showFieldError(nameInput, nameError);
                hasError = true;
            }

            if (!phone || !validatePhone(phone)) {
                showFieldError(phoneInput, 'Введите корректный номер (+7 999 123-45-67)');
                hasError = true;
            }

            if (hasError) {
                ctaForm.querySelector('.input-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                return;
            }

            // -- Отправка --
            removeFormMessages(ctaForm);
            const submitBtn = ctaForm.querySelector('button[type="submit"]');
            const originalText = submitBtn.textContent;
            submitBtn.disabled = true;
            submitBtn.textContent = 'Отправка...';

            const payload = {
                name: name.trim(),
                phone: formatPhone(phone),
                concrete_grade: grade || 'М200',
                volume: calcState.volume > 0 ? parseFloat(calcState.volume.toFixed(2)) : 5,
                calculated_amount: calcState.total > 0 ? calcState.total : null,
                source: 'landing-calc'
            };

            try {
                const response = await fetch(`${API_URL}/api/leads/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    showFormMessage(ctaForm, 'success',
                        '✅ Заявка принята! Перезвоним за 5 минут.');
                    ctaForm.reset();
                } else {
                    const err = await response.json().catch(() => ({}));
                    showFormMessage(ctaForm, 'error',
                        '❌ ' + (err.detail || 'Ошибка сервера') + '. Позвоните: 8-903-916-40-40');
                }
            } catch (err) {
                console.error('Ошибка отправки:', err);
                showFormMessage(ctaForm, 'error',
                    '❌ Нет связи с сервером. Позвоните: 8-903-916-40-40');
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = originalText;
            }
        });
    }

    // ===== URGENCY TIMER =====
    function initUrgencyTimer() {
        const timerEl = document.getElementById('urgency-timer');
        if (!timerEl) return;

        // Find next Sunday midnight
        function getEndOfWeek() {
            const now = new Date();
            const dayOfWeek = now.getDay(); // 0=Sun, 6=Sat
            const daysUntilSunday = dayOfWeek === 0 ? 0 : 7 - dayOfWeek;
            const end = new Date(now);
            end.setDate(now.getDate() + daysUntilSunday);
            end.setHours(23, 59, 59, 0);
            return end;
        }

        const deadline = getEndOfWeek();

        function updateTimer() {
            const now = new Date();
            const diff = deadline - now;

            if (diff <= 0) {
                document.getElementById('timer-days').textContent = '0';
                document.getElementById('timer-hours').textContent = '0';
                document.getElementById('timer-mins').textContent = '0';
                return;
            }

            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

            document.getElementById('timer-days').textContent = days;
            document.getElementById('timer-hours').textContent = hours;
            document.getElementById('timer-mins').textContent = mins;
        }

        updateTimer();
        setInterval(updateTimer, 60000); // update every minute
    }

    initUrgencyTimer();

    // ===== MOBILE MENU =====
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const nav = document.querySelector('.nav');

    if (mobileMenuBtn && nav) {
        mobileMenuBtn.addEventListener('click', () => {
            const isVisible = nav.style.display === 'flex';
            nav.style.display = isVisible ? 'none' : 'flex';
            nav.style.flexDirection = 'column';
            nav.style.position = 'absolute';
            nav.style.top = '100%';
            nav.style.left = '0';
            nav.style.right = '0';
            nav.style.background = '#111';
            nav.style.padding = '16px 20px';
            nav.style.gap = '12px';
            nav.style.borderTop = '3px solid #fbbf24';

            if (isVisible) {
                nav.style.position = '';
                nav.style.top = '';
                nav.style.left = '';
                nav.style.right = '';
                nav.style.background = '';
                nav.style.padding = '';
                nav.style.gap = '';
                nav.style.borderTop = '';
            }
        });
    }

    // ===== SMOOTH SCROLL for nav links =====
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                // Close mobile menu if open
                if (nav && window.innerWidth <= 992) {
                    nav.style.display = 'none';
                }
            }
        });
    });

});
