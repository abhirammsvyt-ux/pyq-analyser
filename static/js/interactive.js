/**
 * interactive.js — Premium Light Theme
 * PYQ Analyzer Design System — Vanilla JS
 */

/* ──────────────────────────────────────────
   1. PAGE ENTRANCE ANIMATION
────────────────────────────────────────── */
function initPageEntrance() {
  var els = document.querySelectorAll('.animate-entrance');
  els.forEach(function(el) {
    el.style.opacity = '0';
    el.style.transform = 'translateY(16px)';
    el.style.transition = 'opacity 0.6s cubic-bezier(0.23,1,0.32,1), transform 0.6s cubic-bezier(0.23,1,0.32,1)';
  });
  setTimeout(function() {
    document.body.classList.add('loaded');
    els.forEach(function(el, i) {
      setTimeout(function() {
        el.style.opacity = '1';
        el.style.transform = 'translateY(0)';
      }, i * 80);
    });
  }, 50);
}

/* ──────────────────────────────────────────
   2. CURSOR FOLLOWER (desktop only)
────────────────────────────────────────── */
function initCursorFollower() {
  if ('ontouchstart' in window || window.innerWidth < 768) return;
  var dot = document.createElement('div');
  dot.className = 'cursor-dot';
  document.body.appendChild(dot);
  var mx = -100, my = -100;
  document.addEventListener('mousemove', function(e) {
    mx = e.clientX; my = e.clientY;
    dot.style.left = mx + 'px';
    dot.style.top = my + 'px';
  });
  document.querySelectorAll('a[href], button, .btn-slide, .glass-card, .premium-card, .stat-card').forEach(function(el) {
    el.addEventListener('mouseenter', function() {
      dot.style.width = '32px'; dot.style.height = '32px';
      dot.style.background = 'transparent';
      dot.style.border = '2px solid rgba(99,102,241,0.7)';
    });
    el.addEventListener('mouseleave', function() {
      dot.style.width = '12px'; dot.style.height = '12px';
      dot.style.background = 'rgba(99,102,241,0.70)';
      dot.style.border = 'none';
    });
  });
  document.addEventListener('mouseleave', function() { dot.style.opacity = '0'; });
  document.addEventListener('mouseenter', function() { dot.style.opacity = '1'; });
}

/* ──────────────────────────────────────────
   3. NAVBAR SCROLL EFFECT
────────────────────────────────────────── */
function initNavbarScroll() {
  var nav = document.querySelector('.navbar-light-custom, .navbar-light');
  if (!nav) return;
  window.addEventListener('scroll', function() {
    nav.classList.toggle('navbar-scrolled', window.scrollY > 20);
  }, { passive: true });
}

/* ──────────────────────────────────────────
   4. AOS — ANIMATE ON SCROLL
────────────────────────────────────────── */
function initAOS() {
  if (typeof AOS !== 'undefined') {
    AOS.init({ duration: 650, easing: 'cubic-bezier(0.23, 1, 0.32, 1)', once: true, offset: 60 });
    return;
  }
  /* Fallback IntersectionObserver */
  var aosEls = document.querySelectorAll('[data-aos]');
  aosEls.forEach(function(el) {
    el.style.opacity = '0';
    el.style.transform = 'translateY(30px)';
    el.style.transition = 'opacity 0.6s cubic-bezier(0.23,1,0.32,1), transform 0.6s cubic-bezier(0.23,1,0.32,1)';
    var delay = parseInt(el.getAttribute('data-aos-delay') || '0', 10);
    el.style.transitionDelay = delay + 'ms';
  });
  var obs = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
        obs.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  aosEls.forEach(function(el) { obs.observe(el); });
}

/* ──────────────────────────────────────────
   5. VANILLA TILT
────────────────────────────────────────── */
function initVanillaTilt() {
  if (typeof VanillaTilt === 'undefined') return;
  VanillaTilt.init(document.querySelectorAll('.tilt-card'), {
    max: 8, glare: true, 'max-glare': 0.15,
    'glare-prerender': false, scale: 1.02
  });
}

/* ──────────────────────────────────────────
   6. COUNT-UP ANIMATION
────────────────────────────────────────── */
function animateCount(el, target, duration) {
  var start = 0, startTime = null;
  duration = duration || 2000;
  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
  function formatNum(n) {
    return n >= 1000 ? n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',') : n.toString();
  }
  function step(ts) {
    if (!startTime) startTime = ts;
    var progress = Math.min((ts - startTime) / duration, 1);
    el.textContent = formatNum(Math.round(easeOutCubic(progress) * target));
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = formatNum(target);
  }
  requestAnimationFrame(step);
}

