(function () {
    'use strict';

    const PRICE_PER_CUBIC = 6200;

    const mobileBtn = document.querySelector('.mobile-menu-btn');
    const navMobile = document.getElementById('navMobile');

    if (mobileBtn && navMobile) {
        mobileBtn.addEventListener('click', function () {
            navMobile.classList.toggle('active');
            const spans = mobileBtn.querySelectorAll('span');
            if (navMobile.classList.contains('active')) {
                spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                spans[1].style.opacity = '0';
                spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
            } else {
                spans[0].style.transform = '';
                spans[1].style.opacity = '';
                spans[2].style.transform = '';
            }
        });

        navMobile.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () {
                navMobile.classList.remove('active');
                const spans = mobileBtn.querySelectorAll('span');
                spans[0].style.transform = '';
                spans[1].style.opacity = '';
                spans[2].style.transform = '';
            });
        });
    }

    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
        anchor.addEventListener('click', function (e) {
            var targetId = this.getAttribute('href');
            if (targetId === '#') return;
            var target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                var headerOffset = 70;
                var elementPosition = target.getBoundingClientRect().top;
                var offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                window.scrollTo({ top: offsetPosition, behavior: 'smooth' });
            }
        });
    });

    var tabs = document.querySelectorAll('.calc-tab');
    var forms = document.querySelectorAll('.calc-form');
    var calcBtns = document.querySelectorAll('.calc-btn');
    var calcResult = document.getElementById('calc-result');
    var resultVolume = document.getElementById('result-volume');
    var resultPrice = document.getElementById('result-price');

    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            var tabName = this.getAttribute('data-tab');
            tabs.forEach(function (t) { t.classList.remove('active'); });
            forms.forEach(function (f) { f.classList.remove('active'); });
            this.classList.add('active');
            document.getElementById('calc-' + tabName)?.classList.add('active');
            if (calcResult) calcResult.style.display = 'none';
        });
    });

    calcBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var type = this.getAttribute('data-type');
            var volume = 0;

            if (type === 'slab') {
                var l = parseFloat(document.getElementById('slab-l').value) || 0;
                var w = parseFloat(document.getElementById('slab-w').value) || 0;
                var h = parseFloat(document.getElementById('slab-h').value) || 0;
                volume = l * w * h;
            } else if (type === 'strip') {
                var p = parseFloat(document.getElementById('strip-p').value) || 0;
                var w = parseFloat(document.getElementById('strip-w').value) || 0;
                var h = parseFloat(document.getElementById('strip-h').value) || 0;
                volume = p * w * h;
            } else if (type === 'cylinder') {
                var r = parseFloat(document.getElementById('cyl-r').value) || 0;
                var h = parseFloat(document.getElementById('cyl-h').value) || 0;
                volume = Math.PI * r * r * h;
            }

            if (volume <= 0) {
                alert('Пожалуйста, заполните все поля корректными значениями.');
                return;
            }

            var cost = Math.round(volume * PRICE_PER_CUBIC);
            if (resultVolume) resultVolume.textContent = volume.toFixed(2) + ' м³';
            if (resultPrice) resultPrice.textContent = cost.toLocaleString('ru-RU') + ' ₽';
            if (calcResult) {
                calcResult.style.display = 'block';
                calcResult.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });
    });

    var ctaForm = document.getElementById('ctaForm');
    var API_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
        ? 'http://localhost:8000'
        : 'https://beton-backend-kwa9.onrender.com';

    function normalizePhone(phone) {
        var digits = String(phone || '').replace(/\D/g, '');
        if (!digits) return '';
        if (digits.length === 11 && digits[0] === '8') return '+7' + digits.slice(1);
        if (digits.length === 11 && digits[0] === '7') return '+' + digits;
        if (digits.length === 10) return '+7' + digits;
        return phone;
    }

    fetch(`${API_URL}/api/config`).then(function (r) {
        if (!r.ok) return null;
        return r.json();
    }).then(function (cfg) {
        if (cfg && cfg.api_url) API_URL = cfg.api_url;
    }).catch(function () {});

    if (ctaForm) {
        ctaForm.addEventListener('submit', async function (e) {
            e.preventDefault();

            var formData = new FormData(this);
            var name = formData.get('name');
            var phone = formData.get('phone');
            var mark = formData.get('mark') || 'М200';
            var volume = formData.get('volume') || '5';

            if (!name || !phone) {
                alert('Пожалуйста, заполните имя и телефон.');
                return;
            }

            var btn = this.querySelector('button[type="submit"]');
            var originalText = btn.textContent;
            btn.textContent = 'Отправляем...';
            btn.disabled = true;

            try {
                const response = await fetch(`${API_URL}/api/leads/create`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name,
                        phone: normalizePhone(phone),
                        concrete_grade: mark,
                        volume: parseFloat(volume) || 5,
                        source: 'landing-trust'
                    })
                });

                const result = await response.json().catch(function () { return {}; });
                if (response.ok && (result.status === 'success' || result.status === 'duplicate')) {
                    btn.textContent = 'Заявка отправлена!';
                    btn.style.background = '#059669';
                    ctaForm.reset();
                } else {
                    alert('Ошибка: ' + (result.message || result.detail || 'Не удалось отправить заявку.'));
                }
            } catch (err) {
                console.error('Ошибка отправки:', err);
                alert('Ошибка соединения. Попробуйте позже или позвоните нам.');
            } finally {
                setTimeout(function () {
                    btn.textContent = originalText;
                    btn.style.background = '';
                    btn.disabled = false;
                }, 3000);
            }
        });

        var phoneInput = ctaForm.querySelector('input[name="phone"]');
        if (phoneInput) {
            phoneInput.addEventListener('input', function () {
                var value = this.value.replace(/\D/g, '');
                if (value.length === 0) {
                    this.value = '';
                    return;
                }

                var formatted = '';
                if (value[0] === '7' || value[0] === '8') {
                    formatted = '+7';
                    if (value.length > 1) formatted += ' (' + value.substring(1, 4);
                    if (value.length > 4) formatted += ') ' + value.substring(4, 7);
                    if (value.length > 7) formatted += '-' + value.substring(7, 9);
                    if (value.length > 9) formatted += '-' + value.substring(9, 11);
                } else {
                    formatted = '+7 (' + value.substring(0, 3);
                    if (value.length > 3) formatted += ') ' + value.substring(3, 6);
                    if (value.length > 6) formatted += '-' + value.substring(6, 8);
                    if (value.length > 8) formatted += '-' + value.substring(8, 10);
                }

                this.value = formatted;
            });
        }
    }

    var header = document.querySelector('.header');
    if (header) {
        window.addEventListener('scroll', function () {
            header.style.boxShadow = window.scrollY > 10 ? '0 2px 12px rgba(0,0,0,0.08)' : 'none';
        });
    }

    var urgencyFill = document.querySelector('.urgency-fill');
    if (urgencyFill) {
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    urgencyFill.style.width = '90%';
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        urgencyFill.style.width = '0%';
        observer.observe(urgencyFill);
    }
})();
