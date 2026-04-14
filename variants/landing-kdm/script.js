// ===== Mobile Menu Toggle =====
const navToggle = document.getElementById('navToggle');
const mobileMenu = document.getElementById('mobileMenu');

if (navToggle && mobileMenu) {
    navToggle.addEventListener('click', () => {
        mobileMenu.classList.toggle('active');
        navToggle.classList.toggle('active');
    });

    // Close menu on link click
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

// Tab switching
calcTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const type = tab.dataset.type;

        // Update tabs
        calcTabs.forEach(t => t.classList.remove('calc__tab--active'));
        tab.classList.add('calc__tab--active');

        // Update panels
        calcPanels.forEach(panel => panel.classList.remove('calc__panel--active'));
        document.getElementById(`panel-${type}`).classList.add('calc__panel--active');

        // Hide result when switching tabs
        if (calcResult) {
            calcResult.style.display = 'none';
        }
    });
});

// Calculate volume
function calculateVolume() {
    const activePanel = document.querySelector('.calc__panel--active');
    if (!activePanel) return;

    const panelId = activePanel.id;
    let volume = 0;

    if (panelId === 'panel-slab') {
        const length = parseFloat(document.getElementById('slab-length').value) || 0;
        const width = parseFloat(document.getElementById('slab-width').value) || 0;
        const height = parseFloat(document.getElementById('slab-height').value) || 0;
        volume = length * width * height;
    } else if (panelId === 'panel-strip') {
        const perimeter = parseFloat(document.getElementById('strip-perimeter').value) || 0;
        const width = parseFloat(document.getElementById('strip-width').value) || 0;
        const height = parseFloat(document.getElementById('strip-height').value) || 0;
        volume = perimeter * width * height;
    } else if (panelId === 'panel-cylinder') {
        const radius = parseFloat(document.getElementById('cyl-radius').value) || 0;
        const height = parseFloat(document.getElementById('cyl-height').value) || 0;
        volume = Math.PI * Math.pow(radius, 2) * height;
    }

    return Math.max(0, volume);
}

if (calcBtn) {
    calcBtn.addEventListener('click', () => {
        const volume = calculateVolume();

        if (volume <= 0) {
            alert('Пожалуйста, заполните все поля корректными значениями');
            return;
        }

        const price = Math.round(volume * PRICE_PER_CUBIC);

        // Display result
        if (calcVolume) {
            calcVolume.textContent = volume.toFixed(2);
        }
        if (calcPrice) {
            calcPrice.textContent = price.toLocaleString('ru-RU');
        }
        if (calcResult) {
            calcResult.style.display = 'block';
            calcResult.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    });
}

// ===== Order Form =====
const orderForm = document.getElementById('orderForm');
const successModal = document.getElementById('successModal');
const modalOverlay = document.getElementById('modalOverlay');
const modalClose = document.getElementById('modalClose');

if (orderForm) {
    orderForm.addEventListener('submit', (e) => {
        e.preventDefault();

        const name = document.getElementById('order-name').value.trim();
        const phone = document.getElementById('order-phone').value.trim();

        if (!name || !phone) {
            alert('Пожалуйста, заполните имя и телефон');
            return;
        }

        // Show success modal
        if (successModal) {
            successModal.classList.add('active');
        }

        // Reset form
        orderForm.reset();
    });
}

// Close modal
if (modalOverlay) {
    modalOverlay.addEventListener('click', () => {
        if (successModal) {
            successModal.classList.remove('active');
        }
    });
}

if (modalClose) {
    modalClose.addEventListener('click', () => {
        if (successModal) {
            successModal.classList.remove('active');
        }
    });
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

        // Handle Russian numbers
        if (value[0] === '8') {
            value = '7' + value.slice(1);
        }
        if (value[0] !== '7') {
            value = '7' + value;
        }

        let formatted = '+7';
        if (value.length > 1) {
            formatted += ' (' + value.slice(1, 4);
        }
        if (value.length > 4) {
            formatted += ') ' + value.slice(4, 7);
        }
        if (value.length > 7) {
            formatted += '-' + value.slice(7, 9);
        }
        if (value.length > 9) {
            formatted += '-' + value.slice(9, 11);
        }

        e.target.value = formatted;
    });
}

// ===== Animated Counter for Trust Section =====
function animateCounters() {
    const statNums = document.querySelectorAll('.trust__stat-num[data-target]');

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const target = parseInt(entry.target.dataset.target);
                animateNumber(entry.target, target);
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

// Initialize counters
animateCounters();

// ===== Smooth Scroll for Anchor Links =====
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;

        const targetElement = document.querySelector(targetId);
        if (targetElement) {
            e.preventDefault();
            const navHeight = document.querySelector('.nav')?.offsetHeight || 70;
            const targetPosition = targetElement.getBoundingClientRect().top + window.scrollY - navHeight;

            window.scrollTo({
                top: targetPosition,
                behavior: 'smooth'
            });
        }
    });
});

// ===== Navbar Background on Scroll =====
const nav = document.querySelector('.nav');

if (nav) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            nav.style.background = 'rgba(10, 10, 10, 0.95)';
        } else {
            nav.style.background = 'rgba(10, 10, 10, 0.9)';
        }
    });
}

// ===== Countdown Timer (24 hours from now) =====
function updateTimer() {
    const timerHours = document.getElementById('timer-hours');
    if (!timerHours) return;

    // Get hours remaining until end of today
    const now = new Date();
    const endOfDay = new Date(now);
    endOfDay.setHours(23, 59, 59, 999);
    const hoursRemaining = Math.ceil((endOfDay - now) / (1000 * 60 * 60));

    timerHours.textContent = Math.max(0, hoursRemaining);
}

updateTimer();
setInterval(updateTimer, 60000);