function initCountUp() {
  var obs = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        var el = entry.target;
        var target = parseInt(el.getAttribute('data-count') || el.textContent, 10);
        if (!isNaN(target)) animateCount(el, target);
        obs.unobserve(el);
      }
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('.count-up-animated').forEach(function(el) { obs.observe(el); });
  /* Also fire on visible stat numbers immediately if above fold */
  document.querySelectorAll('.stat-number[data-count]').forEach(function(el) {
    var rect = el.getBoundingClientRect();
    if (rect.top < window.innerHeight) {
      var target = parseInt(el.getAttribute('data-count'), 10);
      if (!isNaN(target)) { el.textContent = '0'; animateCount(el, target); }
    } else { obs.observe(el); }
  });
}

/* ──────────────────────────────────────────
   7. TYPEWRITER EFFECT
────────────────────────────────────────── */
function initTypewriter(id, phrases, typingSpeed, deleteSpeed, pause) {
  var el = document.getElementById(id || 'typewriter-text');
  if (!el) return;
  phrases = phrases || ['AI-Powered Question Analysis','Smart Priority Ranking','Module-wise Study Guide','Semantic Question Clustering'];
  typingSpeed = typingSpeed || 70; deleteSpeed = deleteSpeed || 40; pause = pause || 2200;
  var phraseIdx = 0, charIdx = 0, isDeleting = false;

  /* Ensure cursor span exists */
  var cursor = el.querySelector('.typewriter-cursor');
  if (!cursor) {
    cursor = document.createElement('span');
    cursor.className = 'typewriter-cursor';
    el.appendChild(cursor);
  }
  var textNode = document.createTextNode('');
  el.insertBefore(textNode, cursor);

  function tick() {
    var current = phrases[phraseIdx];
    if (isDeleting) {
      charIdx--;
      textNode.textContent = current.slice(0, charIdx);
      if (charIdx === 0) { isDeleting = false; phraseIdx = (phraseIdx + 1) % phrases.length; setTimeout(tick, 400); return; }
      setTimeout(tick, deleteSpeed);
    } else {
      charIdx++;
      textNode.textContent = current.slice(0, charIdx);
      if (charIdx === current.length) { isDeleting = true; setTimeout(tick, pause); return; }
      setTimeout(tick, typingSpeed);
    }
  }
  setTimeout(tick, 800);
}

/* ──────────────────────────────────────────
   8. TEXTROLL 3D FLIP (Flip Board)
────────────────────────────────────────── */
function initTextRoll(id, words, interval) {
  var container = document.getElementById(id || 'textroll-word');
  if (!container) return;
  words = words || ['Analysis','Clustering','Ranking','Reports'];
  interval = interval || 2500;
  var idx = 0;

  function flipWord(newWord) {
    /* Clear old chars */
    while (container.firstChild) container.removeChild(container.firstChild);
    newWord.split('').forEach(function(ch, i) {
      var span = document.createElement('span');
      span.className = 'textroll-char flip-in';
      span.textContent = ch === ' ' ? '\u00A0' : ch;
      span.style.animationDelay = (i * 50) + 'ms';
      container.appendChild(span);
    });
  }

  flipWord(words[idx]);
  setInterval(function() {
    /* Exit animation on current */
    Array.from(container.children).forEach(function(span, i) {
      span.classList.remove('flip-in');
      span.classList.add('flip-out');
      span.style.animationDelay = (i * 40) + 'ms';
    });
    setTimeout(function() {
      idx = (idx + 1) % words.length;
      flipWord(words[idx]);
    }, words[idx > 0 ? idx-1 : words.length-1].length * 40 + 200);
  }, interval);
}

