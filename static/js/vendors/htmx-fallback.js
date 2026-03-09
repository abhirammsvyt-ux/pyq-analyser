/**
 * Minimal HTMX Fallback
 * Provides basic hx-get, hx-post, hx-target, hx-swap support
 */
(function() {
    'use strict';
    
    // Global htmx object
    window.htmx = {
        process: function(element) {
            const els = element ? [element] : document.querySelectorAll('[hx-get], [hx-post], [hx-put], [hx-delete]');
            
            els.forEach(el => {
                if (el._htmxBound) return;
                el._htmxBound = true;
                
                const trigger = el.getAttribute('hx-trigger') || 'click';
                
                el.addEventListener(trigger, async (e) => {
                    e.preventDefault();
                    
                    const method = el.getAttribute('hx-get') ? 'GET' :
                                  el.getAttribute('hx-post') ? 'POST' :
                                  el.getAttribute('hx-put') ? 'PUT' :
                                  el.getAttribute('hx-delete') ? 'DELETE' : 'GET';
                    
                    const url = el.getAttribute(`hx-${method.toLowerCase()}`) || el.getAttribute('hx-get');
                    const target = el.getAttribute('hx-target');
                    const swap = el.getAttribute('hx-swap') || 'innerHTML';
                    
                    if (!url) return;
                    
                    try {
                        const response = await fetch(url, {
                            method: method,
                            headers: {
                                'HX-Request': 'true',
                                'X-Requested-With': 'XMLHttpRequest'
                            }
                        });
                        
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        
                        const html = await response.text();
                        const targetEl = target ? document.querySelector(target) : el;
                        
                        if (targetEl) {
                            if (swap === 'innerHTML') {
                                targetEl.innerHTML = html;
                            } else if (swap === 'outerHTML') {
                                targetEl.outerHTML = html;
                            } else if (swap === 'beforebegin') {
                                targetEl.insertAdjacentHTML('beforebegin', html);
                            } else if (swap === 'afterbegin') {
                                targetEl.insertAdjacentHTML('afterbegin', html);
                            } else if (swap === 'beforeend') {
                                targetEl.insertAdjacentHTML('beforeend', html);
                            } else if (swap === 'afterend') {
                                targetEl.insertAdjacentHTML('afterend', html);
                            }
                            
                            // Trigger afterSwap event
                            document.body.dispatchEvent(new Event('htmx:afterSwap'));
                        }
                    } catch (error) {
                        console.error('HTMX fallback error:', error);
                    }
                });
            });
        }
    };
    
    // Process elements on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            htmx.process();
            startObserver();
        });
    } else {
        htmx.process();
        startObserver();
    }
    
    // Watch for new elements
    function startObserver() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) {
                        htmx.process(node);
                    }
                });
            });
        });
        
        if (document.body) {
            observer.observe(document.body, { childList: true, subtree: true });
        }
    }
})();
