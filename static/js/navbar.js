// Common navbar functionality
function toggleMobileMenu() {
    const navLinks = document.getElementById('navLinks');
    const toggleButton = document.querySelector('.mobile-menu-toggle i');
    
    if (navLinks) {
        navLinks.classList.toggle('mobile-menu-open');
        
        // Update toggle button icon
        if (navLinks.classList.contains('mobile-menu-open')) {
            toggleButton.className = 'fas fa-times';
        } else {
            toggleButton.className = 'fas fa-bars';
        }
    }
}

// Add scroll effect to navbar
let lastScrollTop = 0;
window.addEventListener('scroll', function() {
    const navbar = document.querySelector('.navbar');
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    
    if (scrollTop > 50) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
    
    lastScrollTop = scrollTop;
});

// Close mobile menu when clicking outside
document.addEventListener('click', function(event) {
    const navbar = document.querySelector('.navbar');
    const navLinks = document.getElementById('navLinks');
    const toggleButton = document.querySelector('.mobile-menu-toggle');
    
    if (navLinks && navLinks.classList.contains('mobile-menu-open')) {
        if (!navbar.contains(event.target)) {
            navLinks.classList.remove('mobile-menu-open');
            if (toggleButton) {
                toggleButton.querySelector('i').className = 'fas fa-bars';
            }
        }
    }
});

// Close mobile menu when window is resized to desktop
window.addEventListener('resize', function() {
    const navLinks = document.getElementById('navLinks');
    const toggleButton = document.querySelector('.mobile-menu-toggle i');
    
    if (window.innerWidth > 768) {
        if (navLinks) {
            navLinks.classList.remove('mobile-menu-open');
        }
        if (toggleButton) {
            toggleButton.className = 'fas fa-bars';
        }
    }
});

// Add smooth scroll behavior for in-page navigation
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Add loading states for navigation links
document.addEventListener('DOMContentLoaded', function() {
    const navLinks = document.querySelectorAll('.nav-link:not(.btn-logout)');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            // Add loading state for external navigation
            if (this.href && !this.href.includes('#')) {
                this.style.opacity = '0.7';
                this.style.pointerEvents = 'none';
                
                // Reset after a delay (in case navigation fails)
                setTimeout(() => {
                    this.style.opacity = '1';
                    this.style.pointerEvents = 'auto';
                }, 3000);
            }
        });
    });
});