/* ──────────────────────────────────────────
   9. RIPPLE EFFECT
────────────────────────────────────────── */
function initRippleEffects() {
  document.querySelectorAll('.btn-glow, .btn-primary-light, .btn-upload-submit, .btn-slide, .ripple-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      var ripple = document.createElement('span');
      var rect = btn.getBoundingClientRect();
      var size = Math.max(rect.width, rect.height);
      ripple.style.cssText = [
        'position:absolute','border-radius:50%','pointer-events:none',
        'width:' + size + 'px','height:' + size + 'px',
        'left:' + (e.clientX - rect.left - size/2) + 'px',
        'top:' + (e.clientY - rect.top - size/2) + 'px',
        'background:rgba(255,255,255,0.35)',
        'transform:scale(0)','animation:rippleExpand 0.6s ease-out forwards'
      ].join(';');
      /* Ensure relative positioning */
      var pos = window.getComputedStyle(btn).position;
      if (pos === 'static') btn.style.position = 'relative';
      btn.style.overflow = 'hidden';
      btn.appendChild(ripple);
      setTimeout(function() { if (ripple.parentNode) ripple.parentNode.removeChild(ripple); }, 700);
    });
  });
}

/* ──────────────────────────────────────────
   10. FLOATING LABELS (legacy — kept for compat)
────────────────────────────────────────── */
function initFloatingLabels() {
  document.querySelectorAll('.form-control-light, .floating-input').forEach(function(input) {
    function check() {
      if (input.value) input.classList.add('has-value');
      else input.classList.remove('has-value');
    }
    input.addEventListener('input', check);
    input.addEventListener('change', check);
    check();
  });
}

/* ──────────────────────────────────────────
   22. PREMIUM INPUT SYSTEM — Glowing Effects
   Focus/Blur handlers, floating label rebuild,
   content detection, error state management
────────────────────────────────────────── */
function initPremiumInputs() {
  /* Process all floating-label-group containers */
  document.querySelectorAll('.floating-label-group').forEach(function(group) {
    var input = group.querySelector('input, textarea, select');
    if (!input) return;
    if (input.type === 'file' || input.type === 'hidden') return;

    function checkContent() {
      var hasVal = input.value && input.value.trim() !== '';
      group.classList.toggle('has-content', hasVal);
      input.classList.toggle('has-value', hasVal);
    }

    input.addEventListener('focusin', function() {
      group.classList.add('is-focused');
      group.classList.add('has-content');
      group.classList.remove('is-blurred');
    });

    input.addEventListener('focusout', function() {
      group.classList.remove('is-focused');
      group.classList.add('is-blurred');
      setTimeout(function() { group.classList.remove('is-blurred'); }, 500);
      checkContent();
    });

    input.addEventListener('input', checkContent);
    input.addEventListener('change', checkContent);
    checkContent();
  });

  /* Process all reg-field-group containers (register page etc.) */
  document.querySelectorAll('.reg-field-group').forEach(function(group) {
    var input = group.querySelector('input, textarea, select');
    if (!input) return;
    if (input.type === 'file' || input.type === 'hidden') return;

    /* Style Django-rendered inputs */
    if (!input.style.borderRadius) {
      input.style.cssText = 'width:100%;background:#FAFBFF;border:1.5px solid #E2E8F0;border-radius:12px;color:#0F172A;padding:14px 18px;font-size:15px;line-height:1.6;font-family:inherit;outline:none;transition:all 0.3s ease;min-height:52px;height:auto;overflow:visible;white-space:normal;text-overflow:unset;';
    }

    function checkContent() {
      var hasVal = input.value && input.value.trim() !== '';
      group.classList.toggle('has-content', hasVal);
    }

    input.addEventListener('focusin', function() {
      group.classList.add('is-focused');
      group.classList.remove('is-blurred');
    });

    input.addEventListener('focusout', function() {
      group.classList.remove('is-focused');
      group.classList.add('is-blurred');
      setTimeout(function() { group.classList.remove('is-blurred'); }, 500);
      checkContent();
    });

    input.addEventListener('input', checkContent);
    input.addEventListener('change', checkContent);
    checkContent();

    /* Mark groups with Django errors */
    if (group.querySelector('.reg-field-error')) {
      group.classList.add('has-error');
    }
  });
}

