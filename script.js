// DOM Elements
const navbar = document.getElementById('navbar');
const hamburger = document.getElementById('hamburger');
const navMenu = document.getElementById('nav-menu');
const navLinks = document.querySelectorAll('.nav-link');

// Navbar scroll effect
window.addEventListener('scroll', () => {
    if (window.scrollY > 100) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
});

// Mobile menu toggle
hamburger.addEventListener('click', () => {
    hamburger.classList.toggle('active');
    navMenu.classList.toggle('active');
    document.body.style.overflow = navMenu.classList.contains('active') ? 'hidden' : 'auto';
});

// Close mobile menu when clicking on links
navLinks.forEach(link => {
    link.addEventListener('click', () => {
        hamburger.classList.remove('active');
        navMenu.classList.remove('active');
        document.body.style.overflow = 'auto';
    });
});

// Close mobile menu when clicking outside
document.addEventListener('click', (e) => {
    if (!navbar.contains(e.target) && navMenu.classList.contains('active')) {
        hamburger.classList.remove('active');
        navMenu.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
});

// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            const headerOffset = 80;
            const elementPosition = target.getBoundingClientRect().top;
            const offsetPosition = elementPosition + window.pageYOffset - headerOffset;

            window.scrollTo({
                top: offsetPosition,
                behavior: 'smooth'
            });
        }
    });
});

// Intersection Observer for animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe elements for animation
const animateElements = document.querySelectorAll('.theory-card, .book-card, .teaching-card, .story-card, .community-card, .download-card');

animateElements.forEach(element => {
    element.style.opacity = '0';
    element.style.transform = 'translateY(30px)';
    element.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(element);
});

// Parallax effect for hero background
window.addEventListener('scroll', () => {
    const scrolled = window.pageYOffset;
    const heroBackground = document.querySelector('.hero-background');
    if (heroBackground) {
        const speed = scrolled * 0.5;
        heroBackground.style.transform = `translateY(${speed}px)`;
    }
});

// Button interactions
document.addEventListener('DOMContentLoaded', () => {
    // Add click events to all buttons
    const buttons = document.querySelectorAll('button, .button');
    
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            // Create ripple effect
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
    
    // Handle CTA button clicks
    const ctaButtons = document.querySelectorAll('.cta-button, .primary-button');
    ctaButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Scroll to about section or show modal
            const aboutSection = document.getElementById('about');
            if (aboutSection) {
                aboutSection.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
    
    // Handle book buttons
    const bookButtons = document.querySelectorAll('.book-button');
    bookButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            const buttonText = e.target.textContent;
            if (buttonText.includes('購買') || buttonText.includes('立即購買')) {
                // Redirect to purchase page or show purchase modal
                alert('將導向購書頁面');
            } else if (buttonText.includes('了解更多')) {
                // Show more information
                alert('顯示更多書籍資訊');
            }
        });
    });
    
    // Handle teaching buttons
    const teachingButtons = document.querySelectorAll('.teaching-button');
    teachingButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Open video or audio player
            alert('將開啟講經內容');
        });
    });
    
    // Handle community buttons
    const communityButtons = document.querySelectorAll('.community-button, .method-button');
    communityButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            const buttonText = e.target.textContent;
            if (buttonText.includes('Facebook') || buttonText.includes('社團')) {
                window.open('https://www.facebook.com/', '_blank');
            } else if (buttonText.includes('微信') || buttonText.includes('公眾號')) {
                alert('請在微信中搜索：TaiGuangLin 或 askTaiGuangLin');
            } else if (buttonText.includes('QQ') || buttonText.includes('群組')) {
                alert('QQ群號：481903304');
            } else if (buttonText.includes('頻道') || buttonText.includes('收聽')) {
                alert('將開啟語音頻道');
            }
        });
    });
    
    // Handle download buttons
    const downloadButtons = document.querySelectorAll('.download-button');
    downloadButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            const buttonText = e.target.textContent;
            if (buttonText.includes('PDF')) {
                alert('開始下載 PDF 電子書');
            } else if (buttonText.includes('音頻')) {
                alert('開始下載講經音頻合集');
            } else if (buttonText.includes('模板')) {
                alert('開始下載修行日誌模板');
            }
        });
    });
});

// Add ripple effect CSS dynamically
const style = document.createElement('style');
style.textContent = `
    button, .button {
        position: relative;
        overflow: hidden;
    }
    
    .ripple {
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.6);
        transform: scale(0);
        animation: ripple-animation 0.6s linear;
        pointer-events: none;
    }
    
    @keyframes ripple-animation {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Lazy loading for images (if we add images later)
const lazyImages = document.querySelectorAll('img[data-src]');
if (lazyImages.length > 0) {
    const imageObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const img = entry.target;
                img.src = img.dataset.src;
                img.classList.remove('lazy');
                imageObserver.unobserve(img);
            }
        });
    });
    
    lazyImages.forEach(img => imageObserver.observe(img));
}

// Scroll to top functionality
let scrollToTopButton;

// Create scroll to top button
function createScrollToTopButton() {
    scrollToTopButton = document.createElement('button');
    scrollToTopButton.innerHTML = '<i class="fas fa-chevron-up"></i>';
    scrollToTopButton.className = 'scroll-to-top';
    scrollToTopButton.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: linear-gradient(135deg, #ffb6c1 0%, #ff69b4 100%);
        border: none;
        color: white;
        font-size: 1.2rem;
        cursor: pointer;
        opacity: 0;
        visibility: hidden;
        transition: all 0.3s ease;
        z-index: 999;
        box-shadow: 0 4px 12px rgba(255, 105, 180, 0.3);
    `;
    
    scrollToTopButton.addEventListener('click', () => {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
    
    document.body.appendChild(scrollToTopButton);
}

// Show/hide scroll to top button
function toggleScrollToTopButton() {
    if (window.pageYOffset > 300) {
        scrollToTopButton.style.opacity = '1';
        scrollToTopButton.style.visibility = 'visible';
    } else {
        scrollToTopButton.style.opacity = '0';
        scrollToTopButton.style.visibility = 'hidden';
    }
}

// Initialize scroll to top button
document.addEventListener('DOMContentLoaded', () => {
    createScrollToTopButton();
    window.addEventListener('scroll', toggleScrollToTopButton);
});

// Performance optimization: Throttle scroll events
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}

// Apply throttling to scroll events
window.addEventListener('scroll', throttle(() => {
    // Navbar scroll effect (throttled)
    if (window.scrollY > 100) {
        navbar.classList.add('scrolled');
    } else {
        navbar.classList.remove('scrolled');
    }
    
    // Parallax effect (throttled)
    const scrolled = window.pageYOffset;
    const heroBackground = document.querySelector('.hero-background');
    if (heroBackground) {
        const speed = scrolled * 0.3;
        heroBackground.style.transform = `translateY(${speed}px)`;
    }
}, 16)); // ~60fps