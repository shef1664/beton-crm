// ========== NAVIGATION ==========
const nav = document.querySelector('.nav');
const burger = document.querySelector('.nav__burger');
const mobileMenuVedro = document.querySelector('.nav__mobile');

window.addEventListener('scroll', () => {
    if (window.scrollY > 50) nav?.classList.add('scrolled');
    else nav?.classList.remove('scrolled');
});

if (burger && mobileMenuVedro) {
    burger.addEventListener('click', () => {
        mobileMenuVedro.classList.toggle('open');
        const spans = burger.querySelectorAll('span');
        if (mobileMenuVedro.classList.contains('open')) {
            spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
            spans[1].style.opacity = '0';
            spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
        } else {
            spans[0].style.transform = '';
            spans[1].style.opacity = '';
            spans[2].style.transform = '';
        }
    });
}

if (mobileMenuVedro) {
    mobileMenuVedro.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            mobileMenuVedro.classList.remove('open');
            if (!burger) return;
            const spans = burger.querySelectorAll('span');
            spans[0].style.transform = '';
            spans[1].style.opacity = '';
            spans[2].style.transform = '';
        });
    });
}

// ========== CALCULATORS ==========
const calcTabs = document.querySelectorAll('.calc-tab');
const calcPanels = document.querySelectorAll('.calculator__panel');
const shapeBtns = document.querySelectorAll('.calc-shape-btn');
const calcForms = document.querySelectorAll('.calc-form');
const BASE_PRICE = 5800;

calcTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        calcTabs.forEach(t => t.classList.remove('active'));
        calcPanels.forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`calc-${tab.dataset.tab}`)?.classList.add('active');
    });
});

shapeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        shapeBtns.forEach(b => b.classList.remove('active'));
        calcForms.forEach(f => f.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`form-${btn.dataset.shape}`)?.classList.add('active');
    });
});

function formatNumber(num) {
    return num.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

function showResult(containerId, volume, area, price, formula) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let html = '';
    if (volume !== undefined && volume !== null) {
        html += `<div class="calc-result__volume">${formatNumber(volume)} м³</div>`;
        html += `<div class="calc-result__price">Примерная стоимость: от ${formatNumber(price)} ₽</div>`;
    }
    if (area !== undefined && area !== null) {
        html += `<div class="calc-result__volume">${formatNumber(area)} м²</div>`;
        html += `<div class="calc-result__price">Площадь боковой поверхности цилиндра</div>`;
    }
    if (formula) html += `<div class="calc-result__formula">${formula}</div>`;

    container.innerHTML = html;
    container.classList.add('visible');
}

document.querySelector('[data-calc="slab"]')?.addEventListener('click', () => {
    const l = parseFloat(document.getElementById('slab-l').value);
    const w = parseFloat(document.getElementById('slab-w').value);
    const h = parseFloat(document.getElementById('slab-h').value);
    if (!l || !w || !h || l <= 0 || w <= 0 || h <= 0) {
        showResult('result-slab', null, null, null, null);
        document.getElementById('result-slab').innerHTML = '<p style="color: #ef4444;">Заполните все поля корректными значениями</p>';
        document.getElementById('result-slab').classList.add('visible');
        return;
    }
    const volume = l * w * h;
    const price = Math.round(volume * BASE_PRICE);
    showResult('result-slab', volume, undefined, price, `V = ${l} × ${w} × ${h} = ${formatNumber(volume)} м³`);
});

document.querySelector('[data-calc="strip"]')?.addEventListener('click', () => {
    const p = parseFloat(document.getElementById('strip-p').value);
    const w = parseFloat(document.getElementById('strip-w').value);
    const h = parseFloat(document.getElementById('strip-h').value);
    if (!p || !w || !h || p <= 0 || w <= 0 || h <= 0) {
        showResult('result-strip', null, null, null, null);
        document.getElementById('result-strip').innerHTML = '<p style="color: #ef4444;">Заполните все поля корректными значениями</p>';
        document.getElementById('result-strip').classList.add('visible');
        return;
    }
    const volume = p * w * h;
    const price = Math.round(volume * BASE_PRICE);
    showResult('result-strip', volume, undefined, price, `V = ${p} × ${w} × ${h} = ${formatNumber(volume)} м³`);
});

document.querySelector('[data-calc="cylinder"]')?.addEventListener('click', () => {
    const r = parseFloat(document.getElementById('cyl-r').value);
    const h = parseFloat(document.getElementById('cyl-h').value);
    if (!r || !h || r <= 0 || h <= 0) {
        showResult('result-cylinder', null, null, null, null);
        document.getElementById('result-cylinder').innerHTML = '<p style="color: #ef4444;">Заполните все поля корректными значениями</p>';
        document.getElementById('result-cylinder').classList.add('visible');
        return;
    }
    const volume = Math.PI * Math.pow(r, 2) * h;
    const price = Math.round(volume * BASE_PRICE);
    showResult('result-cylinder', volume, undefined, price, `V = π × ${r}² × ${h} = ${formatNumber(volume)} м³`);
});

document.querySelector('[data-calc="area"]')?.addEventListener('click', () => {
    const r = parseFloat(document.getElementById('area-r').value);
    const h = parseFloat(document.getElementById('area-h').value);
    if (!r || !h || r <= 0 || h <= 0) {
        showResult('result-area', null, null, null, null);
        document.getElementById('result-area').innerHTML = '<p style="color: #ef4444;">Заполните все поля корректными значениями</p>';
        document.getElementById('result-area').classList.add('visible');
        return;
    }
    const area = 2 * Math.PI * r * h;
    showResult('result-area', undefined, area, undefined, `S = 2 × π × ${r} × ${h} = ${formatNumber(area)} м²`);
});

// ========== FORM SUBMISSION ==========
const ctaForm = document.getElementById('cta-form');
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

if (ctaForm) {
    ctaForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = ctaForm.querySelector('[name="name"]').value.trim();
        const phone = ctaForm.querySelector('[name="phone"]').value.trim();

        if (!name || !phone) {
            alert('Пожалуйста, заполните все поля');
            return;
        }

        try {
            const response = await fetch(`${API_URL}/api/leads/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    phone: normalizePhone(phone),
                    source: 'landing-vedro'
                })
            });

            const result = await response.json().catch(() => ({}));
            if (response.ok && (result.status === 'success' || result.status === 'duplicate')) {
                alert(`Спасибо, ${name}! Мы перезвоним вам на ${phone} в течение 15 минут.`);
                ctaForm.reset();
            } else {
                alert('Ошибка: ' + (result.message || result.detail || 'Не удалось отправить заявку.'));
            }
        } catch (err) {
            console.error('Ошибка отправки:', err);
            alert('Ошибка соединения. Попробуйте позже или позвоните нам.');
        }
    });
}

// ========== ANIMATIONS ==========
const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

document.querySelectorAll('.section-title, .pain-card, .solution__block, .advantage-item, .step, .trust__content, .urgency__title, .cta__form').forEach(el => {
    el.style.opacity = '0';
    observer.observe(el);
});

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            const offset = 80;
            const position = target.getBoundingClientRect().top + window.pageYOffset - offset;
            window.scrollTo({ top: position, behavior: 'smooth' });
        }
    });
});
