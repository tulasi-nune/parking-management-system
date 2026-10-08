// Modal Management JavaScript
class ModalManager {
    constructor() {
        this.activeModal = null;
        this.setupEventListeners();
    }
    
    show(modalId, title, content, buttons = []) {
        const modal = this.createModal(modalId, title, content, buttons);
        document.body.appendChild(modal);
        
        // Trigger show animation
        setTimeout(() => {
            modal.classList.add('show');
        }, 10);
        
        this.activeModal = modal;
        
        // Focus trap
        this.trapFocus(modal);
        
        return modal;
    }
    
    hide(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
            setTimeout(() => {
                modal.remove();
                this.activeModal = null;
            }, 300);
        }
    }
    
    confirm(title, message, onConfirm, onCancel) {
        const buttons = [
            {
                text: 'Cancel',
                class: 'btn-outline-primary',
                onclick: () => {
                    this.hide('confirm-modal');
                    if (onCancel) onCancel();
                }
            },
            {
                text: 'Confirm',
                class: 'btn-primary',
                onclick: () => {
                    this.hide('confirm-modal');
                    if (onConfirm) onConfirm();
                }
            }
        ];
        
        return this.show('confirm-modal', title, message, buttons);
    }
    
    alert(title, message, onClose) {
        const buttons = [
            {
                text: 'OK',
                class: 'btn-primary',
                onclick: () => {
                    this.hide('alert-modal');
                    if (onClose) onClose();
                }
            }
        ];
        
        return this.show('alert-modal', title, message, buttons);
    }
    
    createModal(id, title, content, buttons) {
        const modal = document.createElement('div');
        modal.id = id;
        modal.className = 'modal fade-in';
        
        const buttonsHtml = buttons.map(btn => 
            `<button type="button" class="btn ${btn.class}" onclick="${btn.onclick ? 'this.clickHandler()' : ''}">${btn.text}</button>`
        ).join('');
        
        modal.innerHTML = `
            <div class="modal-content slide-up">
                <div class="modal-header">
                    <h5 class="modal-title">${title}</h5>
                    <button type="button" class="close" onclick="modalManager.hide('${id}')">&times;</button>
                </div>
                <div class="modal-body">
                    ${content}
                </div>
                ${buttons.length > 0 ? `<div class="modal-footer">${buttonsHtml}</div>` : ''}
            </div>
        `;
        
        // Add click handlers
        buttons.forEach((btn, index) => {
            if (btn.onclick) {
                const button = modal.querySelectorAll('.modal-footer button')[index];
                button.clickHandler = btn.onclick;
            }
        });
        
        // Close on backdrop click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hide(id);
            }
        });
        
        // Close on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal === modal) {
                this.hide(id);
            }
        });
        
        return modal;
    }
    
    trapFocus(modal) {
        const focusableElements = modal.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        
        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        
        firstElement?.focus();
        
        modal.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                if (e.shiftKey) {
                    if (document.activeElement === firstElement) {
                        lastElement?.focus();
                        e.preventDefault();
                    }
                } else {
                    if (document.activeElement === lastElement) {
                        firstElement?.focus();
                        e.preventDefault();
                    }
                }
            }
        });
    }
    
    setupEventListeners() {
        // Setup delete confirmation handlers
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-btn')) {
                e.preventDefault();
                const href = e.target.getAttribute('href');
                const itemType = e.target.getAttribute('data-type') || 'item';
                
                this.confirm(
                    'Confirm Delete',
                    `Are you sure you want to delete this ${itemType}? This action cannot be undone.`,
                    () => {
                        window.location.href = href;
                    }
                );
            }
        });
        
        // Setup form submission handlers
        document.addEventListener('submit', (e) => {
            if (e.target.classList.contains('confirm-submit')) {
                e.preventDefault();
                const form = e.target;
                const message = form.getAttribute('data-confirm') || 'Are you sure you want to submit this form?';
                
                this.confirm(
                    'Confirm Submission',
                    message,
                    () => {
                        form.submit();
                    }
                );
            }
        });
    }
}

// Initialize Modal Manager
const modalManager = new ModalManager();

// Replace default confirm and alert
window.confirm = function(message) {
    return new Promise((resolve) => {
        modalManager.confirm('Confirm', message, () => resolve(true), () => resolve(false));
    });
};

window.alert = function(message) {
    return new Promise((resolve) => {
        modalManager.alert('Alert', message, resolve);
    });
};
