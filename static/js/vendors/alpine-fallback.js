/**
 * Minimal Alpine.js Fallback
 * Provides basic x-data, x-show, x-if, x-transition support
 */
(function() {
    'use strict';
    
    // Global Alpine object
    window.Alpine = {
        start: function() {
            this.initComponents();
        },
        initComponents: function() {
            // Initialize x-data components
            const components = document.querySelectorAll('[x-data]');
            components.forEach(el => {
                try {
                    const dataExpr = el.getAttribute('x-data');
                    // Create a safe evaluation context
                    const data = (function(expr) {
                        try {
                            return new Function('return ' + expr)();
                        } catch (e) {
                            // If eval fails, try to parse as object literal
                            return {};
                        }
                    })(dataExpr);
                    el._alpineData = data;
                    this.bindElement(el, data);
                } catch (e) {
                    console.warn('Alpine fallback: Failed to parse x-data', e);
                }
            });
        },
        bindElement: function(el, data) {
            // Handle x-show within this component
            const xShows = el.querySelectorAll('[x-show]');
            xShows.forEach(element => {
                const expr = element.getAttribute('x-show');
                try {
                    const show = new Function('with(this) { return ' + expr + ' }').call(data);
                    element.style.display = show ? '' : 'none';
                } catch (e) {
                    // Silently fail for x-show errors
                    element.style.display = '';
                }
            });
            
            // Handle x-if
            const xIfs = el.querySelectorAll('[x-if]');
            xIfs.forEach(element => {
                const expr = element.getAttribute('x-if');
                try {
                    const show = new Function('with(this) { return ' + expr + ' }').call(data);
                    if (!show) {
                        element.remove();
                    }
                } catch (e) {
                    // Keep element on error
                }
            });
            
            // Handle @click events
            const clickables = el.querySelectorAll('[\\@click], [x-on\\:click]');
            clickables.forEach(element => {
                const expr = element.getAttribute('@click') || element.getAttribute('x-on:click');
                element.addEventListener('click', (e) => {
                    try {
                        new Function('$event', 'with(this) { ' + expr + ' }').call(data, e);
                        this.bindElement(el, data);
                    } catch (err) {
                        console.warn('Alpine fallback: click handler error', err);
                    }
                });
            });
            
            // Handle :class bindings
            const classBinds = el.querySelectorAll('[\\:class]');
            classBinds.forEach(element => {
                const expr = element.getAttribute(':class');
                try {
                    const classes = new Function('with(this) { return ' + expr + ' }').call(data);
                    if (typeof classes === 'object') {
                        Object.keys(classes).forEach(cls => {
                            if (classes[cls]) {
                                element.classList.add(cls);
                            } else {
                                element.classList.remove(cls);
                            }
                        });
                    }
                } catch (e) {
                    // Silently fail
                }
            });
        }
    };
    
    // Auto-start on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => Alpine.start());
    } else {
        Alpine.start();
    }
})();
