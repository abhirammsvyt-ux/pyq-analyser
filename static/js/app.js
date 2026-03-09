// PYQ Analyzer - Main Application JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Initialize all components
    initAlerts();
    initAnimations();
    initClusterInteractions();
    initModuleFilter();
    initSearch();
});

// Alert/Message Auto-dismiss
function initAlerts() {
    const alerts = document.querySelectorAll('[class*="alert-"]');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            alert.style.transform = 'translateX(100%)';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
}

// Scroll Animations
function initAnimations() {
    const animatedElements = document.querySelectorAll('.animate-on-scroll');
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.classList.add('animate-slide-up');
                }, index * 100);
                observer.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1
    });
    
    animatedElements.forEach(el => observer.observe(el));
}

// Cluster Interactions
function initClusterInteractions() {
    const clusterItems = document.querySelectorAll('.cluster-item');
    
    clusterItems.forEach(item => {
        item.addEventListener('click', function() {
            this.classList.toggle('expanded');
            const details = this.querySelector('.cluster-details');
            if (details) {
                details.classList.toggle('hidden');
            }
        });
    });
}

// Module Filter
function initModuleFilter() {
    const filterButtons = document.querySelectorAll('[data-module-filter]');
    const clusterItems = document.querySelectorAll('[data-module]');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filterValue = this.getAttribute('data-module-filter');
            
            // Update active button
            filterButtons.forEach(btn => {
                btn.classList.remove('active', 'bg-blue-600', 'text-white');
                btn.classList.add('bg-gray-200', 'text-gray-700');
            });
            this.classList.remove('bg-gray-200', 'text-gray-700');
            this.classList.add('active', 'bg-blue-600', 'text-white');
            
            // Filter clusters
            clusterItems.forEach(item => {
                const itemModule = item.getAttribute('data-module');
                if (filterValue === 'all' || itemModule === filterValue) {
                    item.style.display = 'block';
                    item.classList.add('animate-fade-in');
                } else {
                    item.style.display = 'none';
                }
            });
        });
    });
}

// Search Functionality
function initSearch() {
    const searchInput = document.getElementById('cluster-search');
    if (!searchInput) return;
    
    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();
        const clusters = document.querySelectorAll('.cluster-item');
        
        clusters.forEach(cluster => {
            const text = cluster.textContent.toLowerCase();
            if (text.includes(searchTerm)) {
                cluster.style.display = 'block';
                cluster.classList.add('animate-fade-in');
            } else {
                cluster.style.display = 'none';
            }
        });
    });
}

// Copy to Clipboard
function copyClusterText(element) {
    const text = element.closest('.cluster-item').querySelector('.cluster-topic').textContent;
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    });
}

// Show Notification
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `fixed top-20 right-4 z-50 px-6 py-3 rounded-lg shadow-lg text-white animate-slide-left ${
        type === 'success' ? 'bg-green-500' : 
        type === 'error' ? 'bg-red-500' : 
        'bg-blue-500'
    }`;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Priority Badge Helper
function getPriorityBadge(tier, count) {
    const badges = {
        'tier_1': { emoji: '🔥🔥🔥', text: 'TOP PRIORITY', class: 'badge-tier-1' },
        'tier_2': { emoji: '🔥🔥', text: 'HIGH PRIORITY', class: 'badge-tier-2' },
        'tier_3': { emoji: '🔥', text: 'MEDIUM PRIORITY', class: 'badge-tier-3' },
        'tier_4': { emoji: '✓', text: 'LOW PRIORITY', class: 'badge-tier-4' }
    };
    
    const badge = badges[tier] || badges['tier_4'];
    return `<span class="${badge.class}">${badge.emoji} ${badge.text} (${count}x)</span>`;
}

// Smooth Scroll
function scrollToSection(sectionId) {
    const element = document.getElementById(sectionId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Export to PDF
function exportToPDF(subjectId) {
    window.location.href = `/reports/subject/${subjectId}/analytics/`;
}

// Dark Mode Toggle (Future Enhancement)
function toggleDarkMode() {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('darkMode', document.documentElement.classList.contains('dark'));
}

// Load Dark Mode Preference
if (localStorage.getItem('darkMode') === 'true') {
    document.documentElement.classList.add('dark');
}
