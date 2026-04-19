// ===== NAVBAR SCROLL =====
const navbar = document.getElementById('navbar');

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    if (currentScroll > 50) navbar?.classList.add('scrolled');
    else navbar?.classList.remove('scrolled');
});

// ===== MOBILE MENU =====
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const mobileMenu = document.getElementById('mobileMenu');

if (mobileMenuBtn && mobileMenu) {
    mobileMenuBtn.addEventListener('click', () => {
        mobileMenu.classList.toggle('active');
        mobileMenuBtn.classList.toggle('active');
    });
}

function closeMobileMenu() {
    if (mobileMenu) mobileMenu.classList.remove('active');
    if (mobileMenuBtn) mobileMenuBtn.classList.remove('active');
}

// ===== SCROLL TO SECTION =====
function scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// ===== HERO TIMER =====
let heroTimerSeconds = 45 * 60;
function updateHeroTimer() {
    const hours = Math.floor(heroTimerSeconds / 3600);
    const minutes = Math.floor((heroTimerSeconds % 3600) / 60);
    const seconds = heroTimerSeconds % 60;
    document.getElementById('timer-hours').textContent = String(hours).padStart(2, '0');
    document.getElementById('timer-minutes').textContent = String(minutes).padStart(2, '0');
    document.getElementById('timer-seconds').textContent = String(seconds).padStart(2, '0');
    heroTimerSeconds = heroTimerSeconds > 0 ? heroTimerSeconds - 1 : 45 * 60;
}
setInterval(updateHeroTimer, 1000);
updateHeroTimer();

// ===== FREE MIXERS COUNTER =====
let freeMixers = 3;
function updateFreeMixers() {
    const rand = Math.random();
    if (rand < 0.3 && freeMixers > 1) freeMixers--;
    else if (rand > 0.9 && freeMixers < 5) freeMixers++;

    const heroEl = document.getElementById('free-mixers-hero');
    const urgencyEl = document.getElementById('free-mixers-urgency');
    if (heroEl) heroEl.textContent = freeMixers;
    if (urgencyEl) urgencyEl.textContent = freeMixers;
}
setInterval(updateFreeMixers, 30000);

// ===== WORKDAY TIMER =====
function updateWorkdayTimer() {
    const now = new Date();
    const endOfDay = new Date(now);
    endOfDay.setHours(22, 0, 0, 0);
    if (now >= endOfDay) endOfDay.setDate(endOfDay.getDate() + 1);

    const diff = endOfDay - now;
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((diff % (1000 * 60)) / 1000);
    const el = document.getElementById('workday-timer');
    if (el) {
        el.textContent = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
}
setInterval(updateWorkdayTimer, 1000);
updateWorkdayTimer();

// ===== CALCULATOR =====
function switchCalcTab(tab) {
    document.querySelectorAll('.calc-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    document.querySelectorAll('.calc-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(`panel-${tab}`)?.classList.add('active');
    if (tab === 'plate') calcPlate();
    else if (tab === 'strip') calcStrip();
    else if (tab === 'cylinder') calcCylinder();
}

function calcPlate() {
    const l = parseFloat(document.getElementById('plate-l').value) || 0;
    const w = parseFloat(document.getElementById('plate-w').value) || 0;
    const h = parseFloat(document.getElementById('plate-h').value) || 0;
    updateCalcResult(l * w * h);
}

function calcStrip() {
    const p = parseFloat(document.getElementById('strip-p').value) || 0;
    const w = parseFloat(document.getElementById('strip-w').value) || 0;
    const h = parseFloat(document.getElementById('strip-h').value) || 0;
    updateCalcResult(p * w * h);
}

function calcCylinder() {
    const r = parseFloat(document.getElementById('cyl-r').value) || 0;
    const h = parseFloat(document.getElementById('cyl-h').value) || 0;
    updateCalcResult(Math.PI * r * r * h);
}

function updateCalcResult(volume) {
    const resultEl = document.getElementById('calc-result');
    if (!resultEl) return;
    if (volume <= 0) {
        resultEl.style.display = 'none';
        return;
    }

    const roundedVolume = Math.ceil(volume * 100) / 100;
    const price = Math.round(roundedVolume * 5800);
    document.getElementById('calc-volume').textContent = roundedVolume;
    document.getElementById('calc-price').textContent = price.toLocaleString('ru-RU');
    resultEl.style.display = 'block';
}

// ===== UI ANIMATIONS =====
function animateTrustCounters() {
    document.querySelectorAll('.trust-number[data-target]').forEach(counter => {
        const target = parseInt(counter.dataset.target, 10);
        const duration = 2000;
        const step = target / (duration / 16);
        let current = 0;

        function update() {
            current += step;
            if (current < target) {
                counter.textContent = Math.floor(current).toLocaleString('ru-RU');
                requestAnimationFrame(update);
            } else {
                counter.textContent = target.toLocaleString('ru-RU');
            }
        }
        update();
    });
}

const observerOptions = { threshold: 0.2, rootMargin: '0px 0px -50px 0px' };
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            if (entry.target.id === 'trust') animateTrustCounters();
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));
document.getElementById('trust') && observer.observe(document.getElementById('trust'));