/* ──────────────────────────────────────────
   23. SLIDE BUTTON — Slide-to-confirm submit
────────────────────────────────────────── */
function initSlideButton() {
  var container = document.querySelector('.slide-btn-container');
  if (!container) return;

  var handle = container.querySelector('.slide-btn-handle');
  var fill = container.querySelector('.slide-btn-fill');
  var hint = container.querySelector('.slide-btn-hint');
  var form = container.closest('form');
  if (!handle || !fill || !hint || !form) return;

  var isDragging = false;
  var startX = 0;
  var handleStartX = 4;
  var maxDrag = 0;
  var triggered = false;

  function getMaxDrag() {
    return container.offsetWidth - handle.offsetWidth - 8;
  }

  function setPosition(x) {
    x = Math.max(0, Math.min(x, maxDrag));
    handle.style.left = (x + 4) + 'px';
    fill.style.width = (x + handle.offsetWidth / 2 + 4) + 'px';

    /* Update hint opacity based on drag progress */
    var progress = x / maxDrag;
    if (progress > 0.15) {
      hint.style.opacity = 1 - (progress - 0.15) / 0.5;
    } else {
      hint.style.opacity = '1';
    }
  }

  function snapBack() {
    handle.classList.add('snapping');
    fill.classList.add('snapping');
    setPosition(0);
    hint.style.opacity = '1';
    setTimeout(function() {
      handle.classList.remove('snapping');
      fill.classList.remove('snapping');
    }, 450);
  }

  function triggerSubmit() {
    triggered = true;
    /* Success state */
    handle.classList.add('success');
    handle.innerHTML = '<svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg>';
    handle.querySelector('svg').style.animation = 'checkPop 0.4s ease both';
    hint.textContent = 'Uploading...';
    hint.classList.add('uploading');
    hint.style.opacity = '1';

    /* Submit after a brief visual pause */
    setTimeout(function() {
      form.submit();
    }, 600);
  }

  /* Mouse events */
  handle.addEventListener('mousedown', function(e) {
    if (triggered) return;
    isDragging = true;
    maxDrag = getMaxDrag();
    startX = e.clientX;
    handleStartX = parseInt(handle.style.left || '4', 10) - 4;
    handle.classList.remove('snapping');
    fill.classList.remove('snapping');
    e.preventDefault();
  });

  document.addEventListener('mousemove', function(e) {
    if (!isDragging) return;
    var dx = e.clientX - startX;
    setPosition(handleStartX + dx);
  });

  document.addEventListener('mouseup', function() {
    if (!isDragging) return;
    isDragging = false;
    var currentX = parseInt(handle.style.left || '4', 10) - 4;
    if (currentX >= maxDrag * 0.85) {
      setPosition(maxDrag);
      triggerSubmit();
    } else {
      snapBack();
    }
  });

  /* Touch events */
  handle.addEventListener('touchstart', function(e) {
    if (triggered) return;
    isDragging = true;
    maxDrag = getMaxDrag();
    startX = e.touches[0].clientX;
    handleStartX = parseInt(handle.style.left || '4', 10) - 4;
    handle.classList.remove('snapping');
    fill.classList.remove('snapping');
  }, { passive: true });

  document.addEventListener('touchmove', function(e) {
    if (!isDragging) return;
    var dx = e.touches[0].clientX - startX;
    setPosition(handleStartX + dx);
  }, { passive: true });

  document.addEventListener('touchend', function() {
    if (!isDragging) return;
    isDragging = false;
    var currentX = parseInt(handle.style.left || '4', 10) - 4;
    if (currentX >= maxDrag * 0.85) {
      setPosition(maxDrag);
      triggerSubmit();
    } else {
      snapBack();
    }
  });
}

/* ──────────────────────────────────────────
   24. FEATURE CARD GLOW — Mouse-tracking
────────────────────────────────────────── */
function initFeatureCardGlow() {
  var cards = document.querySelectorAll('.feature-card-light');
  if (!cards.length) return;

  /* Add glow border div to each card */
  cards.forEach(function(card) {
    if (card.querySelector('.glow-border')) return;
    var glow = document.createElement('div');
    glow.className = 'glow-border';
    card.insertBefore(glow, card.firstChild);
  });

  document.addEventListener('mousemove', function(e) {
    cards.forEach(function(card) {
      var rect = card.getBoundingClientRect();
      var cx = rect.left + rect.width / 2;
      var cy = rect.top + rect.height / 2;

      /* Check if mouse is within 80px of card boundary */
      var closestX = Math.max(rect.left, Math.min(e.clientX, rect.right));
      var closestY = Math.max(rect.top, Math.min(e.clientY, rect.bottom));
      var dist = Math.hypot(e.clientX - closestX, e.clientY - closestY);

      var glow = card.querySelector('.glow-border');
      if (!glow) return;

      if (dist <= 80) {
        /* Calculate angle from card center to mouse */
        var angle = Math.atan2(e.clientY - cy, e.clientX - cx);
        var deg = angle * (180 / Math.PI) + 90;
        card.style.setProperty('--glow-start', deg + 'deg');
        glow.classList.add('visible');
      } else {
        glow.classList.remove('visible');
      }
    });
  });
}

