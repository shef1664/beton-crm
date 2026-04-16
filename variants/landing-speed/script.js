// ===== NAVBAR SCROLL =====
const navbar = document.getElementById('navbar');
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;
    if (currentScroll > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
    lastScroll = currentScroll;
});

// ===== MOBILE MENU =====
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const mobileMenu = document.getElementById('mobileMenu');

mobileMenuBtn.addEventListener('click', () => {
    mobileMenu.classList.toggle('active');
    mobileMenuBtn.classList.toggle('active');
});

function closeMobileMenu() {
    mobileMenu.classList.remove('active');
    mobileMenuBtn.classList.remove('active');
}

// ===== SCROLL TO SECTION =====
function scrollToSection(id) {
    const el = document.getElementById(id);
    if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// ===== HERO TIMER =====
let heroTimerSeconds = 45 * 60; // 45 minutes

function updateHeroTimer() {
    const hours = Math.floor(heroTimerSeconds / 3600);
    const minutes = Math.floor((heroTimerSeconds % 3600) / 60);
    const seconds = heroTimerSeconds % 60;

    document.getElementById('timer-hours').textContent = String(hours).padStart(2, '0');
    document.getElementById('timer-minutes').textContent = String(minutes).padStart(2, '0');
    document.getElementById('timer-seconds').textContent = String(seconds).padStart(2, '0');

    if (heroTimerSeconds > 0) {
        heroTimerSeconds--;
    } else {
        heroTimerSeconds = 45 * 60; // Reset
    }
}

setInterval(updateHeroTimer, 1000);
updateHeroTimer();

// ===== FREE MIXERS COUNTER =====
let freeMixers = 3;

function updateFreeMixers() {
    // Randomly decrease or occasionally increase
    const rand = Math.random();
    if (rand < 0.3 && freeMixers > 1) {
        freeMixers--;
    } else if (rand > 0.9 && freeMixers < 5) {
        freeMixers++;
    }

    const heroEl = document.getElementById('free-mixers-hero');
    const urgencyEl = document.getElementById('free-mixers-urgency');

    if (heroEl) heroEl.textContent = freeMixers;
    if (urgencyEl) urgencyEl.textContent = freeMixers;
}

setInterval(updateFreeMixers, 30000); // Every 30 seconds

// ===== WORKDAY TIMER =====
function updateWorkdayTimer() {
    const now = new Date();
    const endOfDay = new Date(now);
    endOfDay.setHours(22, 0, 0, 0); // 10 PM end of "work day"

    if (now >= endOfDay) {
        endOfDay.setDate(endOfDay.getDate() + 1);
    }

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
let currentCalcTab = 'plate';

function switchCalcTab(tab) {
    currentCalcTab = tab;

    // Update tabs
    document.querySelectorAll('.calc-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tab);
    });

    // Update panels
    document.querySelectorAll('.calc-panel').forEach(p => {
        p.classList.remove('active');
    });
    document.getElementById(`panel-${tab}`).classList.add('active');

    // Recalculate
    if (tab === 'plate') calcPlate();
    else if (tab === 'strip') calcStrip();
    else if (tab === 'cylinder') calcCylinder();
}

function calcPlate() {
    const l = parseFloat(document.getElementById('plate-l').value) || 0;
    const w = parseFloat(document.getElementById('plate-w').value) || 0;
    const h = parseFloat(document.getElementById('plate-h').value) || 0;

    const volume = l * w * h;
    updateCalcResult(volume);
}

function calcStrip() {
    const p = parseFloat(document.getElementById('strip-p').value) || 0;
    const w = parseFloat(document.getElementById('strip-w').value) || 0;
    const h = parseFloat(document.getElementById('strip-h').value) || 0;

    const volume = p * w * h;
    updateCalcResult(volume);
}

function calcCylinder() {
    const r = parseFloat(document.getElementById('cyl-r').value) || 0;
    const h = parseFloat(document.getElementById('cyl-h').value) || 0;

    const volume = Math.PI * r * r * h;
    updateCalcResult(volume);
}

function updateCalcResult(volume) {
    const resultEl = document.getElementById('calc-result');

    if (volume <= 0) {
        resultEl.style.display = 'none';
        return;
    }

    resultEl.style.display = 'block';

    // Round to 2 decimal places
    const roundedVolume = Math.ceil(volume * 100) / 100;
    const price = Math.round(roundedVolume * 5800);

    document.getElementById('calc-volume').textContent = roundedVolume;
    document.getElementById('calc-price').textContent = price.toLocaleString('ru-RU');
}

// ===== TRUST COUNTER ANIMATION =====
function animateTrustCounters() {
    const counters = document.querySelectorAll('.trust-number[data-target]');

    counters.forEach(counter => {
        const target = parseInt(counter.dataset.target);
        const duration = 2000; // 2 seconds
        const step = target / (duration / 16); // 60fps
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

// ===== INTERSECTION OBSERVER FOR ANIMATIONS =====
const observerOptions = {
    threshold: 0.2,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('visible');

            // Trigger trust counter animation
            if (entry.target.id === 'trust') {
                animateTrustCounters();
            }

            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Observe elements with fade-in class
document.querySelectorAll('.fade-in').forEach(el => {
    observer.observe(el);
});

// Also observe the trust section for counter animation
const trustSection = document.getElementById('trust');
if (trustSection) {
    observer.observe(trustSection);
}

// ===== FLOATING CTA =====
const floatingCta = document.getElementById('floatingCta');

window.addEventListener('scroll', () => {
    if (window.pageYOffset > 500) {
        floatingCta.classList.add('visible');
    } else {
        floatingCta.classList.remove('visible');
    }
});

// ===== MIXER COUNTER ANIMATION =====
let mixerCount = 30;

function animateMixerCount() {
    const el = document.getElementById('mixer-count-display');
    if (!el) return;

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

const solutionObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateMixerCount();
            solutionObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.3 });

const solutionSection = document.getElementById('solution');
if (solutionSection) {
    solutionObserver.observe(solutionSection);
}

// ===== SMOOTH ANCHOR LINKS =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = this.getAttribute('href').substring(1);
        scrollToSection(targetId);
    });
});

// ===== INITIALIZE =====
document.addEventListener('DOMContentLoaded', () => {
    // Ensure calculator starts on plate tab
    switchCalcTab('plate');
});

// ===== CTA FORM SUBMISSION =====
const speedForm = document.getElementById('speedForm');

// API URL для отправки лидов
const API_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : 'https://beton-backend-kwa9.onrender.com';

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
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: data.name,
                    phone: data.phone,
                    concrete_grade: data.concrete_grade || 'М200',
                    volume: parseFloat(data.volume) || 5,
                    source: 'landing-speed'
                })
            });

            const result = await response.json();
            alert('✅ Заявка принята! Перезвоним за 5 минут.');
            speedForm.reset();
        } catch (err) {
            console.error('Ошибка отправки:', err);
            alert('✅ Заявка принята! Мы свяжемся с вами.');
            speedForm.reset();
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    });
}

// ===== PHONE MASK FOR SPEED FORM =====
const speedPhone = speedForm?.querySelector('input[name="phone"]');
if (speedPhone) {
    speedPhone.addEventListener('input', function(e) {
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
