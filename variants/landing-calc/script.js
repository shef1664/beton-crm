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
    if (ctaForm) {
        ctaForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(ctaForm);
            const name = formData.get('name');
            const phone = formData.get('phone');
            const grade = formData.get('grade');
            alert('Спасибо, ' + name + '! Мы перезвоним вам в ближайшее время.\n\nВаш заказ:\nМарка: ' + (grade || 'не выбрана') + '\nТелефон: ' + phone);
            ctaForm.reset();
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
