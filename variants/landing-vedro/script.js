// ========== NAVIGATION ==========
const nav = document.querySelector('.nav');
const burger = document.querySelector('.nav__burger');
const mobileMenu = document.querySelector('.nav__mobile');

// Scroll shadow
window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
        nav.classList.add('scrolled');
    } else {
        nav.classList.remove('scrolled');
    }
});

// Mobile menu toggle
if (burger) {
    burger.addEventListener('click', () => {
        mobileMenu.classList.toggle('open');
        const spans = burger.querySelectorAll('span');
        if (mobileMenu.classList.contains('open')) {
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

// Close mobile menu on link click
if (mobileMenu) {
    mobileMenu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            mobileMenu.classList.remove('open');
            const spans = burger.querySelectorAll('span');
            spans[0].style.transform = '';
            spans[1].style.opacity = '';
            spans[2].style.transform = '';
        });
    });
}

// ========== CALCULATOR TABS ==========
const calcTabs = document.querySelectorAll('.calc-tab');
const calcPanels = document.querySelectorAll('.calculator__panel');

calcTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        calcTabs.forEach(t => t.classList.remove('active'));
        calcPanels.forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const target = document.getElementById(`calc-${tab.dataset.tab}`);
        if (target) target.classList.add('active');
    });
});

// ========== SHAPE TABS (Volume Calculator) ==========
const shapeBtns = document.querySelectorAll('.calc-shape-btn');
const calcForms = document.querySelectorAll('.calc-form');

shapeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        shapeBtns.forEach(b => b.classList.remove('active'));
        calcForms.forEach(f => f.classList.remove('active'));
        btn.classList.add('active');
        const target = document.getElementById(`form-${btn.dataset.shape}`);
        if (target) target.classList.add('active');
    });
});

// ========== CALCULATIONS ==========
const BASE_PRICE = 5800;

function formatNumber(num) {
    return num.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
}

function showResult(containerId, volume, area, price, formula) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let html = '';
    if (volume !== undefined) {
        html += `<div class="calc-result__volume">${formatNumber(volume)} м³</div>`;
        html += `<div class="calc-result__price">Примерная стоимость: от ${formatNumber(price)} ₽</div>`;
    }
    if (area !== undefined) {
        html += `<div class="calc-result__volume">${formatNumber(area)} м²</div>`;
        html += `<div class="calc-result__price">Площадь боковой поверхности цилиндра</div>`;
    }
    if (formula) {
        html += `<div class="calc-result__formula">${formula}</div>`;
    }

    container.innerHTML = html;
    container.classList.add('visible');
}

// Slab: V = L * W * H
document.querySelector('[data-calc="slab"]').addEventListener('click', () => {
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
    const formula = `V = ${l} × ${w} × ${h} = ${formatNumber(volume)} м³`;

    showResult('result-slab', volume, undefined, price, formula);
});

// Strip: V = P * W * H
document.querySelector('[data-calc="strip"]').addEventListener('click', () => {
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
    const formula = `V = ${p} × ${w} × ${h} = ${formatNumber(volume)} м³`;

    showResult('result-strip', volume, undefined, price, formula);
});

// Cylinder Volume: V = π * r² * h
document.querySelector('[data-calc="cylinder"]').addEventListener('click', () => {
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
    const formula = `V = π × ${r}² × ${h} = ${formatNumber(volume)} м³`;

    showResult('result-cylinder', volume, undefined, price, formula);
});

// Cylinder Area: S = 2 * π * r * h
document.querySelector('[data-calc="area"]').addEventListener('click', () => {
    const r = parseFloat(document.getElementById('area-r').value);
    const h = parseFloat(document.getElementById('area-h').value);

    if (!r || !h || r <= 0 || h <= 0) {
        showResult('result-area', null, null, null, null);
        document.getElementById('result-area').innerHTML = '<p style="color: #ef4444;">Заполните все поля корректными значениями</p>';
        document.getElementById('result-area').classList.add('visible');
        return;
    }

    const area = 2 * Math.PI * r * h;
    const formula = `S = 2 × π × ${r} × ${h} = ${formatNumber(area)} м²`;

    showResult('result-area', undefined, area, undefined, formula);
});

// ========== FORM SUBMISSION ==========
const ctaForm = document.getElementById('cta-form');

if (ctaForm) {
    ctaForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const name = ctaForm.querySelector('[name="name"]').value.trim();
        const phone = ctaForm.querySelector('[name="phone"]').value.trim();

        if (!name || !phone) {
            alert('Пожалуйста, заполните все поля');
            return;
        }

        // В реальном проекте здесь будет отправка на сервер
        alert(`Спасибо, ${name}! Мы перезвоним вам на ${phone} в течение 15 минут.`);
        ctaForm.reset();
    });
}

// ========== SCROLL ANIMATIONS ==========
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.classList.add('animate-in');
            observer.unobserve(entry.target);
        }
    });
}, observerOptions);

// Animate elements on scroll
const animTargets = document.querySelectorAll(
    '.section-title, .pain-card, .solution__block, .advantage-item, .step, .trust__content, .urgency__title, .cta__form'
);

animTargets.forEach(el => {
    el.style.opacity = '0';
    observer.observe(el);
});

// ========== SMOOTH SCROLL FOR ANCHOR LINKS ==========
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            e.preventDefault();
            const offset = 80;
            const position = target.getBoundingClientRect().top + window.pageYOffset - offset;
            window.scrollTo({
                top: position,
                behavior: 'smooth'
            });
        }
    });
});