/* ──────────────────────────────────────────
   25. UPLOAD ZONE GLOW — Drag-over rainbow
────────────────────────────────────────── */
function initUploadZoneGlow() {
  document.querySelectorAll('.upload-zone-light').forEach(function(zone) {
    ['dragenter', 'dragover'].forEach(function(ev) {
      zone.addEventListener(ev, function(e) {
        e.preventDefault();
        zone.classList.add('glow-active');
        zone.classList.add('drag-over');
      });
    });
    ['dragleave', 'drop'].forEach(function(ev) {
      zone.addEventListener(ev, function() {
        zone.classList.remove('glow-active');
        zone.classList.remove('drag-over');
      });
    });
  });

  /* Also apply glow to .upload-zone-sm on drag */
  document.querySelectorAll('.upload-zone-sm').forEach(function(zone) {
    ['dragenter', 'dragover'].forEach(function(ev) {
      zone.addEventListener(ev, function(e) {
        e.preventDefault();
        zone.classList.add('glow-active');
        zone.classList.add('upload-zone-light');
      });
    });
    ['dragleave', 'drop'].forEach(function(ev) {
      zone.addEventListener(ev, function() {
        zone.classList.remove('glow-active');
        zone.classList.remove('upload-zone-light');
      });
    });
  });
}

/* ──────────────────────────────────────────
   11. UPLOAD ZONE DRAG & DROP
────────────────────────────────────────── */
function initUploadZones() {
  document.querySelectorAll('.upload-zone').forEach(function(zone) {
    var input = zone.querySelector('input[type="file"]');

    zone.addEventListener('dragover', function(e) {
      e.preventDefault(); e.stopPropagation();
      zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', function(e) {
      if (!zone.contains(e.relatedTarget)) zone.classList.remove('dragover');
    });
    zone.addEventListener('drop', function(e) {
      e.preventDefault(); e.stopPropagation();
      zone.classList.remove('dragover');
      if (input && e.dataTransfer.files.length) {
        try {
          var dt = new DataTransfer();
          Array.from(e.dataTransfer.files).forEach(function(f) { dt.items.add(f); });
          input.files = dt.files;
          input.dispatchEvent(new Event('change', { bubbles: true }));
        } catch(ex) { /* Safari fallback */ }
      }
    });

    /* Click zone → open file picker */
    zone.addEventListener('click', function(e) {
      if (e.target !== input && input) input.click();
    });

    /* Show file list */
    if (input) {
      input.addEventListener('change', function() {
        var container = zone.closest('.upload-section, form') && document.getElementById(zone.dataset.listTarget || 'fileListContainer');
        if (!container) container = zone.nextElementSibling && zone.nextElementSibling.classList.contains('file-list-container') ? zone.nextElementSibling : null;
        if (container) showFileList(Array.from(input.files), container);
      });
    }
  });
}

function showFileList(files, container) {
  container.innerHTML = '';
  if (!files.length) { container.style.maxHeight = '0'; return; }
  container.style.maxHeight = (files.length * 56 + 16) + 'px';
  files.forEach(function(file, i) {
    var item = document.createElement('div');
    item.className = 'file-list-item';
    item.style.cssText = 'opacity:0;transform:translateX(-16px);transition:opacity 0.3s ease,transform 0.3s ease;';
    var sizeStr = file.size > 1048576 ? (file.size/1048576).toFixed(1) + ' MB' : Math.round(file.size/1024) + ' KB';
    item.innerHTML = [
      '<div style="display:flex;align-items:center;gap:0.75rem;padding:0.6rem 0.8rem;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;">',
      '<span style="color:#10B981;font-size:1.1rem;">✓</span>',
      '<span style="flex:1;font-size:0.87rem;color:#0F172A;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="'+file.name+'">'+file.name+'</span>',
      '<span style="color:#94A3B8;font-size:0.78rem;white-space:nowrap;">'+sizeStr+'</span>',
      '</div>'
    ].join('');
    container.appendChild(item);
    setTimeout(function() { item.style.opacity='1'; item.style.transform='translateX(0)'; }, i * 80 + 50);
  });
}

