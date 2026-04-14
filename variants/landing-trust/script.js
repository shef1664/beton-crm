(function () {
    'use strict';

    const PRICE_PER_CUBIC = 6200;

    // ========== MOBILE MENU ==========
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

    // ========== SMOOTH SCROLL ==========
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
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        });
    });

    // ========== CALCULATOR ==========
    var tabs = document.querySelectorAll('.calc-tab');
    var forms = document.querySelectorAll('.calc-form');
    var calcBtns = document.querySelectorAll('.calc-btn');
    var calcResult = document.getElementById('calc-result');
    var resultVolume = document.getElementById('result-volume');
    var resultPrice = document.getElementById('result-price');

    // Tab switching
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            var tabName = this.getAttribute('data-tab');

            tabs.forEach(function (t) { t.classList.remove('active'); });
            forms.forEach(function (f) { f.classList.remove('active'); });

            this.classList.add('active');
            document.getElementById('calc-' + tabName).classList.add('active');

            // Hide previous result when switching tabs
            if (calcResult) {
                calcResult.style.display = 'none';
            }
        });
    });

    // Calculation logic
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

            if (resultVolume) {
                resultVolume.textContent = volume.toFixed(2) + ' м³';
            }
            if (resultPrice) {
                resultPrice.textContent = cost.toLocaleString('ru-RU') + ' ₽';
            }
            if (calcResult) {
                calcResult.style.display = 'block';
                calcResult.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        });
    });

    // ========== CTA FORM ==========
    var ctaForm = document.getElementById('ctaForm');
    if (ctaForm) {
        ctaForm.addEventListener('submit', function (e) {
            e.preventDefault();

            var formData = new FormData(this);
            var name = formData.get('name');
            var phone = formData.get('phone');
            var mark = formData.get('mark');
            var volume = formData.get('volume');

            if (!name || !phone) {
                alert('Пожалуйста, заполните имя и телефон.');
                return;
            }

            // Simulate submission
            var btn = this.querySelector('button[type="submit"]');
            var originalText = btn.textContent;
            btn.textContent = 'Отправляем...';
            btn.disabled = true;

            setTimeout(function () {
                btn.textContent = 'Заявка отправлена!';
                btn.style.background = '#059669';

                setTimeout(function () {
                    btn.textContent = originalText;
                    btn.style.background = '';
                    btn.disabled = false;
                    ctaForm.reset();
                }, 3000);
            }, 1500);
        });

        // Phone mask
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
                    if (value.length > 1) {
                        formatted += ' (' + value.substring(1, 4);
                    }
                    if (value.length > 4) {
                        formatted += ') ' + value.substring(4, 7);
                    }
                    if (value.length > 7) {
                        formatted += '-' + value.substring(7, 9);
                    }
                    if (value.length > 9) {
                        formatted += '-' + value.substring(9, 11);
                    }
                } else {
                    formatted = '+7 (' + value.substring(0, 3);
                    if (value.length > 3) {
                        formatted += ') ' + value.substring(3, 6);
                    }
                    if (value.length > 6) {
                        formatted += '-' + value.substring(6, 8);
                    }
                    if (value.length > 8) {
                        formatted += '-' + value.substring(8, 10);
                    }
                }

                this.value = formatted;
            });

            phoneInput.addEventListener('focus', function () {
                if (!this.value) {
                    this.value = '+7';
                }
            });

            phoneInput.addEventListener('blur', function () {
                if (this.value === '+7') {
                    this.value = '';
                }
            });
        }
    }

    // ========== HEADER SHADOW ON SCROLL ==========
    var header = document.querySelector('.header');
    if (header) {
        window.addEventListener('scroll', function () {
            if (window.scrollY > 10) {
                header.style.boxShadow = '0 2px 12px rgba(0,0,0,0.08)';
            } else {
                header.style.boxShadow = 'none';
            }
        });
    }

    // ========== URGENCY BAR ANIMATION ==========
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

        // Start at 0 for animation
        urgencyFill.style.width = '0%';
        observer.observe(urgencyFill);
    }

})();