const floatingCta = document.getElementById('floatingCta');
window.addEventListener('scroll', () => {
    if (window.pageYOffset > 500) floatingCta?.classList.add('visible');
    else floatingCta?.classList.remove('visible');
});

function animateMixerCount() {
    const el = document.getElementById('mixer-count-display');
    if (!el) return;
    const mixerCount = 30;
    const duration = 2000;
    const step = mixerCount / (duration / 16);
    let current = 0;

    function update() {
        current += step;
        if (current < mixerCount) {
            el.textContent = Math.floor(current);
            requestAnimationFrame(update);
        } else {
            el.textContent = mixerCount;
        }
    }
    update();
}

const solutionSection = document.getElementById('solution');
if (solutionSection) {
    const solutionObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateMixerCount();
                solutionObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });
    solutionObserver.observe(solutionSection);
}

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = this.getAttribute('href').substring(1);
        scrollToSection(targetId);
    });
});

document.addEventListener('DOMContentLoaded', () => switchCalcTab('plate'));

// ===== FORM SUBMISSION =====
const speedForm = document.getElementById('speedForm');
let API_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://beton-backend-kwa9.onrender.com';

function normalizePhone(phone) {
    const digits = String(phone || '').replace(/\D/g, '');
    if (!digits) return '';
    if (digits.length === 11 && digits.startsWith('8')) return '+7' + digits.slice(1);
    if (digits.length === 11 && digits.startsWith('7')) return '+' + digits;
    if (digits.length === 10) return '+7' + digits;
    return phone;
}

fetch(`${API_URL}/api/config`).then(r => r.ok ? r.json() : null).then(cfg => {
    if (cfg && cfg.api_url) API_URL = cfg.api_url;
}).catch(() => {});

if (speedForm) {
    speedForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(speedForm);
        const data = Object.fromEntries(formData.entries());
        const submitBtn = speedForm.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="btn-icon">⏳</span> Отправка...';

        try {
            const response = await fetch(`${API_URL}/api/leads/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: data.name,
                    phone: normalizePhone(data.phone),
                    concrete_grade: data.concrete_grade || 'М200',
                    volume: parseFloat(data.volume) || 5,
                    source: 'landing-speed'
                })
            });

            const result = await response.json().catch(() => ({}));
            if (response.ok && (result.status === 'success' || result.status === 'duplicate')) {
                alert('✅ Заявка принята! Перезвоним за 5 минут.');
                speedForm.reset();
            } else {
                alert('Ошибка: ' + (result.message || result.detail || 'Не удалось отправить заявку.'));
            }
        } catch (err) {
            console.error('Ошибка отправки:', err);
            alert('Ошибка соединения. Попробуйте позже или позвоните нам.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    });
}

const speedPhone = speedForm?.querySelector('input[name="phone"]');
if (speedPhone) {
    speedPhone.addEventListener('input', function (e) {
        let val = e.target.value.replace(/\D/g, '');
        if (val.length > 0) {
            if (val[0] === '7' || val[0] === '8') val = val.substring(1);
            let formatted = '+7';
            if (val.length > 0) formatted += ' (' + val.substring(0, 3);
            if (val.length >= 3) formatted += ') ' + val.substring(3, 6);
            if (val.length >= 6) formatted += '-' + val.substring(6, 8);
            if (val.length >= 8) formatted += '-' + val.substring(8, 10);
            e.target.value = formatted;
        }
    });
}