/* ──────────────────────────────────────────
   12. ANIMATED BEAM (SVG Paths)
────────────────────────────────────────── */
function initAnimatedBeam() {
  var section = document.getElementById('beam-section');
  if (!section) return;
  var nodes = section.querySelectorAll('.beam-node');
  if (nodes.length < 2) return;

  var svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;overflow:visible;z-index:0;';
  section.style.position = 'relative';
  section.insertBefore(svg, section.firstChild);

  var defs = document.createElementNS('http://www.w3.org/2000/svg','defs');
  svg.appendChild(defs);

  var paths = [], animations = [];

  function buildPaths() {
    while (svg.childNodes.length > 1) svg.removeChild(svg.lastChild);

    var sectionRect = section.getBoundingClientRect();
    var nodeArr = Array.from(nodes);

    for (var i = 0; i < nodeArr.length - 1; i++) {
      var r1 = nodeArr[i].getBoundingClientRect();
      var r2 = nodeArr[i+1].getBoundingClientRect();
      var x1 = r1.left - sectionRect.left + r1.width/2;
      var y1 = r1.top  - sectionRect.top  + r1.height/2;
      var x2 = r2.left - sectionRect.left + r2.width/2;
      var y2 = r2.top  - sectionRect.top  + r2.height/2;

      var cx = (x1 + x2)/2, cy = Math.min(y1,y2) - 40;

      /* gradient */
      var grad = document.createElementNS('http://www.w3.org/2000/svg','linearGradient');
      grad.id = 'beamGrad'+i;
      grad.setAttribute('gradientUnits','userSpaceOnUse');
      grad.setAttribute('x1',x1); grad.setAttribute('y1',y1);
      grad.setAttribute('x2',x2); grad.setAttribute('y2',y2);
      var s1 = document.createElementNS('http://www.w3.org/2000/svg','stop');
      s1.setAttribute('offset','0%'); s1.setAttribute('stop-color','#6366F1');
      var s2 = document.createElementNS('http://www.w3.org/2000/svg','stop');
      s2.setAttribute('offset','100%'); s2.setAttribute('stop-color','#8B5CF6');
      grad.appendChild(s1); grad.appendChild(s2);
      defs.appendChild(grad);

      var d = 'M '+x1+' '+y1+' Q '+cx+' '+cy+' '+x2+' '+y2;
      var track = document.createElementNS('http://www.w3.org/2000/svg','path');
      track.setAttribute('d',d);
      track.setAttribute('fill','none');
      track.setAttribute('stroke','#E2E8F0');
      track.setAttribute('stroke-width','2');
      svg.appendChild(track);

      var beam = document.createElementNS('http://www.w3.org/2000/svg','path');
      beam.setAttribute('d',d);
      beam.setAttribute('fill','none');
      beam.setAttribute('stroke','url(#beamGrad'+i+')');
      beam.setAttribute('stroke-width','2.5');
      beam.setAttribute('stroke-linecap','round');
      svg.appendChild(beam);

      var len = beam.getTotalLength ? beam.getTotalLength() : 300;
      beam.setAttribute('stroke-dasharray', len*0.25);
      beam.setAttribute('stroke-dashoffset', len);
      paths.push({ el: beam, len: len, offset: len });
    }
  }

  function animateBeams(ts) {
    paths.forEach(function(p) {
      p.offset -= 1.5;
      if (p.offset < -p.len * 0.25) p.offset = p.len;
      p.el.setAttribute('stroke-dashoffset', p.offset);
    });
    requestAnimationFrame(animateBeams);
  }

  buildPaths();
  window.addEventListener('resize', function() { paths.length = 0; defs.innerHTML = ''; buildPaths(); });
  requestAnimationFrame(animateBeams);
}

