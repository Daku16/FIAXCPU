/* Accesibilidad compartida de FIAX CPU.
 * - Aplica las preferencias guardadas (tema, contraste, tamaño de texto) antes de pintar la página.
 * - Enlace "Saltar al contenido", iconos decorativos ocultos a lectores de pantalla.
 * - Modales: role=dialog, foco inicial, foco atrapado, Escape para cerrar y retorno del foco.
 * - Filas de tabla con onclick operables con Enter / Espacio.
 * - aria-current en el menú y panel de accesibilidad.
 */
(function () {
    'use strict';

    var KEY = 'fiax-a11y';
    var DEFAULTS = { theme: 'dark', contrast: 'normal', fs: '1' };
    var FS_VALUES = ['1', '1.125', '1.25', '1.5'];
    var root = document.documentElement;

    function loadPrefs() {
        var prefs = {};
        try { prefs = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) { prefs = {}; }
        var hasSaved = Object.keys(prefs).length > 0;
        prefs = Object.assign({}, DEFAULTS, prefs);
        if (!hasSaved && window.matchMedia && matchMedia('(prefers-contrast: more)').matches) prefs.contrast = 'high';
        return prefs;
    }

    function savePrefs(prefs) {
        try { localStorage.setItem(KEY, JSON.stringify(prefs)); } catch (e) { /* almacenamiento no disponible */ }
    }

    function resolvedTheme(theme) {
        if (theme === 'system') {
            return window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
        }
        return theme === 'light' ? 'light' : 'dark';
    }

    function applyPrefs(prefs) {
        root.setAttribute('data-theme', resolvedTheme(prefs.theme));
        root.setAttribute('data-contrast', prefs.contrast === 'high' ? 'high' : 'normal');
        root.setAttribute('data-fs', FS_VALUES.indexOf(String(prefs.fs)) >= 0 ? String(prefs.fs) : '1');
    }

    var prefs = loadPrefs();
    applyPrefs(prefs);
    if (window.matchMedia) {
        var mq = matchMedia('(prefers-color-scheme: light)');
        var onSystemChange = function () { if (prefs.theme === 'system') applyPrefs(prefs); };
        if (mq.addEventListener) mq.addEventListener('change', onSystemChange);
    }

    // ---------------- Anuncios para lectores de pantalla ----------------
    var announcer;
    function announce(text) {
        if (!announcer) return;
        announcer.textContent = '';
        setTimeout(function () { announcer.textContent = text; }, 60);
    }

    // ---------------- Utilidades de foco ----------------
    var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), ' +
        'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

    function isVisible(el) {
        return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length) &&
            getComputedStyle(el).visibility !== 'hidden';
    }

    function focusables(container) {
        return Array.prototype.filter.call(container.querySelectorAll(FOCUSABLE), isVisible);
    }

    // ---------------- Modales ----------------
    var openModals = []; // { overlay, returnTo }

    function modalIsOpen(overlay) {
        return getComputedStyle(overlay).display !== 'none';
    }

    function dialogBox(overlay) {
        return overlay.firstElementChild || overlay;
    }

    function prepareModal(overlay) {
        if (overlay.dataset.a11yReady) return;
        overlay.dataset.a11yReady = '1';
        var box = dialogBox(overlay);
        var closer = findCloser(overlay);
        if (!box.hasAttribute('role')) box.setAttribute('role', closer ? 'dialog' : 'alertdialog');
        box.setAttribute('aria-modal', 'true');
        if (!box.hasAttribute('tabindex')) box.setAttribute('tabindex', '-1');
        var title = box.querySelector('h1, h2, h3');
        if (title && !box.hasAttribute('aria-labelledby') && !box.hasAttribute('aria-label')) {
            if (!title.id) title.id = (overlay.id || 'dialogo') + '-titulo';
            box.setAttribute('aria-labelledby', title.id);
        }
        if (!closer) box.setAttribute('aria-busy', 'true');
        new MutationObserver(function () { syncModal(overlay); })
            .observe(overlay, { attributes: true, attributeFilter: ['style', 'class'] });
        if (modalIsOpen(overlay)) syncModal(overlay);
    }

    function findCloser(overlay) {
        var explicit = overlay.querySelector('[data-a11y-close]');
        if (explicit) return explicit;
        var buttons = overlay.querySelectorAll('button');
        for (var i = 0; i < buttons.length; i++) {
            var handler = buttons[i].getAttribute('onclick') || '';
            if (/close\w*\(/i.test(handler)) return buttons[i];
        }
        return null;
    }

    function syncModal(overlay) {
        var index = -1;
        for (var i = 0; i < openModals.length; i++) if (openModals[i].overlay === overlay) index = i;
        var open = modalIsOpen(overlay);
        if (open && index === -1) {
            var returnTo = document.activeElement;
            openModals.push({ overlay: overlay, returnTo: returnTo });
            // Espera a que el contenido del modal termine de pintarse antes de mover el foco.
            setTimeout(function () {
                if (!modalIsOpen(overlay)) return;
                var box = dialogBox(overlay);
                if (box.contains(document.activeElement)) return;
                var preferred = box.querySelector('[autofocus], [data-a11y-initial]');
                var list = focusables(box);
                (preferred || list[0] || box).focus();
            }, 30);
        } else if (!open && index !== -1) {
            var entry = openModals.splice(index, 1)[0];
            if (entry.returnTo && document.contains(entry.returnTo) && isVisible(entry.returnTo)) {
                entry.returnTo.focus();
            }
        }
    }

    function topModal() {
        return openModals.length ? openModals[openModals.length - 1].overlay : null;
    }

    document.addEventListener('keydown', function (e) {
        var overlay = topModal();
        if (!overlay) return;
        if (e.key === 'Escape') {
            var closer = findCloser(overlay);
            if (closer) { e.preventDefault(); closer.click(); }
            return;
        }
        if (e.key !== 'Tab') return;
        var box = dialogBox(overlay);
        var list = focusables(box);
        if (!list.length) { e.preventDefault(); box.focus(); return; }
        var first = list[0], last = list[list.length - 1];
        if (!box.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
        else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }, true);

    // ---------------- Mejoras automáticas del DOM ----------------
    function enhance(scope) {
        // Iconos decorativos: el texto vecino ya describe la acción.
        scope.querySelectorAll('i[class*="fa-"]:not([aria-hidden])').forEach(function (icon) {
            icon.setAttribute('aria-hidden', 'true');
        });
        // Botones que solo tienen icono.
        scope.querySelectorAll('button:not([aria-label]), a[href]:not([aria-label])').forEach(function (el) {
            if (!el.textContent.trim()) el.setAttribute('aria-label', el.getAttribute('title') || 'Acción');
        });
        // Filas clicables: operables con teclado.
        scope.querySelectorAll('tr[onclick]:not([tabindex])').forEach(function (row) {
            row.setAttribute('tabindex', '0');
            if (!row.hasAttribute('aria-label')) {
                var celdas = Array.prototype.map.call(row.cells, function (c) { return c.textContent.trim(); })
                    .filter(Boolean).slice(0, 3).join(', ');
                row.setAttribute('aria-label', 'Ver detalle: ' + celdas);
            }
        });
        // Barras de progreso: su valor ya aparece como texto, son solo decorativas.
        scope.querySelectorAll('.progress-bar:not([aria-hidden])').forEach(function (bar) {
            bar.setAttribute('aria-hidden', 'true');
        });
        scope.querySelectorAll('.modal-overlay').forEach(prepareModal);
        syncNav();
    }

    function syncNav() {
        document.querySelectorAll('.nav-btn').forEach(function (btn) {
            if (btn.classList.contains('active')) btn.setAttribute('aria-current', 'page');
            else btn.removeAttribute('aria-current');
        });
    }

    document.addEventListener('keydown', function (e) {
        var row = e.target;
        if (row && row.tagName === 'TR' && row.hasAttribute('onclick') && (e.key === 'Enter' || e.key === ' ')) {
            e.preventDefault();
            row.click();
        }
    });

    // ---------------- Panel de accesibilidad ----------------
    function radioGroup(name, legend, options, current) {
        var html = '<fieldset><legend>' + legend + '</legend><div class="a11y-options">';
        options.forEach(function (opt) {
            html += '<label><input type="radio" name="' + name + '" value="' + opt[0] + '"' +
                (String(current) === opt[0] ? ' checked' : '') + '><span>' + opt[1] + '</span></label>';
        });
        return html + '</div></fieldset>';
    }

    function buildPanel() {
        var overlay = document.createElement('div');
        overlay.className = 'a11y-panel-overlay';
        overlay.style.display = 'none';
        overlay.id = 'a11yPanel';
        overlay.innerHTML =
            '<div class="a11y-panel">' +
            '<h2 id="a11yPanel-titulo">Opciones de accesibilidad</h2>' +
            '<p class="a11y-hint">Los cambios se aplican al instante y se recuerdan en este navegador.</p>' +
            '<form id="a11yForm">' +
            radioGroup('theme', 'Tema', [['dark', 'Oscuro'], ['light', 'Claro'], ['system', 'Del sistema']], prefs.theme) +
            radioGroup('contrast', 'Contraste', [['normal', 'Normal'], ['high', 'Alto']], prefs.contrast) +
            radioGroup('fs', 'Tamaño del texto', [['1', '100 %'], ['1.125', '112 %'], ['1.25', '125 %'], ['1.5', '150 %']], prefs.fs) +
            '</form>' +
            '<div class="a11y-panel-actions">' +
            '<button type="button" id="a11yReset">Restablecer</button>' +
            '<button type="button" class="primary" data-a11y-close onclick="FiaxA11y.closePanel()">Listo</button>' +
            '</div></div>';
        overlay.addEventListener('click', function (e) { if (e.target === overlay) FiaxA11y.closePanel(); });
        document.body.appendChild(overlay);

        var form = overlay.querySelector('#a11yForm');
        form.addEventListener('change', function () {
            var data = new FormData(form);
            prefs = { theme: data.get('theme'), contrast: data.get('contrast'), fs: data.get('fs') };
            applyPrefs(prefs);
            savePrefs(prefs);
            var etiquetas = { dark: 'oscuro', light: 'claro', system: 'del sistema' };
            announce('Tema ' + etiquetas[prefs.theme] + ', contraste ' + (prefs.contrast === 'high' ? 'alto' : 'normal') +
                ', texto al ' + Math.round(Number(prefs.fs) * 100) + ' por ciento.');
        });
        overlay.querySelector('#a11yReset').addEventListener('click', function () {
            prefs = Object.assign({}, DEFAULTS);
            applyPrefs(prefs);
            try { localStorage.removeItem(KEY); } catch (e) { /* nada */ }
            Array.prototype.forEach.call(form.elements, function (input) {
                input.checked = String(prefs[input.name]) === input.value;
            });
            announce('Opciones de accesibilidad restablecidas.');
        });
        prepareModal(overlay);
        return overlay;
    }

    function buildTrigger() {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'a11y-trigger';
        button.id = 'a11yTrigger';
        button.setAttribute('aria-haspopup', 'dialog');
        button.innerHTML = '<i class="fa-solid fa-universal-access" aria-hidden="true"></i> Accesibilidad';
        button.addEventListener('click', FiaxA11y.openPanel);
        var footer = document.querySelector('.sidebar-footer');
        if (footer) footer.insertBefore(button, footer.firstChild);
        else { button.classList.add('floating'); document.body.appendChild(button); }
    }

    var panel;
    window.FiaxA11y = {
        announce: announce,
        openPanel: function () { panel.style.display = 'flex'; },
        closePanel: function () { panel.style.display = 'none'; },
        /** Lleva el foco al encabezado de una sección recién mostrada. */
        focusSection: function (section) {
            if (!section) return;
            var heading = section.querySelector('h1, h2, h3');
            var target = heading || section;
            if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
            target.focus({ preventScroll: false });
        },
        syncNav: syncNav
    };

    document.addEventListener('DOMContentLoaded', function () {
        var main = document.getElementById('contenido');
        if (main) {
            var skip = document.createElement('a');
            skip.href = '#contenido';
            skip.className = 'skip-link';
            skip.textContent = 'Saltar al contenido principal';
            skip.addEventListener('click', function (e) {
                e.preventDefault();
                if (!main.hasAttribute('tabindex')) main.setAttribute('tabindex', '-1');
                main.focus();
            });
            document.body.insertBefore(skip, document.body.firstChild);
        }

        announcer = document.createElement('div');
        announcer.className = 'sr-only';
        announcer.setAttribute('role', 'status');
        announcer.setAttribute('aria-live', 'polite');
        document.body.appendChild(announcer);

        panel = buildPanel();
        buildTrigger();
        enhance(document);

        new MutationObserver(function (mutations) {
            var needs = false;
            for (var i = 0; i < mutations.length; i++) {
                if (mutations[i].type === 'childList' && mutations[i].addedNodes.length) { needs = true; break; }
                if (mutations[i].type === 'attributes') { syncNav(); }
            }
            if (needs) enhance(document);
        }).observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    });
})();
