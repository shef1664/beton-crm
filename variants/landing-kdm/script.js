// ===== Mobile Menu Toggle =====
const navToggle = document.getElementById('navToggle');
const mobileMenu = document.getElementById('mobileMenu');

if (navToggle && mobileMenu) {
    navToggle.addEventListener('click', () => {
        mobileMenu.classList.toggle('active');
        navToggle.classList.toggle('active');
    });

    mobileMenu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            mobileMenu.classList.remove('active');
            navToggle.classList.remove('active');
        });
    });
}

// ===== Calculator =====
const calcTabs = document.querySelectorAll('.calc__tab');
const calcPanels = document.querySelectorAll('.calc__panel');
const calcBtn = document.getElementById('calcBtn');
const calcResult = document.getElementById('calcResult');
const calcVolume = document.getElementById('calcVolume');
const calcPrice = document.getElementById('calcPrice');
const PRICE_PER_CUBIC = 5800;

calcTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const type = tab.dataset.type;
        calcTabs.forEach(t => t.classList.remove('calc__tab--active'));
        tab.classList.add('calc__tab--active');
        calcPanels.forEach(panel => panel.classList.remove('calc__panel--active'));
        document.getElementById(`panel-${type}`)?.classList.add('calc__panel--active');
        if (calcResult) calcResult.style.display = 'none';
    });
});

function calculateVolume() {
    const activePanel = document.querySelector('.calc__panel--active');
    if (!activePanel) return 0;

    const panelId = activePanel.id;
    if (panelId === 'panel-slab') {
        const length = parseFloat(document.getElementById('slab-length').value) || 0;
        const width = parseFloat(document.getElementById('slab-width').value) || 0;
        const height = parseFloat(document.getElementById('slab-height').value) || 0;
        return Math.max(0, length * width * height);
    }
    if (panelId === 'panel-strip') {
        const perimeter = parseFloat(document.getElementById('strip-perimeter').value) || 0;
        const width = parseFloat(document.getElementById('strip-width').value) || 0;
        const height = parseFloat(document.getElementById('strip-height').value) || 0;
        return Math.max(0, perimeter * width * height);
    }
    if (panelId === 'panel-cylinder') {
        const radius = parseFloat(document.getElementById('cyl-radius').value) || 0;
        const height = parseFloat(document.getElementById('cyl-height').value) || 0;
        return Math.max(0, Math.PI * Math.pow(radius, 2) * height);
    }
    return 0;
}

if (calcBtn) {
    calcBtn.addEventListener('click', () => {
        const volume = calculateVolume();
        if (volume <= 0) {
            alert('Пожалуйста, заполните все поля корректными значениями');
            return;
        }

        const price = Math.round(volume * PRICE_PER_CUBIC);
        if (calcVolume) calcVolume.textContent = volume.toFixed(2);
        if (calcPrice) calcPrice.textContent = price.toLocaleString('ru-RU');
        if (calcResult) {
            calcResult.style.display = 'block';
            calcResult.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    });
}

// ===== Lead Form =====
const orderForm = document.getElementById('orderForm');
const successModal = document.getElementById('successModal');
const modalOverlay = document.getElementById('modalOverlay');
const modalClose = document.getElementById('modalClose');

let API_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://beton-backend-kwa9.onrender.com';

async function loadConfig() {
    try {
        const response = await fetch(`${API_URL}/api/config`);
        if (!response.ok) return;
        const config = await response.json();
        if (config.api_url) API_URL = config.api_url;
    } catch (_) {}
}

function normalizePhone(phone) {
    const digits = String(phone || '').replace(/\D/g, '');
    if (!digits) return '';
    if (digits.length === 11 && digits.startsWith('8')) return '+7' + digits.slice(1);
    if (digits.length === 11 && digits.startsWith('7')) return '+' + digits;
    if (digits.length === 10) return '+7' + digits;
    return phone;
}

loadConfig();

if (orderForm) {
    orderForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById('order-name').value.trim();
        const phone = document.getElementById('order-phone').value.trim();
        const concreteGrade = document.getElementById('order-grade')?.value || 'М200';
        const volume = document.getElementById('order-volume')?.value || '5';
        const address = document.getElementById('order-address')?.value || '';

        if (!name || !phone) {
            alert('Пожалуйста, заполните имя и телефон');
            return;
        }

        try {
            const response = await fetch(`${API_URL}/api/leads/create`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    phone: normalizePhone(phone),
                    concrete_grade: concreteGrade,
                    volume: parseFloat(volume) || 5,
                    address: address || 'Не указан',
                    source: 'landing-kdm'
                })
            });

            const result = await response.json().catch(() => ({}));
            if (response.ok && (result.status === 'success' || result.status === 'duplicate')) {
                if (successModal) successModal.classList.add('active');
                orderForm.reset();
            } else {
                alert('Ошибка: ' + (result.message || result.detail || 'Не удалось отправить заявку'));
            }
        } catch (err) {
            console.error('Ошибка отправки:', err);
            alert('Ошибка соединения. Попробуйте позже или позвоните нам.');
        }
    });
}

if (modalOverlay) {
    modalOverlay.addEventListener('click', () => successModal?.classList.remove('active'));
}

if (modalClose) {
    modalClose.addEventListener('click', () => successModal?.classList.remove('active'));
}

// ===== Phone Input Mask =====
const phoneInput = document.getElementById('order-phone');

if (phoneInput) {
    phoneInput.addEventListener('input', (e) => {
        let value = e.target.value.replace(/\D/g, '');
        if (value.length === 0) {
            e.target.value = '';
            return;
        }

        if (value[0] === '8') value = '7' + value.slice(1);
        if (value[0] !== '7') value = '7' + value;

        let formatted = '+7';
        if (value.length > 1) formatted += ' (' + value.slice(1, 4);
        if (value.length > 4) formatted += ') ' + value.slice(4, 7);
        if (value.length > 7) formatted += '-' + value.slice(7, 9);
        if (value.length > 9) formatted += '-' + value.slice(9, 11);
        e.target.value = formatted;
    });
}

// ===== Animated Counter for Trust Section =====
function animateCounters() {
    const statNums = document.querySelectorAll('.trust__stat-num[data-target]');
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateNumber(entry.target, parseInt(entry.target.dataset.target, 10));
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    statNums.forEach(num => observer.observe(num));
}

function animateNumber(element, target) {
    let current = 0;
    const duration = 1500;
    const step = target / (duration / 16);

    const timer = setInterval(() => {
        current += step;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        element.textContent = Math.floor(current);
    }, 16);
}

animateCounters();

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;

        const targetElement = document.querySelector(targetId);
        if (targetElement) {
            e.preventDefault();
            targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });
});