/* ──────────────────────────────────────────
   13. STEP INDICATOR PROGRESS
────────────────────────────────────────── */
function initStepIndicator() {
  var indicator = document.getElementById('step-indicator');
  if (!indicator) return;

  function updateSteps() {
    var completedEl = document.getElementById('stat-completed');
    var totalEl     = document.getElementById('stat-total') || document.getElementById('totalPapersCount');
    if (!completedEl || !totalEl) return;
    var completed = parseInt(completedEl.textContent, 10) || 0;
    var total     = parseInt(totalEl.textContent, 10) || 1;
    var progress  = Math.min(completed / total, 1);
    /* Map progress to 4 steps: 0-0.25 step1, 0.25-0.5 step2, 0.5-0.75 step3, 0.75-1 step4 */
    var steps = indicator.querySelectorAll('.step-dot');
    var connectors = indicator.querySelectorAll('.step-connector-fill');
    steps.forEach(function(dot, i) {
      var threshold = (i+1) / steps.length;
      if (progress >= threshold) { dot.classList.add('step-active'); dot.classList.add('step-done'); }
      else { dot.classList.remove('step-done'); }
    });
    connectors.forEach(function(conn, i) {
      var pct = Math.max(0, Math.min(100, (progress - i/connectors.length) / (1/connectors.length) * 100));
      conn.style.width = pct + '%';
      conn.style.transition = 'width 0.8s cubic-bezier(0.23,1,0.32,1)';
    });
  }

  updateSteps();
  setInterval(updateSteps, 2000);
}

/* ──────────────────────────────────────────
   14. MOBILE DOCK MAGNIFICATION
────────────────────────────────────────── */
function initMobileDock() {
  var dock = document.getElementById('mobileDock');
  if (!dock) return;
  var items = dock.querySelectorAll('.dock-item');
  var targets = Array.from(items).map(function() { return 1; });
  var MAXSCALE = 1.5, RADIUS = 100;

  function lerp(a,b,t){ return a + (b-a)*t; }

  function onMove(e) {
    var touch = e.touches ? e.touches[0] : e;
    items.forEach(function(item, i) {
      var rect = item.getBoundingClientRect();
      var cx = rect.left + rect.width/2, cy = rect.top + rect.height/2;
      var dist = Math.hypot(touch.clientX - cx, touch.clientY - cy);
      targets[i] = 1 + (MAXSCALE-1) * Math.max(0, 1 - dist/RADIUS);
    });
  }

  function onLeave() { targets = targets.map(function(){ return 1; }); }

  dock.addEventListener('mousemove', onMove);
  dock.addEventListener('touchmove', function(e){ onMove(e); }, { passive: true });
  dock.addEventListener('mouseleave', onLeave);
  dock.addEventListener('touchend', onLeave);

  var current = targets.map(function(){ return 1; });
  function loop() {
    items.forEach(function(item, i) {
      current[i] = lerp(current[i], targets[i], 0.2);
      item.style.transform = 'scale(' + current[i] + ')';
    });
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

/* ──────────────────────────────────────────
   15. SMOOTH SCROLL
────────────────────────────────────────── */
function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(function(link) {
    link.addEventListener('click', function(e) {
      var target = document.querySelector(link.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });
}

/* ──────────────────────────────────────────
   16. CHART.JS LIGHT DEFAULTS
────────────────────────────────────────── */
function initChartDefaults() {
  if (typeof Chart === 'undefined') return;
  Chart.defaults.color = '#64748B';
  Chart.defaults.borderColor = '#E2E8F0';
  if (Chart.defaults.font) Chart.defaults.font.family = "'Inter', sans-serif";
}

/* ──────────────────────────────────────────
   17. GSAP SCROLL ANIMATIONS
────────────────────────────────────────── */
function initGSAP() {
  if (typeof gsap === 'undefined') return;
  gsap.from('.hero-heading', { opacity: 0, y: 40, duration: 0.9, ease: 'power3.out', delay: 0.1 });
  gsap.from('.hero-subtitle', { opacity: 0, y: 30, duration: 0.8, ease: 'power3.out', delay: 0.3 });
  gsap.from('.hero-actions', { opacity: 0, y: 20, duration: 0.7, ease: 'power3.out', delay: 0.5 });
  var featureCards = gsap.utils.toArray ? gsap.utils.toArray('.feature-card') : [];
  if (featureCards.length) {
    gsap.from(featureCards, { opacity: 0, y: 50, duration: 0.7, stagger: 0.15, ease: 'power3.out', scrollTrigger: { trigger: '.features-section', start: 'top 80%' } });
  }
}

/* ──────────────────────────────────────────
   18. ANIME.JS MICRO INTERACTIONS
────────────────────────────────────────── */
function initAnime() {
  if (typeof anime === 'undefined') return;
  var dangerIcons = document.querySelectorAll('.danger-icon');
  if (dangerIcons.length) {
    anime({ targets: dangerIcons, scale: [0.8, 1], opacity: [0, 1], duration: 600, easing: 'easeOutElastic(1, .8)' });
  }
  document.querySelectorAll('.stat-card').forEach(function(card) {
    card.addEventListener('mouseenter', function() {
      anime({ targets: card.querySelector('.stat-number'), scale: 1.05, duration: 200, easing: 'easeOutQuad' });
    });
    card.addEventListener('mouseleave', function() {
      anime({ targets: card.querySelector('.stat-number'), scale: 1, duration: 200, easing: 'easeOutQuad' });
    });
  });
}

/* ──────────────────────────────────────────
   19. NOTIFICATION TOASTS
────────────────────────────────────────── */
function showToast(message, type, duration) {
  type = type || 'info'; duration = duration || 4000;
  var colors = { success:'#10B981', error:'#EF4444', warning:'#F59E0B', info:'#6366F1' };
  var container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = 'position:fixed;bottom:2rem;right:2rem;z-index:99999;display:flex;flex-direction:column;gap:0.75rem;pointer-events:none;';
    document.body.appendChild(container);
  }
  var toast = document.createElement('div');
  toast.style.cssText = [
    'background:#FFFFFF','border-left:4px solid '+(colors[type]||colors.info),
    'border-radius:12px','padding:0.85rem 1.2rem',
    'box-shadow:0 8px 30px rgba(0,0,0,0.12)','max-width:320px',
    'font-size:0.875rem','color:#0F172A','pointer-events:auto',
    'transform:translateX(120%)','transition:transform 0.4s cubic-bezier(0.23,1,0.32,1),opacity 0.4s ease',
    'opacity:0'
  ].join(';');
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(function() { toast.style.transform = 'translateX(0)'; toast.style.opacity = '1'; }, 20);
  setTimeout(function() {
    toast.style.transform = 'translateX(120%)'; toast.style.opacity = '0';
    setTimeout(function() { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 450);
  }, duration);
}
window.showToast = showToast;

/* ──────────────────────────────────────────
   20. SVG MARCHING DASHES
────────────────────────────────────────── */
function initMarchingDashes() {
  document.querySelectorAll('.upload-zone').forEach(function(zone) {
    if (zone.querySelector('.marching-svg')) return;
    var svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
    svg.classList.add('marching-svg');
    svg.style.cssText = 'position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;border-radius:inherit;';
    var rect = document.createElementNS('http://www.w3.org/2000/svg','rect');
    rect.setAttribute('x','2'); rect.setAttribute('y','2'); rect.setAttribute('rx','14'); rect.setAttribute('ry','14');
    rect.setAttribute('width','calc(100% - 4)'); rect.setAttribute('height','calc(100% - 4)');
    rect.setAttribute('fill','none'); rect.setAttribute('stroke','#6366F1');
    rect.setAttribute('stroke-width','2'); rect.setAttribute('stroke-dasharray','8 4');
    rect.style.animation = 'marchingDashes 1s linear infinite';
    svg.appendChild(rect);
    zone.style.position = 'relative';
    zone.insertBefore(svg, zone.firstChild);
  });
}

/* ──────────────────────────────────────────
   21. PROGRESS SHIMMER
────────────────────────────────────────── */
function ensureRippleKeyframe() {
  if (document.getElementById('jsKeyframes')) return;
  var style = document.createElement('style');
  style.id = 'jsKeyframes';
  style.textContent = '@keyframes rippleExpand{0%{transform:scale(0);opacity:0.6}100%{transform:scale(4);opacity:0}}';
  document.head.appendChild(style);
}

/* ──────────────────────────────────────────
   INIT
────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', function() {
  ensureRippleKeyframe();
  initPageEntrance();
  initCursorFollower();
  initNavbarScroll();
  initAOS();
  initVanillaTilt();
  initCountUp();
  initTypewriter();
  initTextRoll();
  initRippleEffects();
  initFloatingLabels();
  initPremiumInputs();
  initSlideButton();
  initFeatureCardGlow();
  initUploadZoneGlow();
  initUploadZones();
  initMarchingDashes();
  initAnimatedBeam();
  initStepIndicator();
  initMobileDock();
  initSmoothScroll();
  initChartDefaults();
  setTimeout(function() {
    initGSAP();
    initAnime();
  }, 100);
});
